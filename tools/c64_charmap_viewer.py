#!/usr/bin/env python3
import copy
import json
import logging
import math
import os
import sys
import time
import tkinter as tk
from collections import Counter
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from tset_parser import (
        FIXED_FLAGBITS,
        ObjectDef,
        TileDef,
        TilesetParseError,
        TsetParseResult,
        parse_tset,
        parse_tset_text,
    )
except ImportError:
    FIXED_FLAGBITS = {}
    ObjectDef = None
    TileDef = None
    TilesetParseError = Exception
    TsetParseResult = None
    parse_tset = None
    parse_tset_text = None

try:
    import koala_tilekit_compiler as tilekit_compiler
except ImportError:
    tilekit_compiler = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    from char_converter import ConvertResult, convert_image
except ImportError:
    ConvertResult = None
    convert_image = None

_c64img_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "c64img"))
if os.path.isdir(_c64img_path) and _c64img_path not in sys.path:
    sys.path.append(_c64img_path)
try:
    from c64img.hires import HiresConverter
    from c64img.multi import MultiConverter
    import c64img.base as c64img_base
except ImportError:
    HiresConverter = None
    MultiConverter = None
    c64img_base = None

if c64img_base is not None:
    def _safe_c64img_palette(self):
        pal = self._src_image.getpalette() or []
        if len(pal) < 16 * 3:
            pal = pal + [0] * (16 * 3 - len(pal))
        return [(pal[i], pal[i + 1], pal[i + 2]) for i in range(0, 16 * 3, 3)]

    c64img_base.FullScreenImage._get_palette = _safe_c64img_palette

    def _safe_c64img_find_most_freq_color(self, histogram):
        pal = self._src_image.getpalette() or []
        if len(pal) < 16 * 3:
            pal = pal + [0] * (16 * 3 - len(pal))
        pal = [tuple(pal[index:index + 3]) for index in range(0, len(pal), 3)]
        sorted_hist = sorted([(count, index)
                              for index, count in enumerate(histogram[:16])],
                             reverse=True)
        self.data['most_freq_colors'] = []
        for _, index in sorted_hist:
            color = self._palette_map[pal[index]]
            self.data['most_freq_colors'].append(color)
        self.data['most_freq_color'] = self.data['most_freq_colors'][0]

    c64img_base.FullScreenImage._find_most_freq_color = _safe_c64img_find_most_freq_color


C64_COLORS = [
    ("Black", "#000000"),
    ("White", "#FFFFFF"),
    ("Red", "#880000"),
    ("Cyan", "#AAFFEE"),
    ("Purple", "#CC44CC"),
    ("Green", "#00CC55"),
    ("Blue", "#0000AA"),
    ("Yellow", "#EEEE77"),
    ("Orange", "#DD8855"),
    ("Brown", "#664400"),
    ("Light Red", "#FF7777"),
    ("Dark Grey", "#333333"),
    ("Grey", "#777777"),
    ("Light Green", "#AAFF66"),
    ("Light Blue", "#0088FF"),
    ("Light Grey", "#BBBBBB"),
]


class CharsetApp:
    def __init__(
        self,
        root: tk.Tk,
        profile_enabled: bool = False,
        profile_log_path: str | None = None,
    ) -> None:
        self.root = root
        self.root.title("C64 Charset Viewer")

        self.charset_bytes = bytearray()
        self.current_file = None
        self.current_tset = None
        self.current_tset_path = None
        self.current_tset_charset = None
        self.recent_files = []
        self.recent_dir = os.path.join(os.path.expanduser("~"), ".c64_charmap")
        self.recent_path = os.path.join(self.recent_dir, "recent.json")
        self.dirty = False
        self.tset_dirty = False
        self.generated_assets = None
        self.logger = self._init_logger()
        self.profile_enabled = profile_enabled
        self.profile_log_path = profile_log_path
        self.profile_log_handle = None
        self._profile_stack = {}
        self._profile_totals = {}
        self._profile_counts = {}
        self._profile_stroke_started = None
        self._loading_tile_editor = False
        self.swatch_enabled = {}
        self.tile_flag_vars = {}
        self.tile_flag_checkbuttons = {}
        self.undo_stack = []
        self.undo_index = -1
        self._is_restoring = False
        self._undo_pending = False
        self._stroke_logged = False
        self._pending_tiles_redraw = False
        self._pending_objects_redraw = False

        self.grid_scale = 4
        self.preview_scale = 12
        self.charset_columns = 16
        self.columns = self.charset_columns
        self.page_chars = 256
        self.total_chars = 0
        self.has_second_tab = True
        self.selection_rects = [None, None]
        self.tile_selection_rects = [[None, None, None, None], [None, None, None, None]]
        self.multi_select_rects = [None, None]
        self.selection_indices = []
        self.selection_range = None
        self.selection_mode = None
        self.selection_anchor = None
        self.selection_dragged = False
        self.copy_buffer = None
        self.tile_scale = self.grid_scale
        self.tile_columns = 8
        self.object_scale = self.grid_scale
        self.object_columns = 1

        self.mode_var = tk.StringVar(value="hires")
        self.bg_var = tk.StringVar(value="Black")
        self.fg_var = tk.StringVar(value="White")
        self.mc1_var = tk.StringVar(value="Light Red")
        self.mc2_var = tk.StringVar(value="Light Green")

        self.selected_index = 0
        self.selected_tile = None
        self.selected_object = None
        self.paint_value = None
        self.paint_color_var = tk.StringVar(value="fg")
        self.paint_fg_override_index = None
        self.object_name_var = tk.StringVar(value="")
        self.object_char_var = tk.StringVar(value="")
        self._loading_object_editor = False
        self.paint_color_widgets = {}
        self.paint_color_mode = None
        self.tile_images = []
        self.object_images = []
        self.tile_entries = []
        self.object_entries = []
        self.tile_entry_by_id = {}
        self.char_to_tiles = {}
        self._pending_tile_update_ids = set()
        self._tile_update_after_id = None
        self._tile_update_delay_ms = 33
        self._objects_redraw_after_id = None
        self._refresh_selected_after_id = None

        self._build_menu()
        self._build_layout()
        self._bind_events()
        self._load_recent()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.report_callback_exception = self._report_callback_exception
        self.mode_var.trace_add("write", lambda *_: self._update_color_states())
        self._enforce_min_size()
        self.logger.info("App started")
        if self.profile_enabled:
            self.logger.info("Profiling enabled")
            self._open_profile_log()

    def _init_logger(self) -> logging.Logger:
        logger = logging.getLogger("c64_charmap_viewer")
        if logger.handlers:
            return logger
        logger.setLevel(logging.INFO)
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        logger.propagate = False
        return logger

    def _open_profile_log(self) -> None:
        if not self.profile_enabled or not self.profile_log_path:
            return
        try:
            os.makedirs(os.path.dirname(self.profile_log_path), exist_ok=True)
            self.profile_log_handle = open(self.profile_log_path, "a", encoding="utf-8")
            self.logger.info("Profiling log: %s", self.profile_log_path)
        except OSError as exc:
            self.logger.error("Failed to open profile log: %s", exc)
            self.profile_log_handle = None

    def _close_profile_log(self) -> None:
        handle = self.profile_log_handle
        if handle is None:
            return
        try:
            handle.flush()
            handle.close()
        except OSError:
            pass
        self.profile_log_handle = None

    def _profile_start(self, tag: str) -> None:
        if not self.profile_enabled:
            return
        self._profile_stack[tag] = time.perf_counter()

    def _profile_end(self, tag: str) -> None:
        if not self.profile_enabled:
            return
        start = self._profile_stack.pop(tag, None)
        if start is None:
            return
        elapsed = time.perf_counter() - start
        self._profile_totals[tag] = self._profile_totals.get(tag, 0.0) + elapsed
        self._profile_counts[tag] = self._profile_counts.get(tag, 0) + 1

    def _profile_reset_stroke(self) -> None:
        if not self.profile_enabled:
            return
        self._profile_stroke_started = time.perf_counter()
        self._profile_totals = {}
        self._profile_counts = {}

    def _profile_log_stroke(self) -> None:
        if not self.profile_enabled or self._profile_stroke_started is None:
            return
        total = time.perf_counter() - self._profile_stroke_started
        payload = {
            "event": "paint.stroke",
            "total_ms": round(total * 1000.0, 3),
            "counts": dict(self._profile_counts),
            "timings_ms": {tag: round(t * 1000.0, 3) for tag, t in self._profile_totals.items()},
        }
        if self.profile_log_handle:
            try:
                self.profile_log_handle.write(json.dumps(payload) + "\n")
                self.profile_log_handle.flush()
            except OSError:
                pass
        self.logger.info("PROFILE paint.stroke %s", payload)
        self._profile_stroke_started = None

    def _adopt_external_logger(self, name: str) -> None:
        external = logging.getLogger(name)
        external.handlers = list(self.logger.handlers)
        external.setLevel(logging.INFO)
        external.propagate = False

    def _report_callback_exception(self, exc_type, exc_value, exc_tb) -> None:
        self.logger.error(
            "Tk callback exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        messagebox.showerror("Unexpected error", str(exc_value))


    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="New Charset", command=self.new_charset)
        file_menu.add_command(label="New TSET", command=self.new_tset)
        file_menu.add_separator()
        file_menu.add_command(label="Open Charset...", command=self.open_charset)
        file_menu.add_command(label="Open TSET...", command=self.open_tset)
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        self.recent_menu.add_command(label="(empty)", state=tk.DISABLED)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        file_menu.add_command(label="Save Charset", command=self.save_file)
        file_menu.add_command(label="Save Charset As...", command=self.save_file_as)
        file_menu.add_command(label="Save TSET", command=self.save_tset)
        file_menu.add_command(label="Save TSET As...", command=self.save_tset_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copy Char...", command=self.copy_char)
        edit_menu.add_command(label="Move Char...", command=self.move_char)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut Selection", command=self.cut_selection)
        menu.add_cascade(label="Edit", menu=edit_menu)

        tools_menu = tk.Menu(menu, tearoff=0)
        tools_menu.add_command(label="Build Tileset from Koala Spec...", command=self.open_koala_spec)
        tools_menu.add_command(label="Create Chars/Tiles/Objects from Image...", command=self.open_image_region)
        menu.add_cascade(label="Tools", menu=tools_menu)

        tiles_menu = tk.Menu(menu, tearoff=0)
        tiles_menu.add_command(label="New Tile", command=self._new_tile)
        tiles_menu.add_command(label="Duplicate Tile", command=self._duplicate_tile)
        tiles_menu.add_command(label="Delete Tile", command=self._delete_tile)
        menu.add_cascade(label="Tiles", menu=tiles_menu)
        self.root.config(menu=menu)

    def _build_layout(self) -> None:
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        self.status_label = tk.Label(main, text="No charset loaded.")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 4))

        self.controls_frame = tk.Frame(main, padx=10, pady=8)
        self.controls_frame.pack(side=tk.TOP, fill=tk.X)

        self.content_frame = tk.Frame(main)
        self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.content_frame.columnconfigure(0, weight=0)
        self.content_frame.columnconfigure(1, weight=1)
        self.content_frame.rowconfigure(0, weight=1)

        self.left_frame = tk.Frame(self.content_frame)
        self.left_frame.grid(row=0, column=0, sticky="ns")
        self.left_frame.pack_propagate(False)

        right = tk.Frame(self.content_frame, padx=10, pady=10)
        right.grid(row=0, column=1, sticky="nsew")

        self.charset_tabs = ttk.Notebook(self.left_frame)
        self.charset_tabs.pack(fill=tk.BOTH, expand=False)

        self.grid_canvases = []
        self.grid_scrolls = []
        self.grid_frames = []
        for idx in range(2):
            grid_frame = tk.Frame(self.charset_tabs)
            self.charset_tabs.add(grid_frame, text=f"Charset {idx}")
            canvas = tk.Canvas(grid_frame, background="#111111")
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            self.grid_frames.append(grid_frame)
            self.grid_canvases.append(canvas)
            self.grid_scrolls.append(None)

        tiles_browser_frame = tk.LabelFrame(self.left_frame, text="Tiles")
        tiles_browser_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        options_frame = tk.Frame(self.controls_frame)
        options_frame.pack(side=tk.LEFT, fill=tk.X)

        tk.Label(options_frame, text="Mode").pack(side=tk.LEFT, padx=(6, 4))
        tk.Radiobutton(
            options_frame,
            text="Hires",
            variable=self.mode_var,
            value="hires",
            command=self.refresh_all,
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Radiobutton(
            options_frame,
            text="Multicolor",
            variable=self.mode_var,
            value="multicolor",
            command=self.refresh_all,
        ).pack(side=tk.LEFT, padx=(0, 12))

        tk.Label(options_frame, text="Background").pack(side=tk.LEFT, padx=(0, 2))
        self.bg_option = self._build_color_swatch_inline(options_frame, self.bg_var)
        tk.Label(options_frame, text="Foreground").pack(side=tk.LEFT, padx=(8, 2))
        self.fg_option = self._build_color_swatch_inline(options_frame, self.fg_var)
        tk.Label(options_frame, text="Multicolor1").pack(side=tk.LEFT, padx=(8, 2))
        self.mc1_option = self._build_color_swatch_inline(options_frame, self.mc1_var)
        tk.Label(options_frame, text="Multicolor2").pack(side=tk.LEFT, padx=(8, 2))
        self.mc2_option = self._build_color_swatch_inline(options_frame, self.mc2_var)
        self._update_color_states()

        right_stack = tk.Frame(right)
        right_stack.pack(fill=tk.BOTH, expand=True)

        editor_row = tk.Frame(right_stack)

        preview_frame = tk.LabelFrame(editor_row, text="Char Editor")
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        size = 8 * self.preview_scale
        self.preview_canvas = tk.Canvas(
            preview_frame, width=size, height=size, background="#111111"
        )
        self.preview_canvas.pack(padx=8, pady=8)
        self.preview_image_id = self.preview_canvas.create_image(0, 0, anchor="nw")
        self._draw_preview_grid()

        edit_hint = tk.Label(
            preview_frame,
            text="Click or drag to edit",
            foreground="#888888",
        )
        edit_hint.pack(pady=(0, 6))
        self._build_paint_color_controls(preview_frame)

        tile_editor_frame = tk.LabelFrame(editor_row, text="Tile Editor")
        tile_editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        self._build_tile_editor(tile_editor_frame)

        browser_frame = tk.LabelFrame(right_stack, text="Objects")

        objects_tab = tk.Frame(browser_frame)
        objects_tab.pack(fill=tk.BOTH, expand=True)

        self.tiles_view = tk.Frame(tiles_browser_frame)
        self.tiles_view.pack(fill=tk.BOTH, expand=True)
        self.tiles_view.columnconfigure(0, weight=1)
        self.tiles_view.rowconfigure(0, weight=1)
        self.tiles_canvas = tk.Canvas(self.tiles_view, background="#0f0f0f")
        self.tiles_canvas.grid(row=0, column=0, sticky="nsew")
        tiles_scroll = tk.Scrollbar(self.tiles_view, orient=tk.VERTICAL, command=self.tiles_canvas.yview)
        self.tiles_canvas.configure(yscrollcommand=tiles_scroll.set)
        tiles_scroll.grid(row=0, column=1, sticky="ns")
        self.tiles_scrollbar = tiles_scroll

        self.tiles_status = tk.Label(tiles_browser_frame, text="No tiles loaded.", anchor="w")
        self.tiles_status.pack(fill=tk.X, pady=(6, 0))
        self.tile_flags_frame = tk.Frame(tiles_browser_frame)
        self.tile_flags_frame.pack_forget()
        self.tile_flags_placeholder = tk.Label(self.tile_flags_frame, text="(no tileset loaded)")
        self.tile_flags_placeholder.pack_forget()
        self.tile_hint_label = tk.Label(tiles_browser_frame, text="", anchor="w")
        self.tile_hint_label.pack_forget()

        self.objects_view = tk.Frame(objects_tab)
        self.objects_view.grid(row=0, column=0, sticky="nsew")
        self.objects_view.columnconfigure(0, weight=1)
        self.objects_view.rowconfigure(0, weight=1)
        self.objects_canvas = tk.Canvas(self.objects_view, background="#0f0f0f")
        self.objects_canvas.grid(row=0, column=0, sticky="nsew")
        objects_scroll = tk.Scrollbar(
            self.objects_view, orient=tk.VERTICAL, command=self.objects_canvas.yview
        )
        self.objects_canvas.configure(yscrollcommand=objects_scroll.set)
        objects_scroll.grid(row=0, column=1, sticky="ns")
        self.objects_scrollbar = objects_scroll

        objects_preview = tk.Frame(objects_tab, padx=8)
        objects_preview.grid(row=0, column=1, sticky="nsew")
        self.objects_status = tk.Label(objects_preview, text="No objects loaded.", anchor="w")
        self.objects_status.pack(fill=tk.X)
        obj_form = tk.Frame(objects_preview)
        obj_form.pack(fill=tk.X, pady=(4, 4))
        tk.Label(obj_form, text="Name").grid(row=0, column=0, sticky="w")
        obj_name_entry = tk.Entry(obj_form, textvariable=self.object_name_var, width=20)
        obj_name_entry.grid(row=0, column=1, sticky="w", padx=(6, 12))
        obj_name_entry.bind("<FocusOut>", lambda _e: self._commit_object_name())
        obj_name_entry.bind("<Return>", lambda _e: self._commit_object_name())
        tk.Label(obj_form, text="Char").grid(row=0, column=2, sticky="w")
        obj_char_entry = tk.Entry(obj_form, textvariable=self.object_char_var, width=4)
        obj_char_entry.grid(row=0, column=3, sticky="w", padx=(6, 0))
        obj_char_entry.bind("<FocusOut>", lambda _e: self._commit_object_char())
        obj_char_entry.bind("<Return>", lambda _e: self._commit_object_char())
        self.object_preview_canvas = tk.Canvas(objects_preview, background=objects_preview.cget("bg"), highlightthickness=0)
        self.object_preview_canvas.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.object_preview_image_id = self.object_preview_canvas.create_image(0, 0, anchor="nw")

        objects_tab.columnconfigure(0, weight=0)
        objects_tab.columnconfigure(1, weight=1)
        objects_tab.rowconfigure(0, weight=1)

        editor_row.pack(fill=tk.X, pady=(0, 8))
        browser_frame.pack(fill=tk.BOTH, expand=True)
        self.root.after(0, self._enforce_min_size)

    def _build_color_selector(self, parent: tk.Widget, label: str, var: tk.StringVar) -> None:
        frame = tk.Frame(parent)
        frame.pack(fill=tk.X, pady=1)
        tk.Label(frame, text=label, width=10, anchor="w").pack(side=tk.LEFT)
        option = tk.OptionMenu(
            frame,
            var,
            *[name for name, _ in C64_COLORS],
            command=lambda _: self._on_color_change(),
        )
        option.config(width=12)
        option.pack(side=tk.LEFT, fill=tk.X, expand=True)
        swatch = tk.Label(frame, width=2, relief="sunken")
        swatch.pack(side=tk.RIGHT, padx=4)
        swatch.configure(background=self._color_hex(var.get()))
        var.trace_add("write", lambda *_: swatch.configure(background=self._color_hex(var.get())))

    def _build_color_swatch_inline(self, parent: tk.Widget, var: tk.StringVar) -> tk.Canvas:
        swatch = tk.Canvas(parent, width=24, height=24, highlightthickness=0)
        swatch.pack(side=tk.LEFT)
        rect = swatch.create_rectangle(1, 1, 23, 23, outline="#333333", fill=self._color_hex(var.get()))
        swatch._rect_id = rect
        self._set_swatch_enabled(swatch, True)
        swatch.bind("<Button-1>", lambda _e: self._on_swatch_click(swatch, var))
        var.trace_add("write", lambda *_: swatch.itemconfigure(rect, fill=self._color_hex(var.get())))
        return swatch

    def _build_tile_color_swatch(self, parent: tk.Widget, var: tk.StringVar) -> tk.Canvas:
        swatch = tk.Canvas(parent, width=24, height=24, highlightthickness=0)
        rect = swatch.create_rectangle(1, 1, 23, 23, outline="#333333", fill=self._color_hex(var.get()))
        swatch._rect_id = rect
        swatch.bind("<Button-1>", lambda _e: self._open_color_palette(var))
        var.trace_add("write", lambda *_: swatch.itemconfigure(rect, fill=self._color_hex(var.get())))
        return swatch

    def _build_paint_color_controls(self, parent: tk.Widget) -> None:
        frame = tk.Frame(parent)
        frame.pack(pady=(0, 6))
        self.paint_color_frame = frame
        self._ensure_paint_color_controls()

    def _ensure_paint_color_controls(self) -> None:
        frame = getattr(self, "paint_color_frame", None)
        if frame is None:
            return
        if self.mode_var.get() == "multicolor":
            options = [("BG", "bg"), ("MC1", "mc1"), ("MC2", "mc2"), ("FG", "fg")]
        else:
            options = [("BG", "bg"), ("FG", "fg")]
        if self.paint_color_mode == self.mode_var.get() and self.paint_color_widgets:
            self._update_paint_swatch_colors()
            valid_values = {value for _, value in options}
            if self.paint_color_var.get() not in valid_values:
                self.paint_color_var.set(options[-1][1])
            return
        for child in frame.winfo_children():
            child.destroy()
        self.paint_color_widgets = {}
        self.paint_color_mode = self.mode_var.get()
        for label, value in options:
            row = tk.Frame(frame)
            row.pack(anchor="w")
            tk.Radiobutton(
                row,
                text=label,
                variable=self.paint_color_var,
                value=value,
                indicatoron=True,
            ).pack(side=tk.LEFT)
            if value == "bg":
                var = self.bg_var
            elif value == "mc1":
                var = self.mc1_var
            elif value == "mc2":
                var = self.mc2_var
            else:
                var = self.fg_var
            swatch = tk.Canvas(row, width=24, height=24, highlightthickness=0)
            rect = swatch.create_rectangle(
                1, 1, 23, 23, outline="#333333", fill=self._paint_swatch_hex(value)
            )
            swatch._rect_id = rect
            swatch.pack(side=tk.LEFT, padx=(6, 0))
            def _update_swatch(*_args, v=var, s=swatch, token=value):
                if not s.winfo_exists():
                    return
                if token == "fg":
                    s.itemconfigure(s._rect_id, fill=self._paint_swatch_hex(token))
                else:
                    s.itemconfigure(s._rect_id, fill=self._color_hex(v.get()))
            var.trace_add("write", _update_swatch)
            self.paint_color_widgets[value] = (swatch, var)
        valid_values = {value for _, value in options}
        if self.paint_color_var.get() not in valid_values:
            self.paint_color_var.set(options[-1][1])

    def _update_paint_swatch_colors(self) -> None:
        for token, (swatch, var) in self.paint_color_widgets.items():
            if not swatch.winfo_exists():
                continue
            if token == "fg":
                swatch.itemconfigure(swatch._rect_id, fill=self._paint_swatch_hex(token))
            else:
                swatch.itemconfigure(swatch._rect_id, fill=self._color_hex(var.get()))

    def _paint_value_for_color(self, token: str, current: int | None = None) -> int | None:
        if self.mode_var.get() == "multicolor":
            mapping = {"bg": 0, "mc1": 1, "mc2": 2, "fg": 3}
            return mapping.get(token)
        if token == "fg":
            return 1
        if token == "bg":
            return 0
        if current is None:
            return None
        return 0 if current else 1

    def _paint_swatch_hex(self, token: str) -> str:
        if token == "fg" and self.paint_fg_override_index is not None:
            return self._color_hex_by_index(self.paint_fg_override_index)
        if token == "bg":
            return self._color_hex(self.bg_var.get())
        if token == "mc1":
            return self._color_hex(self.mc1_var.get())
        if token == "mc2":
            return self._color_hex(self.mc2_var.get())
        return self._color_hex(self.fg_var.get())

    def _paint_token_for_color_index(self, color_index: int) -> str:
        if color_index == self._color_index_by_name(self.bg_var.get()):
            return "bg"
        if self.mode_var.get() == "multicolor":
            if color_index == self._color_index_by_name(self.mc1_var.get()):
                return "mc1"
            if color_index == self._color_index_by_name(self.mc2_var.get()):
                return "mc2"
        if color_index == self._color_index_by_name(self.fg_var.get()):
            return "fg"
        return "fg"

    def _set_swatch_enabled(self, swatch: tk.Canvas, enabled: bool) -> None:
        self.swatch_enabled[swatch] = enabled
        outline = "#333333" if enabled else "#222222"
        swatch.itemconfigure(swatch._rect_id, outline=outline)

    def _on_swatch_click(self, swatch: tk.Canvas, var: tk.StringVar) -> None:
        if swatch in (getattr(self, "mc1_option", None), getattr(self, "mc2_option", None)):
            if self.mode_var.get() == "hires":
                return
        if not self.swatch_enabled.get(swatch, True):
            return
        self._open_color_palette(var)

    def _open_color_palette(self, var: tk.StringVar) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Color")
        dialog.transient(self.root)
        dialog.update_idletasks()
        dialog.grab_set()

        selected = {"name": var.get()}

        header = tk.Frame(dialog, padx=10, pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="Selected", width=10, anchor="w").pack(side=tk.LEFT)
        selected_label = tk.Label(header, text=selected["name"], width=12, anchor="w")
        selected_label.pack(side=tk.LEFT, padx=(0, 6))
        selected_swatch = tk.Label(header, width=2, relief="sunken")
        selected_swatch.pack(side=tk.LEFT)
        selected_swatch.configure(background=self._color_hex(selected["name"]))

        palette = tk.Frame(dialog, padx=10, pady=6)
        palette.pack()
        cols = 8
        swatches = {}
        for idx, (name, hex_value) in enumerate(C64_COLORS):
            row = idx // cols
            col = idx % cols
            swatch = tk.Canvas(palette, width=20, height=20, highlightthickness=0)
            rect = swatch.create_rectangle(1, 1, 19, 19, outline="#333333", fill=hex_value)
            swatch.grid(row=row, column=col, padx=4, pady=4)
            swatches[name] = (swatch, rect)
            swatch.bind(
                "<Button-1>",
                lambda _e, n=name: self._select_palette_color(
                    selected, n, selected_label, selected_swatch, swatches
                ),
            )
        self._select_palette_color(selected, selected["name"], selected_label, selected_swatch, swatches)

        actions = tk.Frame(dialog, padx=10, pady=10)
        actions.pack(fill=tk.X)
        tk.Button(actions, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(actions, text="OK", command=lambda: self._apply_palette_color(dialog, var, selected["name"])).pack(side=tk.RIGHT)

        def _enforce_import_dialog_min():
            dialog.update_idletasks()
            dialog.minsize(dialog.winfo_reqwidth(), dialog.winfo_reqheight())
        dialog.after(0, _enforce_import_dialog_min)
        dialog.wait_window()

    def _select_palette_color(
        self,
        selected: dict,
        name: str,
        label: tk.Label,
        swatch: tk.Label,
        swatches: dict,
    ) -> None:
        selected["name"] = name
        label.configure(text=name)
        swatch.configure(background=self._color_hex(name))
        for swatch_name, (canvas, rect) in swatches.items():
            outline = "#FFFF00" if swatch_name == name else "#333333"
            canvas.itemconfigure(rect, outline=outline)

    def _apply_palette_color(self, dialog: tk.Toplevel, var: tk.StringVar, name: str) -> None:
        if var in (self.bg_var, self.fg_var, self.mc1_var, self.mc2_var) and var.get() != name:
            self._record_undo()
        var.set(name)
        self._on_color_change()
        dialog.destroy()

    def _build_tile_editor(self, parent: tk.Widget) -> None:
        form_row = tk.Frame(parent)
        form_row.pack(fill=tk.X, pady=(2, 4))
        header = tk.Frame(form_row)
        header.pack(fill=tk.X, expand=True)
        self.tile_id_var = tk.StringVar(value="-")
        self.tile_name_var = tk.StringVar(value="")
        name_block = tk.Frame(header)
        name_block.pack(side=tk.LEFT, padx=(4, 6))
        tk.Label(name_block, text="Name").pack(side=tk.LEFT)
        name_entry = tk.Entry(name_block, textvariable=self.tile_name_var, width=24)
        name_entry.pack(side=tk.LEFT, padx=(6, 0))
        name_entry.bind("<FocusOut>", lambda _e: self._commit_tile_name())
        name_entry.bind("<Return>", lambda _e: self._commit_tile_name())
        self.tile_hint_var = tk.StringVar(value="")
        hint_block = tk.Frame(header)
        hint_block.pack(side=tk.LEFT, padx=(12, 6))
        tk.Label(hint_block, text="Hint").pack(side=tk.LEFT)
        hint_options = ["", "roof", "floor", "platform", "wall", "wall_right", "wall_left"]
        tk.OptionMenu(
            hint_block,
            self.tile_hint_var,
            *hint_options,
            command=lambda *_: self._sync_tile_from_editor(update_name=False),
        ).pack(side=tk.LEFT, padx=(6, 0))
        hint_menu = hint_block.winfo_children()[-1]
        try:
            hint_menu.config(width=14)
        except Exception:
            pass

        per_row = tk.Frame(parent)
        per_row.pack(fill=tk.X, pady=(0, 6))
        self.tile_color_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            per_row,
            text="Per-quadrant colors",
            variable=self.tile_color_mode_var,
        ).pack(anchor="w", pady=(4, 0))
        self.tile_color_mode_var.trace_add("write", lambda *_: self._update_tile_preview())
        self.tile_color_mode_var.trace_add("write", lambda *_: self._sync_tile_from_editor(update_name=False))

        self.tile_char_vars = []
        self.tile_color_vars = []
        self.tile_hex_labels = []
        self.tile_quadrant_frames = []
        self.tile_selected_quadrant = 0
        body_row = tk.Frame(parent)
        body_row.pack(fill=tk.X, pady=(4, 6))
        left_col = tk.Frame(body_row)
        left_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
        right_col = tk.Frame(body_row)
        right_col.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))

        preview_row = tk.Frame(left_col)
        preview_row.pack(fill=tk.X, pady=(0, 6))
        self.tile_preview_size = 2 * 8 * self.preview_scale
        self.tile_preview_canvas = tk.Canvas(
            preview_row, width=self.tile_preview_size, height=self.tile_preview_size, background="#111111"
        )
        self.tile_preview_canvas.pack(side=tk.LEFT, padx=(4, 8))
        self.tile_preview_canvas.bind("<Button-1>", self._on_tile_preview_click)

        selectors = tk.Frame(right_col)
        selectors.pack(side=tk.TOP, anchor="n")
        labels = ["TL", "TR", "BL", "BR"]
        for idx in range(4):
            cell = tk.LabelFrame(selectors, text=labels[idx])
            cell.grid(row=idx // 2, column=idx % 2, padx=4, pady=4, sticky="nsew")
            self.tile_quadrant_frames.append(cell)
            char_var = tk.IntVar(value=0)
            color_var = tk.StringVar(value="White")
            self.tile_char_vars.append(char_var)
            self.tile_color_vars.append(color_var)

            char_row = tk.Frame(cell)
            char_row.pack(anchor="w")
            tk.Label(char_row, text="Char").pack(side=tk.LEFT)
            char_value = tk.Label(char_row, textvariable=char_var, width=4)
            char_value.pack(side=tk.LEFT, padx=(4, 2))
            hex_label = tk.Label(char_row, text="0x00", width=6)
            hex_label.pack(side=tk.LEFT)
            self.tile_hex_labels.append(hex_label)
            char_var.trace_add("write", lambda *_args, i=idx: self._update_tile_hex(i))
            char_var.trace_add("write", lambda *_args: self._update_tile_preview())
            color_var.trace_add("write", lambda *_args: self._update_tile_preview())
            char_var.trace_add("write", lambda *_args: self._sync_tile_from_editor(update_name=False))
            color_var.trace_add("write", lambda *_args: self._sync_tile_from_editor(update_name=False))

            color_row = tk.Frame(cell)
            color_row.pack(anchor="w", pady=(4, 0))
            tk.Label(color_row, text="Color").pack(side=tk.LEFT)
            color_swatch = self._build_tile_color_swatch(color_row, color_var)
            color_swatch.pack(side=tk.LEFT, padx=(4, 0))
            tk.Label(color_row, text="Set").pack(side=tk.LEFT, padx=(6, 2))
            tk.Button(
                color_row,
                text="Char",
                width=3,
                padx=2,
                pady=0,
                command=lambda i=idx: self._set_tile_char_from_selected(i),
            ).pack(side=tk.LEFT, padx=(6, 0))

        actions = tk.Frame(left_col)
        actions.pack(fill=tk.X, pady=(0, 6))
        actions.pack_forget()

        flags_frame = tk.LabelFrame(parent, text="Flags")
        flags_frame.pack(fill=tk.BOTH, expand=True, padx=(4, 4), pady=(4, 4))
        flags_canvas = tk.Canvas(flags_frame, highlightthickness=0)
        flags_scroll = tk.Scrollbar(flags_frame, orient=tk.VERTICAL, command=flags_canvas.yview)
        flags_canvas.configure(yscrollcommand=flags_scroll.set)
        flags_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        flags_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        flags_body = tk.Frame(flags_canvas)
        flags_canvas.create_window((0, 0), window=flags_body, anchor="nw")
        flags_body.bind(
            "<Configure>",
            lambda _e: flags_canvas.configure(scrollregion=flags_canvas.bbox("all")),
        )
        self.tile_flags_row_height = 24
        self.tile_flags_min_rows = 2
        flags_canvas.configure(height=self.tile_flags_row_height * self.tile_flags_min_rows)
        self.tile_flags_canvas = flags_canvas
        self.tile_flags_scroll = flags_scroll
        self.tile_flags_editor = flags_body
        self.tile_flags_editor_placeholder = tk.Label(self.tile_flags_editor, text="(no tileset loaded)")
        self.tile_flags_editor_placeholder.grid(row=0, column=0, sticky="w")

    def _update_tile_hex(self, index: int) -> None:
        if index >= len(self.tile_char_vars):
            return
        value = int(self.tile_char_vars[index].get())
        self.tile_hex_labels[index].configure(text=f"0x{value:02X}")

    def _set_tile_char_from_selected(self, index: int) -> None:
        if not (0 <= index < len(self.tile_char_vars)):
            return
        if not self.charset_bytes:
            return
        self.tile_char_vars[index].set(self.selected_index)

    def _tile_editor_data(self) -> tuple[list[int], list[int], int]:
        chars = [int(var.get()) for var in self.tile_char_vars]
        if self.tile_color_mode_var.get():
            colors = [self._color_index_by_name(var.get()) for var in self.tile_color_vars]
            color_mode = 1
        else:
            color = self._color_index_by_name(self.tile_color_vars[0].get())
            colors = [color, 0, 0, 0]
            color_mode = 0
        return chars, colors, color_mode

    def _update_tile_preview(self) -> None:
        if not hasattr(self, "tile_preview_canvas"):
            return
        if TileDef is None:
            return
        chars, colors, color_mode = self._tile_editor_data()
        tile = TileDef(
            tid=0,
            name="PREVIEW",
            chars=chars,
            color_mode=color_mode,
            colors=colors,
            flags=0,
        )
        rows = self._render_tile_rows(tile)
        scale = self.tile_preview_size // 16
        image = tk.PhotoImage(width=self.tile_preview_size, height=self.tile_preview_size)
        for y, row in enumerate(rows):
            expanded_row = []
            for color in row:
                expanded_row.extend([color] * scale)
            row_data = "{" + " ".join(expanded_row) + "}"
            for sy in range(scale):
                image.put(row_data, to=(0, y * scale + sy))
        self.tile_preview_image = image
        self.tile_preview_canvas.delete("all")
        self.tile_preview_canvas.create_image(0, 0, anchor="nw", image=image)
        size = self.tile_preview_size
        half = size // 2
        for idx, char_index in enumerate(chars):
            if char_index != self.selected_index:
                continue
            x0 = 0 if idx % 2 == 0 else half
            y0 = 0 if idx < 2 else half
            x1 = x0 + half
            y1 = y0 + half
            self.tile_preview_canvas.create_rectangle(
                x0, y0, x1, y1, outline="#FFFF00", width=2
            )

    def _on_tile_preview_click(self, event: tk.Event) -> None:
        size = self.tile_preview_size
        if not (0 <= event.x < size and 0 <= event.y < size):
            return
        col = 0 if event.x < size / 2 else 1
        row = 0 if event.y < size / 2 else 1
        self.tile_selected_quadrant = row * 2 + col
        self.logger.info("Tile preview quadrant selected: %s", self.tile_selected_quadrant)
        if self.current_tset and self.selected_tile is not None:
            tile = self.current_tset.tiles.get(self.selected_tile)
            if tile:
                if tile.color_mode == 1 and self.tile_selected_quadrant < len(tile.colors):
                    color_index = tile.colors[self.tile_selected_quadrant]
                else:
                    color_index = tile.colors[0] if tile.colors else 0
                self.paint_fg_override_index = color_index
                self.paint_color_var.set("fg")
                self._update_paint_swatch_colors()
        if self.charset_bytes and 0 <= self.tile_selected_quadrant < len(self.tile_char_vars):
            try:
                new_index = int(self.tile_char_vars[self.tile_selected_quadrant].get())
            except (TypeError, ValueError, tk.TclError):
                new_index = None
            if new_index is not None and 0 <= new_index < self.total_chars:
                self.selected_index = new_index
                page = new_index // self.page_chars
                local = new_index % self.page_chars
                col = local % self.columns
                row = local // self.columns
                self.selection_range = (page, col, row, col, row)
                self.selection_indices = [new_index]
                self._update_multi_selection_rect()
                self.refresh_selected()
        self._update_tile_preview()


    def _load_tile_editor(self, tile) -> None:
        self._loading_tile_editor = True
        self.tile_id_var.set(str(tile.tid))
        self.tile_name_var.set(tile.name)
        if hasattr(self, "tile_hint_var"):
            self.tile_hint_var.set(getattr(tile, "hint", "") or "")
        self._sync_flags_from_tile(tile)
        self.tile_color_mode_var.set(tile.color_mode == 1)
        chars = tile.chars
        colors = tile.colors if tile.color_mode == 1 else [tile.colors[0]] * 4
        for idx in range(4):
            self.tile_char_vars[idx].set(chars[idx])
            self.tile_color_vars[idx].set(self._color_name_by_index(colors[idx]))
            self._update_tile_hex(idx)
        self.tile_selected_quadrant = 0
        self._update_tile_preview()
        self._loading_tile_editor = False
        self._update_tile_flags_display()

    def _apply_tile_edits(self) -> None:
        self.logger.info("Apply tile edits")
        self._sync_tile_from_editor(update_name=True)

    def _commit_tile_name(self) -> None:
        if self._loading_tile_editor:
            return
        if not self.current_tset or self.selected_tile is None:
            return
        self._sync_tile_from_editor(update_name=True)

    def _sync_tile_from_editor(self, update_name: bool) -> None:
        if self._loading_tile_editor:
            return
        if not self.current_tset or self.selected_tile is None:
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if tile is None:
            return

        changed = self._tile_editor_changed(tile, update_name)
        old_name = tile.name
        old_chars = list(tile.chars)
        old_colors = list(tile.colors)
        old_color_mode = tile.color_mode
        old_flags = tile.flags

        if update_name:
            new_name = self.tile_name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Invalid name", "Tile name cannot be empty.")
                return
            new_key = new_name.upper()
            if new_key != tile.name.upper() and new_key in self.current_tset.tiles_by_name:
                messagebox.showwarning("Invalid name", "Tile name must be unique.")
                return
            old_name = tile.name
            if new_key != old_name.upper():
                del self.current_tset.tiles_by_name[old_name.upper()]
                self.current_tset.tiles_by_name[new_key] = tile.tid
                for obj in self.current_tset.objects.values():
                    obj.tiles = [new_name if t == old_name else t for t in obj.tiles]
            tile.name = new_name

        tile.chars = [int(var.get()) for var in self.tile_char_vars]
        if self.tile_color_mode_var.get():
            tile.color_mode = 1
            tile.colors = [self._color_index_by_name(var.get()) for var in self.tile_color_vars]
        else:
            tile.color_mode = 0
            color = self._color_index_by_name(self.tile_color_vars[0].get())
            tile.colors = [color, 0, 0, 0]
        if update_name:
            tile.flags = self._flags_from_editor()
        if hasattr(self, "tile_hint_var"):
            tile.hint = self.tile_hint_var.get().strip()

        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        if update_name:
            self._load_tile_editor(tile)
        if changed:
            self.logger.info(
                "Tile updated id=%s name=%s (chars=%s colors=%s mode=%s flags=0x%X)",
                tile.tid,
                tile.name,
                old_chars != tile.chars,
                old_colors != tile.colors,
                old_color_mode != tile.color_mode,
                old_flags != tile.flags,
            )
            self._record_undo()

    def _next_tile_id(self) -> int:
        if not self.current_tset.tiles:
            return 0
        return max(self.current_tset.tiles.keys()) + 1

    def _new_tile(self) -> None:
        if not self.current_tset:
            return
        if TileDef is None:
            messagebox.showerror("Tile editor", "tset_parser is not available.")
            return
        tid = self._next_tile_id()
        name = f"TILE_{tid}"
        while name.upper() in self.current_tset.tiles_by_name:
            tid += 1
            name = f"TILE_{tid}"
        fg = self._color_index_by_name(self.fg_var.get())
        tile = TileDef(
            tid=tid,
            name=name,
            chars=[0, 0, 0, 0],
            color_mode=1,
            colors=[fg, fg, fg, fg],
            flags=0,
            hint="",
        )
        self.current_tset.tiles[tid] = tile
        self.current_tset.tiles_by_name[name.upper()] = tid
        self.selected_tile = tid
        self.logger.info("Tile created id=%s name=%s", tid, name)
        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._load_tile_editor(tile)
        self._record_undo()

    def _duplicate_tile(self) -> None:
        if not self.current_tset or self.selected_tile is None:
            return
        if TileDef is None:
            messagebox.showerror("Tile editor", "tset_parser is not available.")
            return
        source = self.current_tset.tiles.get(self.selected_tile)
        if source is None:
            return
        tid = self._next_tile_id()
        name = f"{source.name}_COPY"
        while name.upper() in self.current_tset.tiles_by_name:
            tid += 1
            name = f"{source.name}_{tid}"
        tile = TileDef(
            tid=tid,
            name=name,
            chars=list(source.chars),
            color_mode=source.color_mode,
            colors=list(source.colors),
            flags=source.flags,
            hint=getattr(source, "hint", ""),
        )
        self.current_tset.tiles[tid] = tile
        self.current_tset.tiles_by_name[name.upper()] = tid
        self.selected_tile = tid
        self.logger.info("Tile duplicated from id=%s to id=%s name=%s", source.tid, tid, name)
        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._load_tile_editor(tile)
        self._record_undo()

    def _ensure_default_tile_id(self) -> int:
        if not self.current_tset.tiles:
            if TileDef is None:
                messagebox.showerror("Tile editor", "tset_parser is not available.")
                return 0
            tile = TileDef(
                tid=0,
                name="DEFAULT",
                chars=[0, 0, 0, 0],
                color_mode=0,
                colors=[0, 0, 0, 0],
                flags=0,
                hint="",
            )
            self.current_tset.tiles[0] = tile
            self.current_tset.tiles_by_name["DEFAULT"] = 0
        return min(self.current_tset.tiles.keys())

    def _delete_tile(self) -> None:
        if not self.current_tset or self.selected_tile is None:
            return
        if len(self.current_tset.tiles) <= 1:
            messagebox.showwarning("Delete tile", "At least one tile must remain.")
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if tile is None:
            return
        default_id = self._ensure_default_tile_id()
        if default_id == tile.tid and len(self.current_tset.tiles) > 1:
            default_id = next(tid for tid in sorted(self.current_tset.tiles) if tid != tile.tid)
        default_name = self.current_tset.tiles[default_id].name

        refs = 0
        for tid in self.current_tset.charmap_tiles.values():
            if tid == tile.tid:
                refs += 1
        for obj in self.current_tset.objects.values():
            for tname in obj.tiles:
                if tname.upper() == tile.name.upper():
                    refs += 1

        if not messagebox.askyesno(
            "Delete tile",
            f"Delete tile '{tile.name}' and replace {refs} references with '{default_name}'?",
        ):
            return

        for ch, tid in list(self.current_tset.charmap_tiles.items()):
            if tid == tile.tid:
                self.current_tset.charmap_tiles[ch] = default_id
        for obj in self.current_tset.objects.values():
            obj.tiles = [
                default_name if tname.upper() == tile.name.upper() else tname
                for tname in obj.tiles
            ]

        del self.current_tset.tiles_by_name[tile.name.upper()]
        del self.current_tset.tiles[tile.tid]
        self.selected_tile = default_id
        self.logger.info(
            "Tile deleted id=%s name=%s replaced_with=%s refs=%s",
            tile.tid,
            tile.name,
            default_name,
            refs,
        )
        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._load_tile_editor(self.current_tset.tiles[default_id])
        self._record_undo()

    def _update_tiles_status(self, count: int | None = None) -> None:
        suffix = " *" if self.tset_dirty else ""
        if self.current_tset and self.selected_tile is not None:
            tile = self.current_tset.tiles.get(self.selected_tile)
            if tile:
                self.tiles_status.configure(text=f"{tile.name}{suffix}")
                return
        if count is None and self.current_tset:
            count = len(self.current_tset.tiles)
        if count is None:
            self.tiles_status.configure(text="No tiles loaded.")
            return
        self.tiles_status.configure(text=f"{count} tiles loaded.{suffix}")

    def _init_flag_vars(self, clear: bool = False) -> None:
        if clear or not self.current_tset:
            self.tile_flag_vars = {}
            self.tile_flag_checkbuttons = {}
            self._update_tile_flags_display()
            return
        self.tile_flag_vars = {}
        for name, bit in sorted(self.current_tset.flagbits.items(), key=lambda item: item[1]):
            self.tile_flag_vars[name] = (tk.IntVar(value=0), bit)
        self._build_tile_flag_checkbuttons()
        self._update_tile_flags_display()

    def _build_tile_flag_checkbuttons(self) -> None:
        if not hasattr(self, "tile_flags_editor"):
            return
        placeholder = getattr(self, "tile_flags_editor_placeholder", None)
        for child in self.tile_flags_editor.winfo_children():
            if child is placeholder:
                continue
            child.destroy()
        self.tile_flag_checkbuttons = {}
        if not self.tile_flag_vars:
            if placeholder and placeholder.winfo_exists():
                placeholder.grid()
            return
        if placeholder is None or not placeholder.winfo_exists():
            self.tile_flags_editor_placeholder = tk.Label(self.tile_flags_editor, text="(no tileset loaded)")
            placeholder = self.tile_flags_editor_placeholder
            placeholder.grid()
        row = 0
        col = 0
        for name, (var, _bit) in sorted(self.tile_flag_vars.items(), key=lambda item: item[1][1]):
            cb = tk.Checkbutton(
                self.tile_flags_editor,
                text=name,
                variable=var,
                command=self._on_flag_toggle,
            )
            cb.grid(row=row, column=col, sticky="w", padx=(0, 12), pady=1)
            self.tile_flag_checkbuttons[name] = cb
            col += 1
            if col >= 4:
                col = 0
                row += 1
        if hasattr(self, "tile_flags_canvas"):
            self.tile_flags_canvas.update_idletasks()
            bbox = self.tile_flags_canvas.bbox("all")
            if bbox:
                content_h = max(1, bbox[3] - bbox[1] + 6)
                min_h = self.tile_flags_row_height * self.tile_flags_min_rows
                self.tile_flags_canvas.configure(height=max(min_h, content_h))

    def _on_flag_toggle(self) -> None:
        if self._loading_tile_editor:
            return
        if not self.current_tset or self.selected_tile is None:
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if tile is None:
            return
        old_flags = tile.flags
        tile.flags = self._flags_from_editor()
        if tile.flags != old_flags:
            self._mark_tset_dirty()
            self._update_tile_flags_display()
            self._record_undo()

    def _flags_from_editor(self) -> int:
        flags = 0
        for name, (var, bit) in self.tile_flag_vars.items():
            if var.get():
                flags |= (1 << bit)
        return flags

    def _sync_flags_from_tile(self, tile) -> None:
        if not self.tile_flag_vars:
            return
        for name, (var, bit) in self.tile_flag_vars.items():
            var.set(1 if tile.flags & (1 << bit) else 0)
        self._update_tile_flags_display()

    def _update_tile_flags_display(self) -> None:
        for child in self.tile_flags_frame.winfo_children():
            if child is not self.tile_flags_placeholder:
                child.destroy()
        if hasattr(self, "tile_flags_editor"):
            for child in self.tile_flags_editor.winfo_children():
                if child is not self.tile_flags_editor_placeholder:
                    child.grid_remove()
        if not self.current_tset:
            self.tile_flags_placeholder.configure(text="(no tileset loaded)")
            if hasattr(self, "tile_flags_editor_placeholder") and self.tile_flags_editor_placeholder.winfo_exists():
                self.tile_flags_editor_placeholder.configure(text="(no tileset loaded)")
                self.tile_flags_editor_placeholder.grid()
            if hasattr(self, "tile_hint_label"):
                self.tile_hint_label.configure(text="Hint: -")
            return
        if self.selected_tile is None:
            self.tile_flags_placeholder.configure(text="(no tile selected)")
            if hasattr(self, "tile_flags_editor_placeholder") and self.tile_flags_editor_placeholder.winfo_exists():
                self.tile_flags_editor_placeholder.configure(text="(no tile selected)")
                self.tile_flags_editor_placeholder.grid()
            if hasattr(self, "tile_hint_label"):
                self.tile_hint_label.configure(text="Hint: -")
            return
        if not self.current_tset.tiles.get(self.selected_tile):
            self.tile_flags_placeholder.configure(text="(no tile selected)")
            if hasattr(self, "tile_flags_editor_placeholder") and self.tile_flags_editor_placeholder.winfo_exists():
                self.tile_flags_editor_placeholder.configure(text="(no tile selected)")
                self.tile_flags_editor_placeholder.grid()
            if hasattr(self, "tile_hint_label"):
                self.tile_hint_label.configure(text="Hint: -")
            return
        self.tile_flags_placeholder.configure(text="")
        if hasattr(self, "tile_flags_editor_placeholder") and self.tile_flags_editor_placeholder.winfo_exists():
            self.tile_flags_editor_placeholder.configure(text="")
            self.tile_flags_editor_placeholder.grid_remove()
        labels = []
        if self.tile_flag_vars:
            for name, (var, _bit) in sorted(self.tile_flag_vars.items(), key=lambda item: item[1][1]):
                if var.get():
                    labels.append(name)
        else:
            tile = self.current_tset.tiles.get(self.selected_tile)
            for name, bit in sorted(self.current_tset.flagbits.items(), key=lambda item: item[1]):
                if tile.flags & (1 << bit):
                    labels.append(name)
        if not labels:
            tk.Label(self.tile_flags_frame, text="None").pack(anchor="w")
        else:
            for name in labels:
                tk.Label(self.tile_flags_frame, text=name).pack(anchor="w")
        if hasattr(self, "tile_hint_label"):
            hint = getattr(self.current_tset.tiles.get(self.selected_tile), "hint", "")
            self.tile_hint_label.configure(text=f"Hint: {hint or '-'}")
        if self.tile_flag_checkbuttons and hasattr(self, "tile_flags_editor"):
            for name, cb in self.tile_flag_checkbuttons.items():
                cb.grid()

    def _tile_editor_changed(self, tile, update_name: bool) -> bool:
        if update_name and tile.name != self.tile_name_var.get().strip():
            return True
        if getattr(tile, "hint", "") != (self.tile_hint_var.get().strip() if hasattr(self, "tile_hint_var") else ""):
            return True
        new_chars = [int(var.get()) for var in self.tile_char_vars]
        if new_chars != tile.chars:
            return True
        if self.tile_color_mode_var.get():
            if tile.color_mode != 1:
                return True
            new_colors = [self._color_index_by_name(var.get()) for var in self.tile_color_vars]
            if new_colors != tile.colors:
                return True
        else:
            if tile.color_mode != 0:
                return True
            new_color = self._color_index_by_name(self.tile_color_vars[0].get())
            if tile.colors[0] != new_color:
                return True
        if update_name:
            if tile.flags != self._flags_from_editor():
                return True
        return False

    def _record_undo(self) -> None:
        if self._is_restoring:
            return
        self._profile_start("undo.snapshot")
        snapshot = {
            "charset": bytes(self.charset_bytes),
            "total_chars": self.total_chars,
            "current_file": self.current_file,
            "current_tset": copy.deepcopy(self.current_tset) if self.current_tset else None,
            "current_tset_path": self.current_tset_path,
            "current_tset_charset": self.current_tset_charset,
            "mode": self.mode_var.get(),
            "bg": self.bg_var.get(),
            "fg": self.fg_var.get(),
            "mc1": self.mc1_var.get(),
            "mc2": self.mc2_var.get(),
            "selected_index": self.selected_index,
            "selected_tile": self.selected_tile,
            "selected_object": self.selected_object,
            "dirty": self.dirty,
            "tset_dirty": self.tset_dirty,
        }
        if self.undo_index < len(self.undo_stack) - 1:
            self.undo_stack = self.undo_stack[: self.undo_index + 1]
        self.undo_stack.append(snapshot)
        self.undo_index = len(self.undo_stack) - 1
        self._profile_end("undo.snapshot")
        self.logger.info("Undo snapshot recorded (index=%s)", self.undo_index)

    def _restore_snapshot(self, snapshot: dict) -> None:
        self._is_restoring = True
        self.charset_bytes = bytearray(snapshot["charset"])
        self.total_chars = snapshot["total_chars"]
        self.current_file = snapshot["current_file"]
        self.current_tset = copy.deepcopy(snapshot["current_tset"]) if snapshot["current_tset"] else None
        self.current_tset_path = snapshot["current_tset_path"]
        self.current_tset_charset = snapshot["current_tset_charset"]
        self.mode_var.set(snapshot["mode"])
        self.bg_var.set(snapshot["bg"])
        self.fg_var.set(snapshot["fg"])
        self.mc1_var.set(snapshot["mc1"])
        self.mc2_var.set(snapshot["mc2"])
        self.selected_index = snapshot["selected_index"]
        self.selected_tile = snapshot["selected_tile"]
        self.selected_object = snapshot["selected_object"]
        self.dirty = snapshot["dirty"]
        self.tset_dirty = snapshot["tset_dirty"]
        self.columns = self.charset_columns
        self._init_flag_vars(clear=self.current_tset is None)
        self._draw_grid()
        self.refresh_selected()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        if self.current_tset and self.selected_tile is not None:
            tile = self.current_tset.tiles.get(self.selected_tile)
            if tile:
                self._load_tile_editor(tile)
        self._update_title()
        self._is_restoring = False

    def _reset_history(self) -> None:
        self.undo_stack = []
        self.undo_index = -1
        self._record_undo()

    def undo(self) -> None:
        if self.undo_index <= 0:
            return
        self.undo_index -= 1
        self.logger.info("Undo applied (index=%s)", self.undo_index)
        self._restore_snapshot(self.undo_stack[self.undo_index])

    def redo(self) -> None:
        if self.undo_index >= len(self.undo_stack) - 1:
            return
        self.undo_index += 1
        self.logger.info("Redo applied (index=%s)", self.undo_index)
        self._restore_snapshot(self.undo_stack[self.undo_index])

    def _open_flags_modal(self) -> None:
        if not self.current_tset or self.selected_tile is None:
            messagebox.showwarning("Edit Flags", "No tile selected.")
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if not tile:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Tile Flags")
        dialog.transient(self.root)
        dialog.update_idletasks()
        dialog.grab_set()
        self.logger.info("Edit flags modal opened for tile %s", tile.tid)

        flag_vars = {}
        for name, bit in sorted(self.current_tset.flagbits.items(), key=lambda item: item[1]):
            current = 0
            if name in self.tile_flag_vars:
                current = self.tile_flag_vars[name][0].get()
            else:
                current = 1 if tile.flags & (1 << bit) else 0
            var = tk.IntVar(value=current)
            cb = tk.Checkbutton(dialog, text=name, variable=var)
            cb.pack(anchor="w", padx=10, pady=2)
            flag_vars[name] = (var, bit)

        actions = tk.Frame(dialog, padx=10, pady=10)
        actions.pack(fill=tk.X)
        tk.Button(actions, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(6, 0))

        def _apply():
            for name, (var, bit) in flag_vars.items():
                if name in self.tile_flag_vars:
                    self.tile_flag_vars[name][0].set(var.get())
            self._update_tile_flags_display()
            self.logger.info("Edit flags modal applied for tile %s", tile.tid)
            dialog.destroy()

        tk.Button(actions, text="OK", command=_apply).pack(side=tk.RIGHT)

    def _color_token_from_index(self, index: int) -> str:
        name = self._color_name_by_index(index)
        return name.upper().replace(" ", "_")

    def _serialize_tset(self) -> str:
        ts = self.current_tset
        if ts is None:
            return ""
        header = (
            f'TSET name="{ts.name}" tileSize={ts.tile_w}x{ts.tile_h} '
            f"bgColor={self._color_token_from_index(ts.bg_color)} "
            f"mc1Color={self._color_token_from_index(ts.mc1_color)} "
            f"mc2Color={self._color_token_from_index(ts.mc2_color)} "
            f"charset={ts.charset_path}"
        )
        lines = [header, "", "CHARMAP"]
        entries = {}
        for ch, tid in ts.charmap_tiles.items():
            tile = ts.tiles.get(tid)
            if tile:
                entries[ch] = tile.name
        for ch, obj in ts.object_stamps.items():
            entries[ch] = obj["name"]
        for ch in sorted(entries.keys(), key=lambda c: ord(c)):
            lines.append(f"{ch} {entries[ch]}")
        lines.append("END")
        if ts.objects:
            lines.append("")
            lines.append("OBJECTS")
            for name in sorted(ts.objects.keys()):
                obj = ts.objects[name]
                tiles = ",".join(obj.tiles)
                lines.append(f"{obj.name} size={obj.w}x{obj.h} tiles={tiles}")
            lines.append("END")
        lines.append("")
        lines.append("TILES")
        flag_names = sorted(ts.flagbits.items(), key=lambda item: item[1])
        for tid in sorted(ts.tiles.keys()):
            tile = ts.tiles[tid]
            chars = ",".join(f"0x{c:02X}" for c in tile.chars)
            parts = [f"{tile.name} chars={chars}"]
            if tile.color_mode == 1:
                colors = ",".join(self._color_token_from_index(c) for c in tile.colors)
                parts.append(f"colors={colors}")
            else:
                parts.append(f"color={self._color_token_from_index(tile.colors[0])}")
            if getattr(tile, "hint", ""):
                parts.append(f"hint={tile.hint}")
            flags = []
            for name, bit in flag_names:
                if tile.flags & (1 << bit):
                    flags.append(name)
            if flags:
                parts.append("flags=" + "|".join(flags))
            lines.append(" ".join(parts))
        lines.append("END")
        lines.append("")
        lines.append("END")
        return "\n".join(lines) + "\n"
    def _bind_events(self) -> None:
        for canvas in self.grid_canvases:
            canvas.bind("<ButtonPress-1>", self._on_grid_press)
            canvas.bind("<B1-Motion>", self._on_grid_drag)
            canvas.bind("<ButtonRelease-1>", self._on_grid_release)
        self.charset_tabs.bind("<<NotebookTabChanged>>", self._on_charset_tab_change)
        self.preview_canvas.bind("<Button-1>", self._on_preview_click)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)
        self.tiles_canvas.bind("<Button-1>", self._on_tile_click)
        self.tiles_canvas.bind("<Button-3>", self._on_tiles_context_menu)
        self.objects_canvas.bind("<Button-1>", self._on_object_click)
        self.tiles_canvas.bind("<MouseWheel>", self._on_tiles_wheel)
        self.objects_canvas.bind("<MouseWheel>", self._on_objects_wheel)
        self.root.bind_all("<Control-z>", lambda _e: self.undo())
        self.root.bind_all("<Control-y>", lambda _e: self.redo())
        self.root.bind_all("<Control-Shift-Z>", lambda _e: self.redo())
        self.root.bind_all("<Control-c>", lambda _e: self.copy_selection())
        self.root.bind_all("<Control-v>", lambda _e: self.paste_selection())
        self.root.bind_all("<Control-x>", lambda _e: self.cut_selection())

    def _draw_preview_grid(self) -> None:
        self.preview_canvas.delete("grid")
        size = 8 * self.preview_scale
        step = self.preview_scale
        for i in range(0, size + 1, step):
            self.preview_canvas.create_line(0, i, size, i, fill="#222222", tags="grid")
            self.preview_canvas.create_line(i, 0, i, size, fill="#222222", tags="grid")

    def _on_tiles_wheel(self, event: tk.Event) -> None:
        delta = int(-1 * (event.delta / 120))
        if delta != 0:
            self.tiles_canvas.yview_scroll(delta, "units")

    def _on_objects_wheel(self, event: tk.Event) -> None:
        delta = int(-1 * (event.delta / 120))
        if delta != 0:
            self.objects_canvas.yview_scroll(delta, "units")

    def _color_hex(self, name: str) -> str:
        for color_name, hex_value in C64_COLORS:
            if color_name == name:
                return hex_value
        return "#000000"

    def _color_hex_by_index(self, index: int) -> str:
        if 0 <= index < len(C64_COLORS):
            return C64_COLORS[index][1]
        return "#000000"

    def _color_name_by_index(self, index: int) -> str:
        if 0 <= index < len(C64_COLORS):
            return C64_COLORS[index][0]
        return "Black"

    def _color_index_by_name(self, name: str) -> int:
        for idx, (color_name, _) in enumerate(C64_COLORS):
            if color_name == name:
                return idx
        return 0

    def _current_colors(self) -> dict:
        return {
            "bg": self._color_hex(self.bg_var.get()),
            "fg": self._color_hex(self.fg_var.get()),
            "mc1": self._color_hex(self.mc1_var.get()),
            "mc2": self._color_hex(self.mc2_var.get()),
        }

    def load_charset(self, path: str, keep_tset: bool = False, add_recent: bool = True) -> None:
        self.logger.info("Loading charset from %s", path)
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            self.logger.error("Failed to load charset: %s", exc)
            messagebox.showerror("Open failed", str(exc))
            return
        self.load_charset_bytes(
            data,
            path_hint=path,
            keep_tset=keep_tset,
            add_recent=add_recent,
            mark_dirty=False,
        )

    def load_charset_bytes(
        self,
        data: bytes,
        path_hint: str | None = None,
        keep_tset: bool = False,
        add_recent: bool = False,
        mark_dirty: bool = True,
        reset_history: bool = True,
    ) -> None:
        self.logger.info(
            "Loading charset bytes (hint=%s, keep_tset=%s, mark_dirty=%s)",
            path_hint,
            keep_tset,
            mark_dirty,
        )
        if len(data) % 8 != 0:
            messagebox.showerror("Open failed", "Charset size must be a multiple of 8 bytes.")
            return

        min_size = self.page_chars * 8
        if len(data) <= min_size:
            data = data + b"\x00" * (min_size - len(data))
            self.total_chars = self.page_chars
        else:
            needed = self.page_chars * 2 * 8
            if len(data) < needed:
                data = data + b"\x00" * (needed - len(data))
            self.total_chars = self.page_chars * 2
        self.charset_bytes = bytearray(data)
        self.current_file = path_hint
        self.selected_index = 0
        if add_recent and path_hint:
            self._add_recent(path_hint)
        if not keep_tset:
            self.current_tset = None
            self.current_tset_path = None
            self.current_tset_charset = None
            self._init_flag_vars(clear=True)
        self.dirty = mark_dirty
        self._update_title()
        self._draw_grid()
        self.refresh_selected()
        if not keep_tset:
            self._clear_tiles_objects()
        if reset_history:
            self._reset_history()
        self.logger.info("Charset loaded bytes=%s total_chars=%s", len(self.charset_bytes), self.total_chars)

    def load_tset(self, path: str, add_recent: bool = True) -> None:
        if parse_tset is None:
            messagebox.showerror("Open failed", "tset_parser is not available.")
            return
        self.logger.info("Loading TSET from %s", path)
        try:
            tset = parse_tset(path)
        except TilesetParseError as exc:
            self.logger.error("Failed to parse TSET: %s", exc)
            messagebox.showerror(
                "Open failed",
                f"{exc.path}:{exc.line}:{exc.col} {exc.message}",
            )
            return
        self.current_tset = tset
        self.current_tset_path = path
        self.current_tset_charset = self._resolve_tset_charset(path, tset.charset_path)
        self.tset_dirty = False
        self._init_flag_vars(clear=False)
        if add_recent:
            self._add_recent(path)
        self.mode_var.set("multicolor")
        self.bg_var.set(self._color_name_by_index(tset.bg_color))
        self.mc1_var.set(self._color_name_by_index(tset.mc1_color))
        self.mc2_var.set(self._color_name_by_index(tset.mc2_color))
        fg_index = self._guess_fg_color_from_tset(tset)
        fg_index = self._pick_contrasting_fg(fg_index, tset.bg_color, tset.mc1_color, tset.mc2_color)
        self.fg_var.set(self._color_name_by_index(fg_index))
        if self.current_tset_charset and os.path.exists(self.current_tset_charset):
            self.load_charset(self.current_tset_charset, keep_tset=True, add_recent=False)
        self.selected_tile = min(self.current_tset.tiles.keys()) if self.current_tset.tiles else None
        self._update_tile_flags_display()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._update_title()
        self._reset_history()
        self.logger.info("TSET loaded tiles=%s objects=%s", len(self.current_tset.tiles), len(self.current_tset.objects))

    def load_tset_text(
        self,
        text: str,
        source_path: str | None = None,
        charset_hint: str | None = None,
    ) -> None:
        if parse_tset_text is None:
            messagebox.showerror("Open failed", "tset_parser is not available.")
            return
        self.logger.info("Loading TSET text (source=%s)", source_path)
        try:
            tset = parse_tset_text(text, path=source_path or "<memory>", validate_charset=False)
        except TilesetParseError as exc:
            self.logger.error("Failed to parse TSET text: %s", exc)
            messagebox.showerror(
                "Open failed",
                f"{exc.path}:{exc.line}:{exc.col} {exc.message}",
            )
            return
        self.current_tset = tset
        self.current_tset_path = source_path
        self.current_tset_charset = charset_hint or tset.charset_path
        self.tset_dirty = True
        self._init_flag_vars(clear=False)
        self.mode_var.set("multicolor")
        self.bg_var.set(self._color_name_by_index(tset.bg_color))
        self.mc1_var.set(self._color_name_by_index(tset.mc1_color))
        self.mc2_var.set(self._color_name_by_index(tset.mc2_color))
        fg_index = self._guess_fg_color_from_tset(tset)
        fg_index = self._pick_contrasting_fg(fg_index, tset.bg_color, tset.mc1_color, tset.mc2_color)
        self.fg_var.set(self._color_name_by_index(fg_index))
        self.selected_tile = min(self.current_tset.tiles.keys()) if self.current_tset.tiles else None
        self._update_tile_flags_display()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._update_title()
        self._reset_history()
        self.logger.info("TSET text loaded tiles=%s objects=%s", len(self.current_tset.tiles), len(self.current_tset.objects))

    def _resolve_tset_charset(self, tset_path: str, charset_path: str) -> str:
        if not charset_path:
            return ""
        if os.path.isabs(charset_path):
            return charset_path
        base = os.path.dirname(tset_path)
        candidate = os.path.join(base, charset_path)
        if os.path.isfile(candidate):
            return candidate
        candidate = os.path.join(base, "..", charset_path)
        if os.path.isfile(candidate):
            return candidate
        return os.path.join(base, charset_path)

    def _guess_fg_color_from_tset(self, tset) -> int:
        counts = [0] * 16
        for tile in tset.tiles.values():
            if tile.color_mode == 1:
                colors = tile.colors
            else:
                colors = [tile.colors[0]]
            for color in colors:
                if 0 <= color < len(counts):
                    counts[color] += 1
        bg = tset.bg_color if 0 <= tset.bg_color < len(counts) else None
        for idx in range(len(counts)):
            if idx == bg:
                counts[idx] = 0
        if max(counts) == 0:
            return 1
        return max(range(len(counts)), key=lambda idx: counts[idx])

    def _pick_contrasting_fg(self, fg_index: int, bg_index: int, mc1_index: int, mc2_index: int) -> int:
        avoid = {bg_index, mc1_index, mc2_index}
        if fg_index not in avoid:
            return fg_index
        for candidate in (1, 15, 7, 14, 13, 10):
            if candidate not in avoid:
                return candidate
        return fg_index

    def _add_recent(self, path: str) -> None:
        normalized = os.path.abspath(path)
        self.recent_files = [p for p in self.recent_files if p != normalized]
        self.recent_files.insert(0, normalized)
        self.recent_files = self.recent_files[:10]
        self._refresh_recent_menu()
        self._save_recent()
        self.logger.info("Recent updated: %s", normalized)

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.delete(0, tk.END)
        if not self.recent_files:
            self.recent_menu.add_command(label="(empty)", state=tk.DISABLED)
            return
        for path in self.recent_files:
            self.recent_menu.add_command(
                label=path,
                command=lambda p=path: self._open_recent(p),
            )

    def _open_recent(self, path: str) -> None:
        if not os.path.exists(path):
            messagebox.showwarning("Open failed", f"File not found:\n{path}")
            self.recent_files = [p for p in self.recent_files if p != path]
            self._refresh_recent_menu()
            self._save_recent()
            return
        self.logger.info("Open recent: %s", path)
        if not self._confirm_discard_changes():
            return
        self._add_recent(path)
        if path.lower().endswith(".tset"):
            self.load_tset(path, add_recent=False)
        else:
            keep_tset = self.current_tset is not None
            self.load_charset(path, keep_tset=keep_tset, add_recent=False)

    def _load_recent(self) -> None:
        try:
            with open(self.recent_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._refresh_recent_menu()
            return
        if isinstance(data, list):
            self.recent_files = [str(p) for p in data if isinstance(p, str)]
        self._refresh_recent_menu()

    def _save_recent(self) -> None:
        try:
            os.makedirs(self.recent_dir, exist_ok=True)
            with open(self.recent_path, "w", encoding="utf-8") as handle:
                json.dump(self.recent_files, handle, indent=2)
        except OSError:
            self.logger.warning("Failed to save recent list", exc_info=True)
            pass

    def _mark_dirty(self) -> None:
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _clear_dirty(self) -> None:
        if self.dirty:
            self.dirty = False
            self._update_title()

    def _mark_tset_dirty(self) -> None:
        if not self.tset_dirty:
            self.tset_dirty = True
            self._update_title()
            self._update_tiles_status()

    def _clear_tset_dirty(self) -> None:
        if self.tset_dirty:
            self.tset_dirty = False
            self._update_title()
            self._update_tiles_status()

    def _confirm_discard_changes(self) -> bool:
        if not (self.dirty or self.tset_dirty):
            return True
        if self.dirty and self.tset_dirty:
            message = "Save changes to charset and tileset before continuing?"
        elif self.dirty:
            message = "Save changes to charset before continuing?"
        else:
            message = "Save changes to tileset before continuing?"
        result = messagebox.askyesnocancel("Unsaved changes", message)
        if result is None:
            return False
        if result:
            if self.dirty:
                self.save_file()
            if self.tset_dirty:
                self.save_tset()
            return not (self.dirty or self.tset_dirty)
        return True

    def _on_close(self) -> None:
        if self._confirm_discard_changes():
            self._close_profile_log()
            self.root.destroy()

    def _compute_columns(self, count: int) -> int:
        return self.charset_columns

    def _draw_grid(self) -> None:
        self.char_images = [[], []]
        self.char_image_items = [[], []]

        if self.total_chars <= self.page_chars:
            if self.has_second_tab:
                self.charset_tabs.forget(self.grid_frames[1])
                self.has_second_tab = False
            self.charset_tabs.tab(0, text="Charset")
            self.charset_tabs.select(0)
        else:
            if not self.has_second_tab:
                self.charset_tabs.add(self.grid_frames[1], text="Charset 1")
                self.has_second_tab = True
            self.charset_tabs.tab(0, text="Charset 0")
            self.charset_tabs.tab(1, text="Charset 1")

        cell_size = 8 * self.grid_scale
        rows = 16
        width = self.columns * cell_size
        height = rows * cell_size

        for page in range(2):
            canvas = self.grid_canvases[page]
            canvas.delete("all")
            if page == 1 and self.total_chars <= self.page_chars:
                canvas.configure(scrollregion=(0, 0, width, height))
                continue
            start_index = page * self.page_chars
            end_index = start_index + self.page_chars
            for index in range(start_index, end_index):
                local_index = index - start_index
                col = local_index % self.columns
                row = local_index // self.columns
                x = col * cell_size
                y = row * cell_size
                image = self._render_char_image(index, self.grid_scale)
                self.char_images[page].append(image)
                item = canvas.create_image(x, y, anchor="nw", image=image)
                self.char_image_items[page].append(item)
                canvas.create_rectangle(
                    x, y, x + cell_size, y + cell_size, outline="#333333"
                )
            selection_rect = canvas.create_rectangle(
                0, 0, cell_size, cell_size, outline="#FFFF00", width=2
            )
            canvas.configure(scrollregion=(0, 0, width, height))
            self.selection_rects[page] = selection_rect
            multi_rect = canvas.create_rectangle(
                0, 0, cell_size, cell_size, outline="#00FFFF", width=2
            )
            canvas.itemconfigure(multi_rect, state="hidden")
            self.multi_select_rects[page] = multi_rect
            for rect in self.tile_selection_rects[page]:
                if rect:
                    canvas.delete(rect)
            for i in range(len(self.tile_selection_rects[page])):
                self.tile_selection_rects[page][i] = canvas.create_rectangle(
                    0,
                    0,
                    cell_size,
                    cell_size,
                    outline="#00FFAA",
                    width=2,
                )
                canvas.itemconfigure(self.tile_selection_rects[page][i], state="hidden")

    def _render_char_image(self, index: int, scale: int, fg_override: str | None = None) -> tk.PhotoImage:
        char_bytes = self._char_bytes(index)
        colors = self._current_colors()
        if fg_override:
            colors = dict(colors)
            colors["fg"] = fg_override
        mode = self.mode_var.get()
        rows = self._char_to_rows(char_bytes, mode, colors)
        width = 8 * scale
        height = 8 * scale
        image = tk.PhotoImage(width=width, height=height)
        for y, row in enumerate(rows):
            expanded_row = []
            for color in row:
                expanded_row.extend([color] * scale)
            row_data = "{" + " ".join(expanded_row) + "}"
            for sy in range(scale):
                image.put(row_data, to=(0, y * scale + sy))
        return image

    def _char_bytes(self, index: int) -> bytes:
        start = index * 8
        end = start + 8
        if end > len(self.charset_bytes):
            return b"\x00" * 8
        return self.charset_bytes[start:end]

    def _char_to_rows(self, char_bytes: bytes, mode: str, colors: dict) -> list:
        rows = []
        if mode == "multicolor":
            palette = [colors["bg"], colors["mc1"], colors["mc2"], colors["fg"]]
            for row_index in range(8):
                byte = char_bytes[row_index]
                row = []
                for shift in (6, 4, 2, 0):
                    value = (byte >> shift) & 0x03
                    color = palette[value]
                    row.extend([color, color])
                rows.append(row)
        else:
            for row_index in range(8):
                byte = char_bytes[row_index]
                row = []
                for bit in range(7, -1, -1):
                    color = colors["fg"] if (byte >> bit) & 0x01 else colors["bg"]
                    row.append(color)
                rows.append(row)
        return rows

    def refresh_all(self) -> None:
        if not self.charset_bytes:
            return
        self._update_color_states()
        self._draw_grid()
        self.refresh_selected()
        self._draw_tiles_grid()
        self._draw_objects_grid()

    def _refresh_selected_view(self) -> None:
        if not self.charset_bytes:
            self.status_label.configure(text="No charset loaded.")
            return
        if self.selected_index >= self.total_chars:
            self.selected_index = 0
        fg_override = None
        if self.paint_fg_override_index is not None:
            fg_override = self._color_hex_by_index(self.paint_fg_override_index)
        image = self._render_char_image(self.selected_index, self.preview_scale, fg_override=fg_override)
        self.preview_image = image
        self.preview_canvas.itemconfigure(self.preview_image_id, image=image)
        self._update_selection_rect()
        self._update_tile_preview()
        dirty_marker = " *" if self.dirty else ""
        self.status_label.configure(
            text=f"Char {self.selected_index:03d} (0x{self.selected_index:02X}){dirty_marker}"
        )

    def _schedule_refresh_selected_view(self) -> None:
        if self._refresh_selected_after_id is not None:
            return
        self._refresh_selected_after_id = self.root.after(
            self._tile_update_delay_ms, self._run_refresh_selected_view
        )

    def _run_refresh_selected_view(self) -> None:
        self._refresh_selected_after_id = None
        self._refresh_selected_view()

    def _flush_refresh_selected_view(self) -> None:
        if self._refresh_selected_after_id is not None:
            self.root.after_cancel(self._refresh_selected_after_id)
            self._refresh_selected_after_id = None
        self._refresh_selected_view()

    def refresh_selected(self) -> None:
        if not self.charset_bytes:
            self.status_label.configure(text="No charset loaded.")
            return
        if self.selected_index >= self.total_chars:
            self.selected_index = 0
        fg_override = None
        if self.paint_fg_override_index is not None:
            fg_override = self._color_hex_by_index(self.paint_fg_override_index)
        image = self._render_char_image(self.selected_index, self.preview_scale, fg_override=fg_override)
        self.preview_image = image
        self.preview_canvas.itemconfigure(self.preview_image_id, image=image)
        self._update_selection_rect()
        if self.tile_entries:
            self._schedule_tiles_redraw()
            if self.current_tset and self.current_tset.objects:
                self._schedule_objects_redraw()
        self._update_tile_preview()
        dirty_marker = " *" if self.dirty else ""
        self.status_label.configure(
            text=f"Char {self.selected_index:03d} (0x{self.selected_index:02X}){dirty_marker}"
        )

    def _schedule_tiles_redraw(self) -> None:
        if self._pending_tiles_redraw:
            return
        self._pending_tiles_redraw = True
        self.root.after_idle(self._run_tiles_redraw)

    def _run_tiles_redraw(self) -> None:
        self._pending_tiles_redraw = False
        self._profile_start("tiles.redraw")
        self._draw_tiles_grid()
        self._profile_end("tiles.redraw")

    def _schedule_objects_redraw(self) -> None:
        if self._pending_objects_redraw:
            return
        self._pending_objects_redraw = True
        self.root.after_idle(self._run_objects_redraw)

    def _run_objects_redraw(self) -> None:
        self._pending_objects_redraw = False
        self._profile_start("objects.redraw")
        self._draw_objects_grid()
        self._profile_end("objects.redraw")

    def _schedule_objects_redraw_throttled(self) -> None:
        if self._objects_redraw_after_id is not None:
            return
        self._objects_redraw_after_id = self.root.after(
            self._tile_update_delay_ms, self._run_objects_redraw_throttled
        )

    def _run_objects_redraw_throttled(self) -> None:
        self._objects_redraw_after_id = None
        self._run_objects_redraw()

    def _queue_tile_update_for_char(self, index: int) -> None:
        if not self.current_tset:
            return
        tile_ids = self.char_to_tiles.get(index)
        if not tile_ids:
            return
        self._pending_tile_update_ids.update(tile_ids)
        if self._tile_update_after_id is not None:
            return
        self._tile_update_after_id = self.root.after(
            self._tile_update_delay_ms, self._flush_tile_updates
        )

    def _flush_tile_updates(self) -> None:
        self._tile_update_after_id = None
        if not self._pending_tile_update_ids:
            return
        tile_ids = list(self._pending_tile_update_ids)
        self._pending_tile_update_ids.clear()
        self._profile_start("tiles.incremental")
        for tid in tile_ids:
            self._update_tile_image(tid)
        self._profile_end("tiles.incremental")

    def _update_tile_image(self, tile_id: int) -> None:
        if not self.current_tset:
            return
        entry = self.tile_entry_by_id.get(tile_id)
        if not entry:
            return
        tile = self.current_tset.tiles.get(tile_id)
        if not tile:
            return
        image = self._render_tile_image(tile, self.tile_scale)
        image_index = entry.get("tile_index")
        if image_index is not None and 0 <= image_index < len(self.tile_images):
            self.tile_images[image_index] = image
        image_id = entry.get("image_id")
        if image_id is not None:
            self.tiles_canvas.itemconfigure(image_id, image=image)

    def _char_used_in_tiles(self, index: int) -> bool:
        if not self.current_tset:
            return False
        for tile in self.current_tset.tiles.values():
            if index in tile.chars:
                return True
        return False

    def _update_selection_rect(self) -> None:
        cell_size = 8 * self.grid_scale
        page = self.selected_index // self.page_chars
        local_index = self.selected_index % self.page_chars
        col = local_index % self.columns
        row = local_index // self.columns
        x0 = col * cell_size
        y0 = row * cell_size
        x1 = x0 + cell_size
        y1 = y0 + cell_size
        canvas = self.grid_canvases[page]
        selection_rect = self.selection_rects[page]
        if selection_rect is None:
            return
        canvas.coords(selection_rect, x0, y0, x1, y1)
        self._update_tile_highlights()
        canvas.tag_raise(selection_rect)

    def _grid_cell_from_event(self, event: tk.Event) -> tuple[int, int, int] | None:
        if not self.charset_bytes:
            return None
        canvas = event.widget
        page = 0 if canvas == self.grid_canvases[0] else 1
        if page == 1 and self.total_chars <= self.page_chars:
            return None
        x = int(canvas.canvasx(event.x))
        y = int(canvas.canvasy(event.y))
        cell_size = 8 * self.grid_scale
        col = x // cell_size
        row = y // cell_size
        if not (0 <= col < self.columns and 0 <= row < 16):
            return None
        index = row * self.columns + col
        if 0 <= index < self.page_chars:
            return page, col, row
        return None

    def _on_grid_press(self, event: tk.Event) -> None:
        cell = self._grid_cell_from_event(event)
        if not cell:
            return
        page, col, row = cell
        self.selection_mode = "select"
        self.selection_anchor = (page, col, row)
        self.selection_dragged = False
        self.selection_range = (page, col, row, col, row)
        self._update_multi_selection_rect()

    def _on_grid_drag(self, event: tk.Event) -> None:
        cell = self._grid_cell_from_event(event)
        if not cell or not self.selection_mode:
            return
        page, col, row = cell
        if self.selection_mode == "select":
            start_page, start_col, start_row = self.selection_anchor
            if start_page != page:
                return
            if (start_col, start_row) != (col, row):
                self.selection_dragged = True
            self.selection_range = (
                page,
                min(start_col, col),
                min(start_row, row),
                max(start_col, col),
                max(start_row, row),
            )
            self._update_multi_selection_rect()

    def _on_grid_release(self, event: tk.Event) -> None:
        cell = self._grid_cell_from_event(event)
        if not cell:
            return
        page, col, row = cell
        if self.selection_mode == "select" and self.selection_range:
            page, start_col, start_row, end_col, end_row = self.selection_range
            if not self.selection_dragged and self.selection_anchor:
                page, start_col, start_row = self.selection_anchor
                end_col, end_row = start_col, start_row
                self.selection_range = (page, start_col, start_row, end_col, end_row)
            if start_col == end_col and start_row == end_row:
                self.selected_index = page * self.page_chars + start_row * self.columns + start_col
                self.selection_indices = [self.selected_index]
                self._update_multi_selection_rect()
                self.logger.info("Charset selection set to %s", self.selected_index)
                self.paint_fg_override_index = None
                self.paint_color_var.set("fg")
                self._update_paint_swatch_colors()
                self.refresh_selected()
            else:
                self.selected_index = page * self.page_chars + start_row * self.columns + start_col
                self._update_multi_selection_indices()
                self._update_multi_selection_rect()
                self.paint_fg_override_index = None
                self.paint_color_var.set("fg")
                self._update_paint_swatch_colors()
                self.refresh_selected()
        self.selection_mode = None

    def _update_multi_selection_indices(self) -> None:
        if not self.selection_range:
            self.selection_indices = []
            return
        page, start_col, start_row, end_col, end_row = self.selection_range
        indices = []
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                indices.append(page * self.page_chars + row * self.columns + col)
        self.selection_indices = indices

    def _update_multi_selection_rect(self) -> None:
        for page, rect in enumerate(self.multi_select_rects):
            if rect:
                self.grid_canvases[page].itemconfigure(rect, state="hidden")
        if not self.selection_range:
            return
        page, start_col, start_row, end_col, end_row = self.selection_range
        cell_size = 8 * self.grid_scale
        x0 = start_col * cell_size
        y0 = start_row * cell_size
        x1 = (end_col + 1) * cell_size
        y1 = (end_row + 1) * cell_size
        rect = self.multi_select_rects[page]
        if rect is None:
            return
        canvas = self.grid_canvases[page]
        canvas.coords(rect, x0, y0, x1, y1)
        canvas.itemconfigure(rect, state="normal")
        canvas.tag_raise(rect)

    def _on_preview_click(self, event: tk.Event) -> None:
        if not self.charset_bytes:
            return
        self._profile_reset_stroke()
        self._undo_pending = True
        self._stroke_logged = False
        row, col = self._preview_to_cell(event.x, event.y)
        if row is None or col is None:
            return
        current = self._get_pixel_value(self.selected_index, row, col)
        paint_value = self._paint_value_for_color(self.paint_color_var.get(), current=current)
        if paint_value is None:
            if self.mode_var.get() == "multicolor":
                self.paint_value = (current + 1) % 4
            else:
                self.paint_value = 0 if current else 1
        else:
            self.paint_value = paint_value
        self._apply_paint(row, col)

    def _on_preview_drag(self, event: tk.Event) -> None:
        if not self.charset_bytes or self.paint_value is None:
            return
        row, col = self._preview_to_cell(event.x, event.y)
        if row is None or col is None:
            return
        self._apply_paint(row, col)

    def _on_preview_release(self, event: tk.Event) -> None:
        self.paint_value = None
        self._undo_pending = False
        self._flush_refresh_selected_view()
        if self.current_tset and self.current_tset.objects:
            self._schedule_objects_redraw()
        self._profile_log_stroke()

    def _preview_to_cell(self, x: int, y: int) -> tuple[int | None, int | None]:
        size = 8 * self.preview_scale
        if not (0 <= x < size and 0 <= y < size):
            return None, None
        col = x // self.preview_scale
        row = y // self.preview_scale
        if 0 <= row < 8 and 0 <= col < 8:
            return row, col
        return None, None

    def _get_pixel_value(self, index: int, row: int, col: int) -> int:
        start = index * 8 + row
        byte = self.charset_bytes[start]
        if self.mode_var.get() == "multicolor":
            pair = col // 2
            shift = (3 - pair) * 2
            return (byte >> shift) & 0x03
        bit = 7 - col
        return (byte >> bit) & 0x01

    def _set_pixel_value(self, index: int, row: int, col: int, value: int) -> None:
        self._profile_start("paint.set_pixel")
        start = index * 8 + row
        byte = self.charset_bytes[start]
        original = byte
        if self.mode_var.get() == "multicolor":
            pair = col // 2
            shift = (3 - pair) * 2
            mask = 0x03 << shift
            byte = (byte & ~mask) | ((value & 0x03) << shift)
        else:
            bit = 7 - col
            mask = 1 << bit
            if value:
                byte |= mask
            else:
                byte &= ~mask
        self.charset_bytes[start] = byte
        if byte != original:
            if self._undo_pending:
                self._record_undo()
                self._undo_pending = False
                if not self._stroke_logged:
                    self.logger.info("Char edit start index=%s mode=%s", index, self.mode_var.get())
                    self._stroke_logged = True
            self._mark_dirty()
        self._profile_end("paint.set_pixel")

    def _apply_paint(self, row: int, col: int) -> None:
        value = self.paint_value
        if value is None:
            return
        self._profile_start("paint.apply")
        self._set_pixel_value(self.selected_index, row, col, value)
        self._profile_start("paint.char_update")
        self._update_char_image(self.selected_index)
        self._profile_end("paint.char_update")
        if self._char_used_in_tiles(self.selected_index):
            self._queue_tile_update_for_char(self.selected_index)
        self._profile_start("paint.refresh_selected")
        self._schedule_refresh_selected_view()
        self._profile_end("paint.refresh_selected")
        self._profile_end("paint.apply")

    def _update_char_image(self, index: int) -> None:
        self._profile_start("char.render")
        page = index // self.page_chars
        local = index % self.page_chars
        if page >= len(self.char_images):
            self._profile_end("char.render")
            return
        image = self._render_char_image(index, self.grid_scale)
        if local >= len(self.char_images[page]):
            self._profile_end("char.render")
            return
        self.char_images[page][local] = image
        self.grid_canvases[page].itemconfigure(self.char_image_items[page][local], image=image)
        self._profile_end("char.render")

    def _on_tile_click(self, event: tk.Event) -> None:
        if not self.tile_entries:
            return
        x = int(self.tiles_canvas.canvasx(event.x))
        y = int(self.tiles_canvas.canvasy(event.y))
        for entry in self.tile_entries:
            x0, y0, x1, y1 = entry["bbox"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.selected_tile = entry["id"]
                self.logger.info("Tile selected id=%s name=%s", entry["id"], entry["name"])
                self._update_tile_selection(entry)
                if self.current_tset and entry["id"] in self.current_tset.tiles:
                    self._load_tile_editor(self.current_tset.tiles[entry["id"]])
                return

    def _on_tiles_context_menu(self, event: tk.Event) -> None:
        if not hasattr(self, "tiles_context_menu"):
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="New Tile", command=self._new_tile)
            menu.add_command(label="Duplicate Tile", command=self._duplicate_tile)
            menu.add_command(label="Delete Tile", command=self._delete_tile)
            self.tiles_context_menu = menu
        try:
            self.tiles_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.tiles_context_menu.grab_release()

    def _on_object_click(self, event: tk.Event) -> None:
        if not self.object_entries:
            return
        x = int(self.objects_canvas.canvasx(event.x))
        y = int(self.objects_canvas.canvasy(event.y))
        for entry in self.object_entries:
            x0, y0, x1, y1 = entry["bbox"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.selected_object = entry["name"]
                self.logger.info("Object selected name=%s", entry["name"])
                self._update_object_selection(entry)
                return

    def _on_color_change(self) -> None:
        self.logger.info(
            "Palette changed bg=%s fg=%s mc1=%s mc2=%s mode=%s",
            self.bg_var.get(),
            self.fg_var.get(),
            self.mc1_var.get(),
            self.mc2_var.get(),
            self.mode_var.get(),
        )
        self.refresh_all()

    def copy_selection(self) -> None:
        if not self.charset_bytes or not self.selection_range:
            return
        page, start_col, start_row, end_col, end_row = self.selection_range
        width = end_col - start_col + 1
        height = end_row - start_row + 1
        data = []
        indices = []
        for row in range(height):
            row_data = []
            row_indices = []
            for col in range(width):
                idx = page * self.page_chars + (start_row + row) * self.columns + (start_col + col)
                row_data.append(bytes(self._char_bytes(idx)))
                row_indices.append(idx)
            data.append(row_data)
            indices.append(row_indices)
        self.copy_buffer = {"width": width, "height": height, "data": data, "indices": indices, "cut": False}
        self.logger.info("Selection copied size=%sx%s", width, height)

    def paste_selection(self) -> None:
        if not self.copy_buffer or not self.charset_bytes:
            return
        page = self.selected_index // self.page_chars
        local = self.selected_index % self.page_chars
        start_col = local % self.columns
        start_row = local // self.columns
        width = self.copy_buffer["width"]
        height = self.copy_buffer["height"]
        if start_col + width > self.columns or start_row + height > 16:
            messagebox.showwarning("Paste", "Paste would exceed charset bounds.")
            return
        mapping = {}
        if self.current_tset and self.copy_buffer.get("cut"):
            for row in range(height):
                for col in range(width):
                    old_idx = self.copy_buffer["indices"][row][col]
                    new_idx = page * self.page_chars + (start_row + row) * self.columns + (start_col + col)
                    mapping[old_idx] = new_idx
            refs = []
            for tile in self.current_tset.tiles.values():
                if any(c in mapping for c in tile.chars):
                    refs.append(tile)
            if refs and messagebox.askyesno(
                "Update tiles",
                f"Cut chars are used in {len(refs)} tile(s). Update those tiles to the new locations?",
            ):
                for tile in refs:
                    tile.chars = [mapping.get(c, c) for c in tile.chars]
                self._mark_tset_dirty()
                self.logger.info("Tiles updated for pasted cut selection")
        self._record_undo()
        for row in range(height):
            for col in range(width):
                idx = page * self.page_chars + (start_row + row) * self.columns + (start_col + col)
                dest = idx * 8
                self.charset_bytes[dest:dest + 8] = self.copy_buffer["data"][row][col]
        self._mark_dirty()
        self._draw_grid()
        self.refresh_selected()
        self.logger.info("Selection pasted at %s,%s", start_col, start_row)
        if self.copy_buffer.get("cut"):
            self.copy_buffer["cut"] = False

    def cut_selection(self) -> None:
        if not self.charset_bytes or not self.selection_range:
            return
        self.copy_selection()
        if self.copy_buffer is not None:
            self.copy_buffer["cut"] = True
        page, start_col, start_row, end_col, end_row = self.selection_range
        width = end_col - start_col + 1
        height = end_row - start_row + 1
        self._record_undo()
        cleared = []
        for row in range(height):
            for col in range(width):
                idx = page * self.page_chars + (start_row + row) * self.columns + (start_col + col)
                self.charset_bytes[idx * 8:idx * 8 + 8] = b"\x00" * 8
                cleared.append(idx)
        if self.current_tset:
            self._mark_tset_dirty()
        self._mark_dirty()
        self._draw_grid()
        self.refresh_selected()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self.logger.info("Selection cut size=%sx%s", width, height)

    def _prompt_char_index(self, title: str) -> int | None:
        if not self.charset_bytes:
            messagebox.showwarning(title, "No charset loaded.")
            return None
        prompt = f"Target index (0-{self.total_chars - 1}):"
        value = simpledialog.askinteger(title, prompt, minvalue=0, maxvalue=self.total_chars - 1)
        if value is None:
            return None
        return int(value)

    def copy_char(self) -> None:
        if not self.charset_bytes:
            messagebox.showwarning("Copy Char", "No charset loaded.")
            return
        target = self._prompt_char_index("Copy Char")
        if target is None or target == self.selected_index:
            return
        if not messagebox.askyesno(
            "Copy Char",
            f"Overwrite char {target:03d} (0x{target:02X})?",
        ):
            return
        self._record_undo()
        src = self.selected_index * 8
        dst = target * 8
        self.charset_bytes[dst:dst + 8] = self.charset_bytes[src:src + 8]
        self._mark_dirty()
        self._draw_grid()
        self.refresh_selected()
        self.logger.info("Char copied from %s to %s", self.selected_index, target)

    def move_char(self) -> None:
        if not self.charset_bytes:
            messagebox.showwarning("Move Char", "No charset loaded.")
            return
        target = self._prompt_char_index("Move Char")
        if target is None or target == self.selected_index:
            return
        if not messagebox.askyesno(
            "Move Char",
            f"Move char {self.selected_index:03d} (0x{self.selected_index:02X}) to "
            f"{target:03d} (0x{target:02X}) and clear source?",
        ):
            return
        self._record_undo()
        src = self.selected_index * 8
        dst = target * 8
        self.charset_bytes[dst:dst + 8] = self.charset_bytes[src:src + 8]
        self.charset_bytes[src:src + 8] = b"\x00" * 8
        if self.current_tset:
            refs = []
            for tile in self.current_tset.tiles.values():
                if self.selected_index in tile.chars:
                    refs.append(tile)
            if refs:
                if messagebox.askyesno(
                    "Update tiles",
                    f"Char {self.selected_index:03d} is used in {len(refs)} tile(s). "
                    "Update those tiles to point at the new location?",
                ):
                    for tile in refs:
                        tile.chars = [target if c == self.selected_index else c for c in tile.chars]
                    self.logger.info("Tiles updated for moved char %s -> %s", self.selected_index, target)
            self._mark_tset_dirty()
        self.selected_index = target
        self._mark_dirty()
        self._draw_grid()
        self.refresh_selected()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self.logger.info("Char moved from %s to %s", src // 8, target)

    def _on_charset_tab_change(self, event: tk.Event) -> None:
        page = self.charset_tabs.index("current")
        if page == 1 and self.total_chars <= self.page_chars:
            return
        self.selected_index = page * self.page_chars + (self.selected_index % self.page_chars)
        self.logger.info("Charset tab switched to %s", page)
        self.refresh_selected()

    def _update_color_states(self) -> None:
        if not hasattr(self, "mc1_option"):
            return
        if self.mode_var.get() == "hires":
            self._set_swatch_enabled(self.mc1_option, False)
            self._set_swatch_enabled(self.mc2_option, False)
        else:
            self._set_swatch_enabled(self.mc1_option, True)
            self._set_swatch_enabled(self.mc2_option, True)
        self._ensure_paint_color_controls()

    def open_charset(self) -> None:
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            title="Open Charset",
            filetypes=[("Charset binary", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.logger.info("Open charset dialog selected %s", path)
            self.generated_assets = None
            keep_tset = self.current_tset is not None
            self.load_charset(path, keep_tset=keep_tset)

    def new_charset(self) -> None:
        if not self._confirm_discard_changes():
            return
        self._create_empty_charset()
        self.logger.info("New charset created")

    def open_tset(self) -> None:
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            title="Open TSET",
            filetypes=[("Tileset", "*.tset"), ("All files", "*.*")],
        )
        if path:
            self.logger.info("Open TSET dialog selected %s", path)
            self.generated_assets = None
            self.load_tset(path)

    def new_tset(self) -> None:
        if not self._confirm_discard_changes():
            return
        if TsetParseResult is None or TileDef is None:
            messagebox.showerror("New TSET", "tset_parser is not available.")
            return
        self._create_empty_tset()
        self.logger.info("New TSET created")

    def open_koala_spec(self) -> None:
        if not self._confirm_discard_changes():
            return
        if tilekit_compiler is None:
            messagebox.showerror("Import failed", "koala_tilekit_compiler is not available.")
            return
        spec_path = filedialog.askopenfilename(
            title="Import Koala Spec",
            filetypes=[("Spec JSON", "*.json"), ("All files", "*.*")],
        )
        if not spec_path:
            return
        self.logger.info("Import Koala spec: %s", spec_path)
        kla_path = os.path.splitext(spec_path)[0] + ".kla"
        if not os.path.exists(kla_path):
            kla_path = filedialog.askopenfilename(
                title="Select Koala .kla",
                filetypes=[("Koala", "*.kla"), ("All files", "*.*")],
                initialdir=os.path.dirname(spec_path),
            )
            if not kla_path:
                return
        progress = self._show_working_modal("Importing Koala Spec...")
        try:
            artifacts = tilekit_compiler.compile_to_memory(spec_path, kla_path)
        except Exception as exc:
            if progress:
                progress.destroy()
            self.logger.error("Koala import failed: %s", exc, exc_info=True)
            messagebox.showerror("Import failed", str(exc))
            return
        if progress:
            progress.destroy()
        self.logger.info("Koala import completed")
        self.generated_assets = artifacts
        self.load_charset_bytes(
            artifacts["charset_bytes"],
            path_hint=artifacts.get("charset_path_abs"),
            keep_tset=True,
            add_recent=False,
            mark_dirty=True,
            reset_history=False,
        )
        self.load_tset_text(
            artifacts["tset_text"],
            source_path=artifacts.get("tset_path_abs"),
            charset_hint=artifacts.get("charset_path_abs"),
        )

    def open_image_region(self) -> None:
        if not self._confirm_discard_changes():
            return
        if Image is None or ImageTk is None:
            messagebox.showerror("Import failed", "Pillow (PIL) is not available.")
            return
        if convert_image is None:
            messagebox.showerror("Import failed", "char_converter is not available.")
            return
        path = filedialog.askopenfilename(
            title="Import Image Region",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("PNG", "*.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("GIF", "*.gif"),
                ("BMP", "*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.logger.info("Image import selected %s", path)
        self._show_image_region_modal(path)

    def _show_image_region_modal(self, path: str) -> None:
        try:
            image = Image.open(path).convert("RGB")
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc))
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Import Image Region")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)

        dialog.grid_rowconfigure(1, weight=1)
        dialog.grid_columnconfigure(0, weight=1)

        info = tk.Frame(dialog, padx=12, pady=8)
        info.grid(row=0, column=0, sticky="ew")
        tk.Label(info, text="Drag to select region.").pack(side=tk.LEFT)

        mode_var = tk.StringVar(value="hires")
        strategy_labels = [
            "Auto",
            "Lock BG",
            "Lock BG+MC1",
            "Lock BG+MC1+MC2",
        ]
        strategy_values = {
            "Auto": "auto",
            "Lock BG": "lock_bg",
            "Lock BG+MC1": "lock_bg_mc1",
            "Lock BG+MC1+MC2": "lock_bg_mc1_mc2",
        }
        strategy_var = tk.StringVar(value="Auto")
        output_unit_var = tk.StringVar(value="chars")
        preserve_var = tk.BooleanVar(value=True)
        fix_clash_var = tk.BooleanVar(value=True)
        mode_box = tk.Frame(info)
        mode_box.pack(side=tk.RIGHT)
        hires_radio = tk.Radiobutton(mode_box, text="Hires", variable=mode_var, value="hires")
        hires_radio.pack(side=tk.LEFT)
        mc_radio = tk.Radiobutton(mode_box, text="Multicolor", variable=mode_var, value="multicolor")
        mc_radio.pack(side=tk.LEFT)
        if self.current_tset:
            mode_var.set("multicolor")
            hires_radio.configure(state="disabled")
            mc_radio.configure(state="disabled")
            strategy_var.set("Lock BG+MC1+MC2")

        max_display = 600
        fit_scale = min(max_display / image.width, max_display / image.height, 1.0)
        if fit_scale <= 0:
            fit_scale = 1.0
        default_w = max(1, int(image.width * fit_scale))
        default_h = max(1, int(image.height * fit_scale))
        base_scale = {"value": fit_scale}
        zoom_factor = {"value": 1.0}
        display_scale = {"value": fit_scale}

        display_offset = {"x": 0, "y": 0, "w": default_w, "h": default_h}

        def render_display_image():
            scale = display_scale["value"]
            disp_w = max(1, int(image.width * scale))
            disp_h = max(1, int(image.height * scale))
            display_image = image.resize((disp_w, disp_h), Image.NEAREST)
            photo = ImageTk.PhotoImage(display_image)
            return photo, disp_w, disp_h

        photo, disp_w, disp_h = render_display_image()

        body = tk.Frame(dialog, padx=12, pady=8)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)

        image_frame = tk.Frame(body, background=body.cget("bg"))
        image_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=0)
        canvas = tk.Canvas(
            image_frame,
            width=default_w,
            height=default_h,
            background=body.cget("bg"),
            highlightthickness=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        image_item = canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.image = photo

        sel = {"mode": "new", "edges": None, "last": (0, 0)}
        rect = canvas.create_rectangle(0, 0, disp_w, disp_h, outline="#FFFF00", width=2)
        canvas.itemconfigure(rect, state="hidden")
        selection_visible = {"active": False}

        x_var = tk.IntVar(value=0)
        y_var = tk.IntVar(value=0)
        w_var = tk.IntVar(value=image.width)
        h_var = tk.IntVar(value=image.height)

        preview_size = 240
        settings_row = tk.Frame(dialog, padx=12, pady=6)
        settings_row.grid(row=2, column=0, sticky="ew")
        settings_row.grid_columnconfigure(0, weight=1)
        settings_row.grid_columnconfigure(1, weight=0)
        settings_col = tk.Frame(settings_row)
        settings_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        fields = tk.Frame(settings_col)
        fields.pack(fill=tk.X)
        tk.Label(fields, text="X").pack(side=tk.LEFT)
        tk.Entry(fields, textvariable=x_var, width=6).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(fields, text="Y").pack(side=tk.LEFT)
        tk.Entry(fields, textvariable=y_var, width=6).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(fields, text="W").pack(side=tk.LEFT)
        tk.Entry(fields, textvariable=w_var, width=6).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(fields, text="H").pack(side=tk.LEFT)
        tk.Entry(fields, textvariable=h_var, width=6).pack(side=tk.LEFT, padx=(4, 8))

        output_frame = tk.Frame(settings_col, pady=6)
        output_frame.pack(fill=tk.X)
        tk.Label(output_frame, text="Output").pack(side=tk.LEFT)
        tk.Radiobutton(output_frame, text="Chars", variable=output_unit_var, value="chars").pack(side=tk.LEFT, padx=(6, 0))
        tk.Radiobutton(output_frame, text="Tiles", variable=output_unit_var, value="tiles").pack(side=tk.LEFT, padx=(6, 0))
        tk.Radiobutton(output_frame, text="Object", variable=output_unit_var, value="object").pack(side=tk.LEFT, padx=(6, 0))

        chars_w_var = tk.StringVar(value="1")
        chars_h_var = tk.StringVar(value="1")
        tiles_w_var = tk.StringVar(value="1")
        tiles_h_var = tk.StringVar(value="1")

        output_sizes = tk.Frame(settings_col, pady=6)
        output_sizes.pack(fill=tk.X)
        max_chars_w = 40
        max_chars_h = 25
        tk.Label(output_sizes, text="Chars W").pack(side=tk.LEFT)
        chars_w_entry = tk.Entry(output_sizes, textvariable=chars_w_var, width=6)
        chars_w_entry.pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(output_sizes, text="Chars H").pack(side=tk.LEFT)
        chars_h_entry = tk.Entry(output_sizes, textvariable=chars_h_var, width=6)
        chars_h_entry.pack(side=tk.LEFT, padx=(4, 16))
        tk.Label(output_sizes, text="Tiles W").pack(side=tk.LEFT)
        tiles_w_entry = tk.Entry(output_sizes, textvariable=tiles_w_var, width=6)
        tiles_w_entry.pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(output_sizes, text="Tiles H").pack(side=tk.LEFT)
        tiles_h_entry = tk.Entry(output_sizes, textvariable=tiles_h_var, width=6)
        tiles_h_entry.pack(side=tk.LEFT, padx=(4, 0))

        options = tk.Frame(settings_col, pady=4)
        options.pack(fill=tk.X)
        tk.Checkbutton(options, text="Preserve aspect ratio", variable=preserve_var).pack(side=tk.LEFT)
        tk.Checkbutton(options, text="Auto remap clashes", variable=fix_clash_var).pack(side=tk.LEFT, padx=(12, 0))

        palette_frame = tk.Frame(settings_col, pady=4)
        palette_frame.pack(fill=tk.X)
        tk.Label(palette_frame, text="Palette strategy").pack(side=tk.LEFT)
        strategy_menu = ttk.Combobox(
            palette_frame,
            textvariable=strategy_var,
            values=strategy_labels,
            state="readonly",
            width=20,
        )
        strategy_menu.pack(side=tk.LEFT, padx=(6, 12))
        palette_label = tk.Label(palette_frame, text="", anchor="w")
        palette_label.pack(side=tk.LEFT)
        if self.current_tset:
            strategy_menu.configure(state="disabled")

        info_frame = tk.LabelFrame(settings_row, text="Color Info", padx=8, pady=8)
        info_frame.configure(width=260, height=110)
        info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        info_frame.pack_propagate(False)
        result_palette_label = tk.Label(info_frame, text="BG: -  MC1: -  MC2: -", anchor="w", justify="left")
        result_palette_label.pack(anchor="w")
        result_fg_label = tk.Label(info_frame, text="FG: -", anchor="w")
        result_fg_label.pack(anchor="w")
        result_remap_label = tk.Label(info_frame, text="Remap: -", anchor="w", justify="left", wraplength=240)
        result_remap_label.pack(anchor="w")

        preview_total_h = preview_size * 2 + 42
        preview_panel = tk.Frame(body)
        preview_panel.configure(width=preview_size + 32, height=preview_total_h)
        preview_panel.grid(row=0, column=1, sticky="n")
        preview_panel.pack_propagate(False)

        preview_frame = tk.LabelFrame(preview_panel, text="Preview", padx=8, pady=8)
        preview_frame.configure(width=preview_size + 16, height=preview_size + 16)
        preview_frame.pack(side=tk.TOP, fill=tk.X)
        preview_frame.pack_propagate(False)
        preview_canvas = tk.Canvas(preview_frame, width=preview_size, height=preview_size, background=body.cget("bg"))
        preview_canvas.pack()
        preview_canvas.image = None
        result_frame = tk.LabelFrame(preview_panel, text="Result Preview", padx=8, pady=8)
        result_frame.configure(width=preview_size + 16, height=preview_size + 16)
        result_frame.pack(side=tk.TOP, fill=tk.X, pady=(10, 0))
        result_frame.pack_propagate(False)
        result_canvas = tk.Canvas(result_frame, width=preview_size, height=preview_size, background=body.cget("bg"))
        result_canvas.pack()
        result_canvas.image = None
        result_state = {"after_id": None, "meta": None}
        output_override = {"active": False, "updating": False}

        def _current_lock_colors():
            if self.current_tset:
                return {
                    "bg": self.current_tset.bg_color,
                    "mc1": self.current_tset.mc1_color,
                    "mc2": self.current_tset.mc2_color,
                }
            return {
                "bg": self._color_index_by_name(self.bg_var.get()),
                "mc1": self._color_index_by_name(self.mc1_var.get()),
                "mc2": self._color_index_by_name(self.mc2_var.get()),
            }

        def _update_palette_label():
            colors = _current_lock_colors()
            if mode_var.get() == "multicolor":
                palette_label.configure(
                    text=(
                        f"BG: {self._color_name_by_index(colors['bg'])}  "
                        f"MC1: {self._color_name_by_index(colors['mc1'])}  "
                        f"MC2: {self._color_name_by_index(colors['mc2'])}"
                    )
                )
            else:
                palette_label.configure(text=f"BG: {self._color_name_by_index(colors['bg'])}")

        def clamp_selection():
            x = max(0, min(x_var.get(), image.width - 1))
            y = max(0, min(y_var.get(), image.height - 1))
            w = max(1, min(w_var.get(), image.width - x))
            h = max(1, min(h_var.get(), image.height - y))
            x_var.set(x)
            y_var.set(y)
            w_var.set(w)
            h_var.set(h)
            s = display_scale["value"]
            sx0 = display_offset["x"] + int(x * s)
            sy0 = display_offset["y"] + int(y * s)
            sx1 = display_offset["x"] + int((x + w) * s)
            sy1 = display_offset["y"] + int((y + h) * s)
            if selection_visible["active"]:
                canvas.coords(rect, sx0, sy0, sx1, sy1)
                canvas.itemconfigure(rect, state="normal")

        def update_from_canvas():
            s = display_scale["value"]
            x0, y0, x1, y1 = canvas.coords(rect)
            x0, y0, x1, y1 = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
            x = int((x0 - display_offset["x"]) / s)
            y = int((y0 - display_offset["y"]) / s)
            w = max(1, int((x1 - x0) / s))
            h = max(1, int((y1 - y0) / s))
            x_var.set(x)
            y_var.set(y)
            w_var.set(w)
            h_var.set(h)
            clamp_selection()
            update_output_defaults()

        def _safe_int(var, default):
            try:
                value = var.get()
            except tk.TclError:
                return default
            if value in ("", None):
                return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default

        def update_output_defaults():
            if output_override["active"]:
                return
            output_override["updating"] = True
            cell_w = 8
            cell_h = 8
            cols = max(1, min(max_chars_w, w_var.get() // cell_w))
            rows = max(1, min(max_chars_h, h_var.get() // cell_h))
            chars_w_var.set(str(cols))
            chars_h_var.set(str(rows))
            tiles_w_var.set(str(max(1, cols // 2)))
            tiles_h_var.set(str(max(1, rows // 2)))
            output_override["updating"] = False
            build_preview()

        def build_preview():
            try:
                if mode_var.get() == "hires":
                    cell_w = 8
                    cell_h = 8
                    src = image
                    scale_x = 1.0
                else:
                    cell_h = 8
                    src = image
                    scale_x = 1.0
                    cell_w = 8

                x = int(x_var.get() * scale_x)
                w = int(w_var.get() * scale_x)
                x = max(0, min(x, src.width - 1))
                y = max(0, min(y_var.get(), src.height - 1))
                w = max(1, min(w, src.width - x))
                h = max(1, min(h_var.get(), src.height - y))

                if output_unit_var.get() == "chars":
                    cols = max(1, min(40, _safe_int(chars_w_var, 1)))
                    rows = max(1, min(25, _safe_int(chars_h_var, 1)))
                else:
                    cols = max(1, min(20, _safe_int(tiles_w_var, 1))) * 2
                    rows = max(1, min(12, _safe_int(tiles_h_var, 1))) * 2

                cols = min(cols, 40)
                rows = min(rows, 25)

                target_w = cols * cell_w
                target_h = rows * cell_h
                raw_region = src.crop((x, y, x + w, y + h))
                if preserve_var.get():
                    bg_rgb = self._hex_to_rgb(self._color_hex_by_index(_current_lock_colors()["bg"]))
                    region = self._fit_region_to_target_with_bg(raw_region, target_w, target_h, bg_rgb)
                else:
                    region = raw_region.resize((target_w, target_h), Image.NEAREST)

                scale = min(preview_size / raw_region.width, preview_size / raw_region.height)
                prev_w = max(1, int(raw_region.width * scale))
                prev_h = max(1, int(raw_region.height * scale))
                preview = raw_region.resize((prev_w, prev_h), Image.NEAREST)
                photo = ImageTk.PhotoImage(preview)
                preview_frame.configure(width=preview_size + 16, height=preview_size + 16)
                preview_canvas.configure(width=preview_size, height=preview_size)
                preview_canvas.delete("all")
                x = (preview_size - prev_w) // 2
                y = (preview_size - prev_h) // 2
                preview_canvas.create_image(x, y, anchor="nw", image=photo)
                preview_canvas.image = photo
                schedule_result_preview()
            except Exception:
                preview_canvas.delete("all")
                preview_canvas.image = None
                result_canvas.delete("all")
                result_canvas.image = None

        def schedule_result_preview():
            if result_state["after_id"]:
                dialog.after_cancel(result_state["after_id"])
            result_state["after_id"] = dialog.after(250, update_result_preview)

        def update_result_preview():
            result_state["after_id"] = None
            try:
                mode = mode_var.get()
                cell_w = 8
                cell_h = 8
                base_size = (320, 200)
                x = x_var.get()
                y = y_var.get()
                w = w_var.get()
                h = h_var.get()
                if output_unit_var.get() == "chars":
                    cols = max(1, min(40, _safe_int(chars_w_var, 1)))
                    rows = max(1, min(25, _safe_int(chars_h_var, 1)))
                else:
                    cols = max(1, min(20, _safe_int(tiles_w_var, 1))) * 2
                    rows = max(1, min(12, _safe_int(tiles_h_var, 1))) * 2
                target_w = cols * cell_w
                target_h = rows * cell_h

                raw_region = image.crop((x, y, x + w, y + h))
                placement = None
                if preserve_var.get():
                    scale = min(target_w / raw_region.width, target_h / raw_region.height)
                    scaled_w = max(1, int(raw_region.width * scale))
                    scaled_h = max(1, int(raw_region.height * scale))
                    placement = {
                        "target_w": target_w,
                        "target_h": target_h,
                        "offset_x": (target_w - scaled_w) // 2,
                        "offset_y": (target_h - scaled_h) // 2,
                        "scaled_w": scaled_w,
                        "scaled_h": scaled_h,
                    }
                    region = raw_region
                else:
                    region = raw_region.resize((target_w, target_h), Image.NEAREST)
                strategy = strategy_values.get(strategy_var.get(), "auto")
                locks = _current_lock_colors()
                result = convert_image(region, mode, strategy, locks, remap=fix_clash_var.get(), placement=placement)

                result_img = self._render_convert_result(result, mode, target_w, target_h)
                if result_img is None:
                    raise ValueError("No preview")
                scale = min(preview_size / target_w, preview_size / target_h)
                prev_w = max(1, int(target_w * scale))
                prev_h = max(1, int(target_h * scale))
                preview = result_img.resize((prev_w, prev_h), Image.NEAREST)
                photo = ImageTk.PhotoImage(preview)
                result_frame.configure(width=preview_size + 16, height=preview_size + 16)
                result_canvas.configure(width=preview_size, height=preview_size)
                result_canvas.delete("all")
                x = (preview_size - prev_w) // 2
                y = (preview_size - prev_h) // 2
                result_canvas.create_image(x, y, anchor="nw", image=photo)
                grid_unit = 16 if output_unit_var.get() in ("tiles", "object") else 8
                for gx in range(0, target_w + 1, grid_unit):
                    px = x + int(gx * scale)
                    result_canvas.create_line(px, y, px, y + prev_h, fill="#FF5FA2")
                for gy in range(0, target_h + 1, grid_unit):
                    py = y + int(gy * scale)
                    result_canvas.create_line(x, py, x + prev_w, py, fill="#FF5FA2")
                result_canvas.image = photo
                result_state["meta"] = {
                    "mode": mode,
                    "scale": scale,
                    "offset": (x, y),
                    "size": (target_w, target_h),
                    "cols": target_w // 8,
                    "rows": target_h // 8,
                    "screen": result.screen_ram,
                    "color": result.color_ram,
                    "bg": result.bg,
                    "mc1": result.mc1,
                    "mc2": result.mc2,
                }
                if mode == "multicolor":
                    result_palette_label.configure(
                        text=(
                            f"BG: {self._color_name_by_index(result.bg)}  "
                            f"MC1: {self._color_name_by_index(result.mc1)}  "
                            f"MC2: {self._color_name_by_index(result.mc2)}"
                        )
                    )
                else:
                    result_palette_label.configure(text=f"BG: {self._color_name_by_index(result.bg)}")
                result_fg_label.configure(text="FG: -")
                if result.remap_counts:
                    ordered = sorted(result.remap_counts.items(), key=lambda item: item[1], reverse=True)
                    parts = []
                    remaining = 0
                    for idx, ((src, dst), count) in enumerate(ordered):
                        if idx < 4:
                            parts.append(
                                f"{self._color_name_by_index(src)}→{self._color_name_by_index(dst)} x{count}"
                            )
                        else:
                            remaining += count
                    if remaining:
                        parts.append(f"+{remaining} more")
                    result_remap_label.configure(text=f"Remap: {', '.join(parts)}")
                else:
                    result_remap_label.configure(text="Remap: none")
            except Exception:
                result_canvas.delete("all")
                result_canvas.image = None
                result_palette_label.configure(text="BG: -  MC1: -  MC2: -")
                result_fg_label.configure(text="FG: -")
                result_remap_label.configure(text="Remap: -")
                result_state["meta"] = None

        def on_result_click(event):
            meta = result_state.get("meta")
            if not meta:
                return
            offset_x, offset_y = meta["offset"]
            scale = meta["scale"]
            width, height = meta["size"]
            src_x = int((event.x - offset_x) / scale)
            src_y = int((event.y - offset_y) / scale)
            if not (0 <= src_x < width and 0 <= src_y < height):
                return
            col = src_x // 8
            row = src_y // 8
            cols = meta.get("cols") or (width // 8)
            idx = row * cols + col
            screen = meta["screen"]
            if idx >= len(screen):
                return
            if meta["mode"] == "hires":
                fg = (screen[idx] >> 4) & 0x0F
            else:
                fg = screen[idx] & 0x0F
            result_fg_label.configure(text=f"FG: {self._color_name_by_index(fg)}")

        result_canvas.bind("<Button-1>", on_result_click)

        def _hit_test(x, y, x0, y0, x1, y1):
            handle = 6
            edges = {"left": abs(x - x0) <= handle,
                     "right": abs(x - x1) <= handle,
                     "top": abs(y - y0) <= handle,
                     "bottom": abs(y - y1) <= handle}
            if any(edges.values()):
                return "resize", edges
            if x0 < x < x1 and y0 < y < y1:
                return "move", None
            return "new", None

        def _event_to_image_coords(event):
            s = display_scale["value"]
            x = int((event.x - display_offset["x"]) / s)
            y = int((event.y - display_offset["y"]) / s)
            x = max(0, min(x, image.width - 1))
            y = max(0, min(y, image.height - 1))
            return x, y

        def on_press(event):
            x0, y0, x1, y1 = canvas.coords(rect)
            x0, y0, x1, y1 = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
            mode, edges = _hit_test(event.x, event.y, x0, y0, x1, y1)
            sel["mode"] = mode
            sel["edges"] = edges
            sel["last"] = _event_to_image_coords(event)
            sel["origin"] = (x_var.get(), y_var.get(), w_var.get(), h_var.get())
            selection_visible["active"] = True
            canvas.itemconfigure(rect, state="normal")
            if mode == "new":
                x_img, y_img = sel["last"]
                x_var.set(x_img)
                y_var.set(y_img)
                w_var.set(1)
                h_var.set(1)
                clamp_selection()

        def on_drag(event):
            x_img, y_img = _event_to_image_coords(event)
            start_x, start_y = sel["last"]
            orig_x, orig_y, orig_w, orig_h = sel.get("origin", (x_var.get(), y_var.get(), w_var.get(), h_var.get()))
            if sel["mode"] == "move":
                dx = x_img - start_x
                dy = y_img - start_y
                x_var.set(orig_x + dx)
                y_var.set(orig_y + dy)
            elif sel["mode"] == "resize" and sel["edges"]:
                x0 = orig_x
                y0 = orig_y
                x1 = orig_x + orig_w
                y1 = orig_y + orig_h
                if sel["edges"].get("left"):
                    x0 = min(x_img, x1 - 1)
                if sel["edges"].get("right"):
                    x1 = max(x_img, x0 + 1)
                if sel["edges"].get("top"):
                    y0 = min(y_img, y1 - 1)
                if sel["edges"].get("bottom"):
                    y1 = max(y_img, y0 + 1)
                x_var.set(x0)
                y_var.set(y0)
                w_var.set(max(1, x1 - x0))
                h_var.set(max(1, y1 - y0))
            else:
                x0 = min(start_x, x_img)
                y0 = min(start_y, y_img)
                x1 = max(start_x, x_img)
                y1 = max(start_y, y_img)
                x_var.set(x0)
                y_var.set(y0)
                w_var.set(max(1, x1 - x0))
                h_var.set(max(1, y1 - y0))
            clamp_selection()

        def on_release(_event):
            sel["mode"] = "new"
            sel["edges"] = None

        canvas.bind("<Button-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        def on_entry_change(*_args):
            selection_visible["active"] = True
            clamp_selection()
            build_preview()

        x_var.trace_add("write", on_entry_change)
        y_var.trace_add("write", on_entry_change)
        w_var.trace_add("write", on_entry_change)
        h_var.trace_add("write", on_entry_change)
        mode_var.trace_add("write", lambda *_: (update_output_defaults(), _update_palette_label()))
        _update_palette_label()
        update_output_defaults()
        build_preview()

        def update_output_entry_state(*_args):
            unit = output_unit_var.get()
            if unit == "chars":
                chars_w_entry.configure(state="normal")
                chars_h_entry.configure(state="normal")
                tiles_w_entry.configure(state="disabled")
                tiles_h_entry.configure(state="disabled")
            else:
                chars_w_entry.configure(state="disabled")
                chars_h_entry.configure(state="disabled")
                tiles_w_entry.configure(state="normal")
                tiles_h_entry.configure(state="normal")
            build_preview()

        output_unit_var.trace_add("write", update_output_entry_state)
        preserve_var.trace_add("write", lambda *_: build_preview())
        strategy_var.trace_add("write", lambda *_: build_preview())
        fix_clash_var.trace_add("write", lambda *_: build_preview())
        def _log_output_change(label: str) -> None:
            if not output_override["updating"]:
                output_override["active"] = True
            self.logger.info(
                "Import output change %s chars=%sx%s tiles=%sx%s unit=%s",
                label,
                chars_w_var.get(),
                chars_h_var.get(),
                tiles_w_var.get(),
                tiles_h_var.get(),
                output_unit_var.get(),
            )

        chars_w_var.trace_add("write", lambda *_: (_log_output_change("chars_w"), build_preview()))
        chars_h_var.trace_add("write", lambda *_: (_log_output_change("chars_h"), build_preview()))
        tiles_w_var.trace_add("write", lambda *_: (_log_output_change("tiles_w"), build_preview()))
        tiles_h_var.trace_add("write", lambda *_: (_log_output_change("tiles_h"), build_preview()))
        update_output_entry_state()

        def _mark_output_override(_event=None):
            output_override["active"] = True

        for entry in (chars_w_entry, chars_h_entry, tiles_w_entry, tiles_h_entry):
            entry.bind("<KeyRelease>", _mark_output_override)

        def on_zoom(event):
            delta = 1 if event.delta > 0 else -1
            zoom_factor["value"] = max(0.25, min(8.0, zoom_factor["value"] * (1.1 ** delta)))
            display_scale["value"] = base_scale["value"] * zoom_factor["value"]
            photo, new_w, new_h = render_display_image()
            canvas.itemconfigure(image_item, image=photo)
            canvas.image = photo
            update_from_canvas()

        canvas.bind("<MouseWheel>", on_zoom)

        resize_state = {"after_id": None}

        def _apply_resize():
            resize_state["after_id"] = None
            available_w = max(1, image_frame.winfo_width())
            available_h = max(1, image_frame.winfo_height())
            new_base = min(available_w / image.width, available_h / image.height)
            if new_base <= 0:
                return
            base_scale["value"] = new_base
            display_scale["value"] = new_base * zoom_factor["value"]
            photo, new_w, new_h = render_display_image()
            offset_x = max(0, (available_w - new_w) // 2)
            offset_y = max(0, (available_h - new_h) // 2)
            display_offset["x"] = offset_x
            display_offset["y"] = offset_y
            display_offset["w"] = new_w
            display_offset["h"] = new_h
            canvas.itemconfigure(image_item, image=photo)
            canvas.coords(image_item, offset_x, offset_y)
            canvas.image = photo
            clamp_selection()

        def on_resize(_event=None):
            if resize_state["after_id"]:
                dialog.after_cancel(resize_state["after_id"])
            resize_state["after_id"] = dialog.after(50, _apply_resize)

        image_frame.bind("<Configure>", on_resize)
        dialog.after(0, on_resize)

        actions = tk.Frame(dialog, padx=12, pady=10)
        actions.grid(row=3, column=0, sticky="ew")
        tk.Button(actions, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

        def do_import():
            parsed_chars_w = max(1, min(40, _safe_int(chars_w_var, 1)))
            parsed_chars_h = max(1, min(25, _safe_int(chars_h_var, 1)))
            parsed_tiles_w = max(1, min(20, _safe_int(tiles_w_var, 1)))
            parsed_tiles_h = max(1, min(12, _safe_int(tiles_h_var, 1)))
            strategy = strategy_values.get(strategy_var.get(), "auto")
            locks = _current_lock_colors()
            dialog.destroy()
            self._import_image_region(
                image,
                mode_var.get(),
                x_var.get(),
                y_var.get(),
                w_var.get(),
                h_var.get(),
                output_unit_var.get(),
                parsed_chars_w,
                parsed_chars_h,
                parsed_tiles_w,
                parsed_tiles_h,
                preserve_var.get(),
                fix_clash_var.get(),
                strategy,
                locks,
            )

        tk.Button(actions, text="Import", command=do_import).pack(side=tk.RIGHT, padx=(0, 8))
        dialog.update_idletasks()
        dialog.minsize(dialog.winfo_reqwidth(), dialog.winfo_reqheight())
        dialog.wait_window()

    def _import_image_region(
        self,
        image: Image.Image,
        mode: str,
        x: int,
        y: int,
        w: int,
        h: int,
        output_unit: str,
        chars_w: int,
        chars_h: int,
        tiles_w: int,
        tiles_h: int,
        preserve_aspect: bool,
        fix_clashes: bool,
        palette_strategy: str,
        palette_locks: dict,
    ) -> None:
        self.logger.info(
            "Image import params mode=%s selection=(%s,%s %sx%s) output=%s chars=%sx%s tiles=%sx%s aspect=%s strategy=%s locks=%s",
            mode,
            x,
            y,
            w,
            h,
            output_unit,
            chars_w,
            chars_h,
            tiles_w,
            tiles_h,
            preserve_aspect,
            palette_strategy,
            palette_locks,
        )
        if not self.charset_bytes:
            if not messagebox.askyesno(
                "Create charset",
                "No charset loaded. Create a new empty charset?",
            ):
                return
            self._create_empty_charset()
        if output_unit in ("tiles", "object") and not self.current_tset:
            if messagebox.askyesno(
                "Create tileset",
                "No tileset loaded. Create a new empty tileset?",
            ):
                self._create_empty_tset()
        if mode == "hires":
            cell_w = 8
            cell_h = 8
            src = image
            scale_x = 1.0
        else:
            cell_h = 8
            src = image
            scale_x = 1.0
            cell_w = 8

        x = int(x * scale_x)
        w = int(w * scale_x)
        x = max(0, min(x, src.width - 1))
        y = max(0, min(y, src.height - 1))
        w = max(1, min(w, src.width - x))
        h = max(1, min(h, src.height - y))

        if output_unit == "chars":
            cols = max(1, min(40, chars_w))
            rows = max(1, min(25, chars_h))
        else:
            cols = max(1, min(20, tiles_w)) * 2
            rows = max(1, min(12, tiles_h)) * 2

        max_cols = 40
        max_rows = 25
        if cols > max_cols or rows > max_rows:
            messagebox.showerror("Import failed", f"Max {max_cols}x{max_rows} chars for this mode.")
            return

        target_w = cols * cell_w
        target_h = rows * cell_h
        self.logger.info(
            "Image import target chars=%sx%s size=%sx%s cell=%sx%s",
            cols,
            rows,
            target_w,
            target_h,
            cell_w,
            cell_h,
        )
        raw_region = src.crop((x, y, x + w, y + h))
        placement = None
        if preserve_aspect:
            scale = min(target_w / raw_region.width, target_h / raw_region.height)
            scaled_w = max(1, int(raw_region.width * scale))
            scaled_h = max(1, int(raw_region.height * scale))
            placement = {
                "target_w": target_w,
                "target_h": target_h,
                "offset_x": (target_w - scaled_w) // 2,
                "offset_y": (target_h - scaled_h) // 2,
                "scaled_w": scaled_w,
                "scaled_h": scaled_h,
            }
            region = raw_region
        else:
            region = raw_region.resize((target_w, target_h), Image.NEAREST)

        progress = self._show_working_modal("Importing image region...")
        try:
            result = convert_image(region, mode, palette_strategy, palette_locks, remap=fix_clashes, placement=placement)
        except Exception as exc:
            if progress:
                progress.destroy()
            self.logger.error("Image import failed: %s", exc, exc_info=True)
            messagebox.showerror("Import failed", str(exc))
            return
        if progress:
            progress.destroy()

        bitmap = result.charset
        if not bitmap:
            self.logger.error("Image import produced no bitmap data")
            messagebox.showerror("Import failed", "No bitmap data produced.")
            return
        screen_ram = result.screen_ram
        color_ram = result.color_ram
        if result.remap_counts:
            ordered = sorted(result.remap_counts.items(), key=lambda item: item[1], reverse=True)
            summary = ", ".join(
                f"{self._color_name_by_index(src)}→{self._color_name_by_index(dst)} x{count}"
                for (src, dst), count in ordered[:6]
            )
            self.logger.info("Import auto-remap: %s", summary)

        if mode == "multicolor" and self.current_tset:
            bg = result.bg
            mc1 = result.mc1
            mc2 = result.mc2
            warn_bits = []
            if bg is not None and bg != self.current_tset.bg_color:
                warn_bits.append(
                    f"BG {bg} ({self._color_name_by_index(bg)}) != "
                    f"TSET {self.current_tset.bg_color} ({self._color_name_by_index(self.current_tset.bg_color)})"
                )
            if mc1 is not None and mc1 != self.current_tset.mc1_color:
                warn_bits.append(
                    f"MC1 {mc1} ({self._color_name_by_index(mc1)}) != "
                    f"TSET {self.current_tset.mc1_color} ({self._color_name_by_index(self.current_tset.mc1_color)})"
                )
            if mc2 is not None and mc2 != self.current_tset.mc2_color:
                warn_bits.append(
                    f"MC2 {mc2} ({self._color_name_by_index(mc2)}) != "
                    f"TSET {self.current_tset.mc2_color} ({self._color_name_by_index(self.current_tset.mc2_color)})"
                )
            if warn_bits:
                if self._confirm_apply_import_colors("\n".join(warn_bits)):
                    if bg is not None:
                        self.current_tset.bg_color = bg
                        self.bg_var.set(self._color_name_by_index(bg))
                    if mc1 is not None:
                        self.current_tset.mc1_color = mc1
                        self.mc1_var.set(self._color_name_by_index(mc1))
                    if mc2 is not None:
                        self.current_tset.mc2_color = mc2
                        self.mc2_var.set(self._color_name_by_index(mc2))
                    self._mark_tset_dirty()
                    self.refresh_all()
                    self.logger.info("Import colors applied to TSET")
                else:
                    self.logger.info("Import color mismatch: %s", " | ".join(warn_bits))
            self.logger.info(
                "Import colors inferred bg=%s (%s) mc1=%s (%s) mc2=%s (%s)",
                bg,
                self._color_name_by_index(bg) if bg is not None else "unknown",
                mc1,
                self._color_name_by_index(mc1) if mc1 is not None else "unknown",
                mc2,
                self._color_name_by_index(mc2) if mc2 is not None else "unknown",
            )

        cols = target_w // cell_w
        rows = target_h // cell_h
        chars_needed = cols * rows
        self._ensure_charset_capacity(chars_needed)
        if self.selected_index + chars_needed > self.total_chars:
            messagebox.showerror("Import failed", "Not enough space in charset for selection.")
            return

        self._record_undo()
        for row in range(rows):
            for col in range(cols):
                char_index = row * cols + col
                start = char_index * 8
                end = start + 8
                if end > len(bitmap):
                    self.logger.warning(
                        "Bitmap data shorter than expected (end=%s len=%s)",
                        end,
                        len(bitmap),
                    )
                    continue
                dest = (self.selected_index + row * cols + col) * 8
                self.charset_bytes[dest:dest + 8] = bytearray(bitmap[start:end])

        created_tiles = []
        created_object = None
        if output_unit in ("tiles", "object") and self.current_tset and TileDef is not None:
            per_char_colors = []
            for row in range(rows):
                for col in range(cols):
                    idx = row * cols + col
                    if mode == "hires":
                        if idx < len(screen_ram):
                            color = (screen_ram[idx] >> 4) & 0x0F
                        else:
                            color = self._color_index_by_name(self.fg_var.get())
                    else:
                        if idx < len(screen_ram):
                            color = screen_ram[idx] & 0x0F
                        else:
                            color = self._color_index_by_name(self.fg_var.get())
                    per_char_colors.append(color)

            for ty in range(max(1, tiles_h)):
                for tx in range(max(1, tiles_w)):
                    tid = self._next_tile_id()
                    name = f"IMG_TILE_{tid}"
                    while name.upper() in self.current_tset.tiles_by_name:
                        tid = self._next_tile_id()
                        name = f"IMG_TILE_{tid}"
                    base_row = ty * 2
                    base_col = tx * 2
                    chars = []
                    colors = []
                    for dy in range(2):
                        for dx in range(2):
                            char_idx = (base_row + dy) * cols + (base_col + dx)
                            if char_idx >= len(per_char_colors):
                                chars.append(self.selected_index)
                                colors.append(self._color_index_by_name(self.fg_var.get()))
                            else:
                                chars.append(self.selected_index + char_idx)
                                colors.append(per_char_colors[char_idx])
                    tile = TileDef(
                        tid=tid,
                        name=name,
                        chars=chars,
                        color_mode=1,
                        colors=colors,
                        flags=0,
                        hint="",
                    )
                    self.current_tset.tiles[tid] = tile
                    self.current_tset.tiles_by_name[name.upper()] = tid
                    created_tiles.append(tid)

            if output_unit == "object" and ObjectDef is not None:
                obj_name = f"IMG_OBJECT_{len(self.current_tset.objects) + 1}"
                obj_key = obj_name.upper()
                while obj_key in self.current_tset.objects:
                    obj_name = f"IMG_OBJECT_{len(self.current_tset.objects) + 1}"
                    obj_key = obj_name.upper()
                tile_names = [self.current_tset.tiles[tid].name.upper() for tid in created_tiles]
                created_object = ObjectDef(
                    name=obj_name,
                    w=tiles_w,
                    h=tiles_h,
                    tiles=tile_names,
                )
                self.current_tset.objects[obj_key] = created_object
                self.logger.info("Created object %s size=%sx%s", obj_name, tiles_w, tiles_h)
                self.selected_object = obj_key

            if created_tiles:
                self.selected_tile = created_tiles[0]
                self._load_tile_editor(self.current_tset.tiles[self.selected_tile])
                self._update_tile_flags_display()
                self._mark_tset_dirty()
                self.logger.info("Created %s tiles from image import", len(created_tiles))
        self.mode_var.set("hires" if mode == "hires" else "multicolor")
        self._mark_dirty()
        self._draw_grid()
        self.refresh_selected()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self.logger.info("Imported image region (%s) %sx%s chars", mode, cols, rows)

    def _ensure_charset_capacity(self, _chars: int) -> None:
        if self.total_chars <= 0 or not self.charset_bytes:
            self.total_chars = self.page_chars * 2
            self.charset_bytes = bytearray(self.total_chars * 8)
            self.selected_index = 0
            self._init_flag_vars(clear=self.current_tset is None)
            self._draw_grid()

    def _create_empty_charset(self) -> None:
        self.total_chars = self.page_chars * 2
        self.charset_bytes = bytearray(self.total_chars * 8)
        self.current_file = None
        self.selected_index = 0
        self.mode_var.set("hires")
        self.bg_var.set("Black")
        self.fg_var.set("White")
        self.mc1_var.set("Light Red")
        self.mc2_var.set("Light Green")
        self.dirty = True
        self._update_title()
        self._draw_grid()
        self.refresh_selected()
        self._reset_history()

    def _create_empty_tset(self) -> None:
        if TsetParseResult is None or TileDef is None:
            return
        fg = self._color_index_by_name(self.fg_var.get())
        bg = self._color_index_by_name(self.bg_var.get())
        mc1 = self._color_index_by_name(self.mc1_var.get())
        mc2 = self._color_index_by_name(self.mc2_var.get())
        tset = TsetParseResult(
            name="UNTITLED",
            tile_w=2,
            tile_h=2,
            declared_count=1,
            bg_color=bg,
            mc1_color=mc1,
            mc2_color=mc2,
            charset_path="",
            flagbits=dict(FIXED_FLAGBITS),
        )
        tile = TileDef(
            tid=0,
            name="DEFAULT",
            chars=[0, 0, 0, 0],
            color_mode=0,
            colors=[fg, 0, 0, 0],
            flags=0,
            hint="",
        )
        tset.tiles[0] = tile
        tset.tiles_by_name["DEFAULT"] = 0
        self.current_tset = tset
        self.current_tset_path = None
        self.current_tset_charset = None
        self.selected_tile = 0
        self.tset_dirty = True
        self._init_flag_vars(clear=False)
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._update_title()
        self._reset_history()
    def _fit_region_to_aspect(self, region: Image.Image, target_w: int, target_h: int) -> Image.Image:
        if target_w <= 0 or target_h <= 0:
            return region
        src_w, src_h = region.size
        if src_w <= 0 or src_h <= 0:
            return region
        src_ratio = src_w / src_h
        target_ratio = target_w / target_h
        if abs(src_ratio - target_ratio) < 1e-3:
            return region
        if src_ratio > target_ratio:
            new_w = int(src_h * target_ratio)
            offset = (src_w - new_w) // 2
            box = (offset, 0, offset + new_w, src_h)
        else:
            new_h = int(src_w / target_ratio)
            offset = (src_h - new_h) // 2
            box = (0, offset, src_w, offset + new_h)
        return region.crop(box)

    def _fit_region_to_target(self, region: Image.Image, target_w: int, target_h: int) -> Image.Image:
        if target_w <= 0 or target_h <= 0:
            return region
        src_w, src_h = region.size
        if src_w <= 0 or src_h <= 0:
            return region
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        resized = region.resize((new_w, new_h), Image.NEAREST)
        canvas = Image.new("RGB", (target_w, target_h), (0, 0, 0))
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        canvas.paste(resized, (x, y))
        return canvas

    def _fit_region_to_target_with_bg(
        self,
        region: Image.Image,
        target_w: int,
        target_h: int,
        bg_rgb: tuple[int, int, int],
    ) -> Image.Image:
        if target_w <= 0 or target_h <= 0:
            return region
        src_w, src_h = region.size
        if src_w <= 0 or src_h <= 0:
            return region
        scale = min(target_w / src_w, target_h / src_h)
        new_w = max(1, int(src_w * scale))
        new_h = max(1, int(src_h * scale))
        resized = region.resize((new_w, new_h), Image.NEAREST)
        canvas = Image.new("RGB", (target_w, target_h), bg_rgb)
        x = (target_w - new_w) // 2
        y = (target_h - new_h) // 2
        canvas.paste(resized, (x, y))
        return canvas

    def _hex_to_rgb(self, hex_value: str) -> tuple[int, int, int]:
        value = hex_value.lstrip("#")
        if len(value) != 6:
            return (0, 0, 0)
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def _render_convert_result(self, result: ConvertResult, mode: str, width: int, height: int) -> Image.Image | None:
        if Image is None:
            return None
        cols = width // 8
        rows = height // 8
        if mode == "hires":
            img = Image.new("RGB", (width, height), self._hex_to_rgb(self._color_hex_by_index(result.bg)))
            for cy in range(rows):
                for cx in range(cols):
                    idx = cy * cols + cx
                    if idx >= len(result.screen_ram):
                        continue
                    fg = (result.screen_ram[idx] >> 4) & 0x0F
                    bg = result.screen_ram[idx] & 0x0F
                    fg_rgb = self._hex_to_rgb(self._color_hex_by_index(fg))
                    bg_rgb = self._hex_to_rgb(self._color_hex_by_index(bg))
                    base = idx * 8
                    for y in range(8):
                        if base + y >= len(result.charset):
                            continue
                        b = result.charset[base + y]
                        for x in range(8):
                            color = fg_rgb if (b >> (7 - x)) & 1 else bg_rgb
                            img.putpixel((cx * 8 + x, cy * 8 + y), color)
            return img

        img = Image.new("RGB", (width, height), self._hex_to_rgb(self._color_hex_by_index(result.bg)))
        for cy in range(rows):
            for cx in range(cols):
                idx = cy * cols + cx
                if idx >= len(result.screen_ram):
                    continue
                fg = result.screen_ram[idx] & 0x0F
                colors = [
                    self._hex_to_rgb(self._color_hex_by_index(result.bg)),
                    self._hex_to_rgb(self._color_hex_by_index(result.mc1)),
                    self._hex_to_rgb(self._color_hex_by_index(result.mc2)),
                    self._hex_to_rgb(self._color_hex_by_index(fg)),
                ]
                base = idx * 8
                for y in range(8):
                    if base + y >= len(result.charset):
                        continue
                    b = result.charset[base + y]
                    for xmc in range(4):
                        code = (b >> (6 - 2 * xmc)) & 0x03
                        color = colors[code]
                        px = cx * 8 + xmc * 2
                        py = cy * 8 + y
                        img.putpixel((px, py), color)
                        img.putpixel((px + 1, py), color)
        return img

    def _render_c64img_result(self, converter, mode: str, width: int, height: int) -> Image.Image | None:
        if Image is None:
            return None
        if mode == "hires":
            bitmap = converter.data.get("bitmap", [])
            screen = converter.data.get("screen-ram", [])
            cols = width // 8
            rows = height // 8
            img = Image.new("RGB", (width, height), (0, 0, 0))
            for cy in range(rows):
                for cx in range(cols):
                    idx = cy * cols + cx
                    if idx >= len(screen):
                        continue
                    fg = (screen[idx] >> 4) & 0x0F
                    bg = screen[idx] & 0x0F
                    fg_rgb = self._hex_to_rgb(self._color_hex_by_index(fg))
                    bg_rgb = self._hex_to_rgb(self._color_hex_by_index(bg))
                    base = idx * 8
                    for y in range(8):
                        if base + y >= len(bitmap):
                            continue
                        b = bitmap[base + y]
                        for x in range(8):
                            color = fg_rgb if (b >> (7 - x)) & 1 else bg_rgb
                            img.putpixel((cx * 8 + x, cy * 8 + y), color)
            return img

        bitmap = converter.data.get("bitmap", [])
        screen = converter.data.get("screen-ram", [])
        color_ram = converter.data.get("color-ram", [])
        bg = converter.data.get("background", 0)
        cols = width // 8
        rows = height // 8
        img = Image.new("RGB", (width, height), self._hex_to_rgb(self._color_hex_by_index(bg)))
        for cy in range(rows):
            for cx in range(cols):
                idx = cy * cols + cx
                if idx >= len(screen) or idx >= len(color_ram):
                    continue
                mc1 = (color_ram[idx] >> 4) & 0x0F
                mc2 = color_ram[idx] & 0x0F
                fg = screen[idx] & 0x0F
                colors = [
                    self._hex_to_rgb(self._color_hex_by_index(bg)),
                    self._hex_to_rgb(self._color_hex_by_index(mc1)),
                    self._hex_to_rgb(self._color_hex_by_index(mc2)),
                    self._hex_to_rgb(self._color_hex_by_index(fg)),
                ]
                base = idx * 8
                for y in range(8):
                    if base + y >= len(bitmap):
                        continue
                    b = bitmap[base + y]
                    for xmc in range(4):
                        code = (b >> (6 - 2 * xmc)) & 0x03
                        color = colors[code]
                        px = cx * 8 + xmc * 2
                        py = cy * 8 + y
                        img.putpixel((px, py), color)
                        img.putpixel((px + 1, py), color)
        return img

    def _confirm_apply_import_colors(self, details: str) -> bool:
        dialog = tk.Toplevel(self.root)
        dialog.title("Import colors differ")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = tk.Frame(dialog, padx=12, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text="Imported image colors do not match current TSET:").pack(anchor="w")
        tk.Label(frame, text=details, justify="left").pack(anchor="w", pady=(6, 0))

        result = {"apply": False}
        actions = tk.Frame(frame, pady=10)
        actions.pack(fill=tk.X)
        tk.Button(actions, text="Keep Current", command=dialog.destroy).pack(side=tk.RIGHT)

        def _apply():
            result["apply"] = True
            dialog.destroy()

        tk.Button(actions, text="Apply Suggested Colors", command=_apply).pack(side=tk.RIGHT, padx=(0, 8))
        dialog.wait_window()
        return result["apply"]
    def _show_working_modal(self, message: str) -> tk.Toplevel | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Working...")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        frame = tk.Frame(dialog, padx=20, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(frame, text=message).pack()
        dialog.update_idletasks()
        dialog.update()
        return dialog

    def save_file(self) -> None:
        if not self.current_file:
            self.save_file_as()
            return
        self.logger.info("Saving charset to %s", self.current_file)
        if self._write_charset(self.current_file):
            self._clear_dirty()

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Charset As",
            defaultextension=".bin",
            filetypes=[("Charset binary", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.logger.info("Save charset as %s", path)
            self.current_file = path
            if self._write_charset(path):
                self._clear_dirty()
            self._update_title()

    def _write_charset(self, path: str) -> bool:
        try:
            with open(path, "wb") as handle:
                handle.write(self.charset_bytes)
        except OSError as exc:
            self.logger.error("Failed to save charset: %s", exc)
            messagebox.showerror("Save failed", str(exc))
            return False
        return True

    def save_tset(self) -> bool:
        if not self.current_tset_path or not self.current_tset:
            messagebox.showwarning("Save failed", "No TSET loaded.")
            return False
        self.logger.info("Saving TSET to %s", self.current_tset_path)
        try:
            with open(self.current_tset_path, "w", encoding="utf-8") as handle:
                handle.write(self._serialize_tset())
        except OSError as exc:
            self.logger.error("Failed to save TSET: %s", exc)
            messagebox.showerror("Save failed", str(exc))
            return False
        self._clear_tset_dirty()
        return True

    def save_tset_as(self) -> bool:
        if not self.current_tset:
            messagebox.showwarning("Save failed", "No TSET loaded.")
            return False
        path = filedialog.asksaveasfilename(
            title="Save TSET As",
            defaultextension=".tset",
            filetypes=[("Tileset", "*.tset"), ("All files", "*.*")],
        )
        if not path:
            return False
        self.logger.info("Save TSET as %s", path)
        self.current_tset_path = path
        if self.save_tset():
            self._update_title()
            return True
        return False

    def _update_title(self) -> None:
        name = os.path.basename(self.current_file) if self.current_file else "Untitled"
        dirty_marker = "*" if (self.dirty or self.tset_dirty) else ""
        if self.current_tset:
            tset_name = os.path.basename(self.current_tset_path or "")
            self.root.title(f"C64 Charset Viewer - {tset_name} ({name}){dirty_marker}")
        else:
            self.root.title(f"C64 Charset Viewer - {name}{dirty_marker}")

    def _enforce_min_size(self) -> None:
        grid_size = 16 * 8 * self.grid_scale
        self.root.update_idletasks()
        controls_h = self.controls_frame.winfo_reqheight() if hasattr(self, "controls_frame") else 0
        status_h = self.status_label.winfo_reqheight() if hasattr(self, "status_label") else 0
        right_w = 420
        min_w = max(self.root.winfo_reqwidth(), grid_size + right_w)
        min_h = max(self.root.winfo_reqheight(), grid_size + controls_h + status_h + 20)
        self.root.minsize(min_w, min_h)
        if hasattr(self, "left_frame"):
            self.left_frame.configure(width=grid_size, height=grid_size)
        if hasattr(self, "charset_tabs"):
            self.charset_tabs.configure(width=grid_size, height=grid_size)
        if hasattr(self, "grid_canvases"):
            for canvas in self.grid_canvases:
                canvas.configure(width=grid_size, height=grid_size)

    def _clear_tiles_objects(self) -> None:
        self.tiles_canvas.delete("all")
        self.objects_canvas.delete("all")
        self._update_tiles_status(None)
        self.objects_status.configure(text="No objects loaded.")
        if hasattr(self, "object_preview_canvas"):
            self.object_preview_canvas.delete("all")
            self.object_preview_image_id = self.object_preview_canvas.create_image(0, 0, anchor="nw")
        self.tile_images = []
        self.object_images = []
        self.tile_entries = []
        self.object_entries = []
        self.tile_entry_by_id = {}
        self.char_to_tiles = {}
        self._pending_tile_update_ids = set()
        if self._tile_update_after_id is not None:
            self.root.after_cancel(self._tile_update_after_id)
            self._tile_update_after_id = None
        if self._objects_redraw_after_id is not None:
            self.root.after_cancel(self._objects_redraw_after_id)
            self._objects_redraw_after_id = None
        if self._refresh_selected_after_id is not None:
            self.root.after_cancel(self._refresh_selected_after_id)
            self._refresh_selected_after_id = None
        self.selected_tile = None
        self.selected_object = None
        if hasattr(self, "tile_hint_label"):
            self.tile_hint_label.configure(text="Hint: -")

    def _draw_tiles_grid(self) -> None:
        self._profile_start("tiles.draw")
        if not self.current_tset or not self.charset_bytes:
            self._clear_tiles_objects()
            self._profile_end("tiles.draw")
            return
        if self._tile_update_after_id is not None:
            self.root.after_cancel(self._tile_update_after_id)
            self._tile_update_after_id = None
        self._pending_tile_update_ids.clear()
        tiles = [self.current_tset.tiles[tid] for tid in sorted(self.current_tset.tiles)]
        self.tiles_canvas.delete("all")
        self.tile_images = []
        self.tile_entries = []
        self.tile_entry_by_id = {}
        self.char_to_tiles = {}
        selected_id = self.selected_tile

        cell_size = 16 * self.tile_scale
        columns = self.tile_columns
        rows = int(math.ceil(len(tiles) / columns))
        width = columns * cell_size
        height = rows * cell_size

        for index, tile in enumerate(tiles):
            for ch in tile.chars:
                self.char_to_tiles.setdefault(ch, []).append(tile.tid)
            col = index % columns
            row = index // columns
            x = col * cell_size
            y = row * cell_size
            image = self._render_tile_image(tile, self.tile_scale)
            self.tile_images.append(image)
            image_id = self.tiles_canvas.create_image(x, y, anchor="nw", image=image)
            bbox = (x, y, x + cell_size, y + cell_size)
            rect_id = self.tiles_canvas.create_rectangle(*bbox, outline="#333333")
            entry = {
                "id": tile.tid,
                "name": tile.name,
                "bbox": bbox,
                "image_id": image_id,
                "rect_id": rect_id,
                "tile_index": index,
            }
            self.tile_entries.append(entry)
            self.tile_entry_by_id[tile.tid] = entry
            if self.selected_index in tile.chars:
                half = cell_size // 2
                inset = max(1, self.tile_scale // 2)
                for idx, char_index in enumerate(tile.chars):
                    if char_index != self.selected_index:
                        continue
                    qx = x + (0 if idx % 2 == 0 else half)
                    qy = y + (0 if idx < 2 else half)
                    self.tiles_canvas.create_rectangle(
                        qx + inset,
                        qy + inset,
                        qx + half - inset,
                        qy + half - inset,
                        outline="#00FFAA",
                        width=2,
                    )

        self.tiles_selection_rect = self.tiles_canvas.create_rectangle(
            0, 0, cell_size, cell_size, outline="#FFFF00", width=2
        )
        self.tiles_canvas.itemconfigure(self.tiles_selection_rect, state="hidden")
        self.tiles_canvas.configure(scrollregion=(0, 0, width, height))
        self._update_tiles_status(len(tiles))
        if selected_id is not None and selected_id in self.current_tset.tiles:
            for entry in self.tile_entries:
                if entry["id"] == selected_id:
                    self.selected_tile = selected_id
                    self._update_tile_selection(entry)
                    self._load_tile_editor(self.current_tset.tiles[selected_id])
                    break
        else:
            self.selected_tile = None
        self._profile_end("tiles.draw")

    def _draw_objects_grid(self) -> None:
        self._profile_start("objects.draw")
        if not self.current_tset or not self.charset_bytes:
            self._clear_tiles_objects()
            self._profile_end("objects.draw")
            return
        objects = [self.current_tset.objects[name] for name in sorted(self.current_tset.objects)]
        self.objects_canvas.delete("all")
        self.object_images = []
        self.object_entries = []
        self.selected_object = None

        columns = 1
        padding = 8
        x = padding
        y = padding
        max_row_height = 0
        canvas_width = 0

        for obj in objects:
            image = self._render_object_image(obj, self.object_scale)
            self.object_images.append(image)
            w = image.width()
            h = image.height()
            self.objects_canvas.create_image(x, y, anchor="nw", image=image)
            bbox = (x, y, x + w, y + h)
            self.object_entries.append({"name": obj.name, "bbox": bbox})
            self.objects_canvas.create_rectangle(*bbox, outline="#333333")
            max_row_height = max(max_row_height, h)
            canvas_width = max(canvas_width, w + padding * 2)

            if (len(self.object_entries) % columns) == 0:
                x = padding
                y += max_row_height + padding
                max_row_height = 0
            else:
                x += w + padding

        height = y + max_row_height + padding
        self.objects_selection_rect = self.objects_canvas.create_rectangle(
            0, 0, 10, 10, outline="#FFFF00", width=2
        )
        self.objects_canvas.itemconfigure(self.objects_selection_rect, state="hidden")
        if canvas_width == 0:
            canvas_width = 16 * self.object_scale + padding * 2
        self.objects_canvas.configure(scrollregion=(0, 0, canvas_width, height))
        self.objects_status.configure(text=f"{len(objects)} objects loaded.")
        if hasattr(self, "object_preview_canvas"):
            self.object_preview_canvas.delete("all")
            self.object_preview_image_id = self.object_preview_canvas.create_image(0, 0, anchor="nw")
            self.object_preview_canvas.configure(width=1, height=1)
        if hasattr(self, "object_name_var"):
            self._load_object_editor(None)
        self._profile_end("objects.draw")

    def _render_tile_image(self, tile, scale: int) -> tk.PhotoImage:
        rows = self._render_tile_rows(tile)
        width = 16 * scale
        height = 16 * scale
        image = tk.PhotoImage(width=width, height=height)
        for y, row in enumerate(rows):
            expanded_row = []
            for color in row:
                expanded_row.extend([color] * scale)
            row_data = "{" + " ".join(expanded_row) + "}"
            for sy in range(scale):
                image.put(row_data, to=(0, y * scale + sy))
        return image

    def _render_object_image(self, obj, scale: int) -> tk.PhotoImage:
        tile_rows = []
        tiles = obj.tiles
        for ty in range(obj.h):
            row_tiles = tiles[ty * obj.w : (ty + 1) * obj.w]
            row_rows = []
            for tile_name in row_tiles:
                tile_id = self.current_tset.tiles_by_name[tile_name]
                row_rows.append(self._render_tile_rows(self.current_tset.tiles[tile_id]))
            for inner_row in range(16):
                row = []
                for tile_row in row_rows:
                    row.extend(tile_row[inner_row])
                tile_rows.append(row)
        width = 16 * obj.w * scale
        height = 16 * obj.h * scale
        image = tk.PhotoImage(width=width, height=height)
        for y, row in enumerate(tile_rows):
            expanded_row = []
            for color in row:
                expanded_row.extend([color] * scale)
            row_data = "{" + " ".join(expanded_row) + "}"
            for sy in range(scale):
                image.put(row_data, to=(0, y * scale + sy))
        return image

    def _render_tile_rows(self, tile) -> list:
        colors = self._current_colors()
        fg_colors = tile.colors if tile.color_mode == 1 else [tile.colors[0]] * 4
        char_indices = tile.chars
        quadrant_rows = []
        for quadrant in range(4):
            fg_hex = self._color_hex_by_index(fg_colors[quadrant])
            quadrant_rows.append(
                self._char_to_rows(
                    self._char_bytes(char_indices[quadrant]),
                    self.mode_var.get(),
                    {**colors, "fg": fg_hex},
                )
            )

        rows = []
        for y in range(16):
            top = y < 8
            row = []
            for x in range(16):
                left = x < 8
                quadrant = (0 if top else 2) + (0 if left else 1)
                row.append(quadrant_rows[quadrant][y % 8][x % 8])
            rows.append(row)
        return rows

    def _update_tile_selection(self, entry: dict) -> None:
        x0, y0, x1, y1 = entry["bbox"]
        self.tiles_canvas.coords(self.tiles_selection_rect, x0, y0, x1, y1)
        self.tiles_canvas.itemconfigure(self.tiles_selection_rect, state="normal")
        self.tiles_canvas.tag_raise(self.tiles_selection_rect)
        self._update_tiles_status()
        self._update_tile_highlights()
        self._update_tile_preview()

    def _update_tile_highlights(self) -> None:
        for page, canvas in enumerate(self.grid_canvases):
            for rect in self.tile_selection_rects[page]:
                if rect:
                    canvas.itemconfigure(rect, state="hidden")
        if not self.current_tset or self.selected_tile is None:
            for page, canvas in enumerate(self.grid_canvases):
                selection_rect = self.selection_rects[page]
                if selection_rect:
                    canvas.tag_raise(selection_rect)
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if not tile:
            for page, canvas in enumerate(self.grid_canvases):
                selection_rect = self.selection_rects[page]
                if selection_rect:
                    canvas.tag_raise(selection_rect)
            return
        cell_size = 8 * self.grid_scale
        for idx, char_index in enumerate(tile.chars):
            page = char_index // self.page_chars
            local = char_index % self.page_chars
            col = local % self.columns
            row = local // self.columns
            x0 = col * cell_size
            y0 = row * cell_size
            x1 = x0 + cell_size
            y1 = y0 + cell_size
            if page < len(self.grid_canvases):
                rect = self.tile_selection_rects[page][idx]
                self.grid_canvases[page].coords(rect, x0, y0, x1, y1)
                self.grid_canvases[page].itemconfigure(rect, state="normal")
                self.grid_canvases[page].tag_raise(rect)
        for page, canvas in enumerate(self.grid_canvases):
            selection_rect = self.selection_rects[page]
            if selection_rect:
                canvas.tag_raise(selection_rect)

    def _update_object_selection(self, entry: dict) -> None:
        x0, y0, x1, y1 = entry["bbox"]
        self.objects_canvas.coords(self.objects_selection_rect, x0, y0, x1, y1)
        self.objects_canvas.itemconfigure(self.objects_selection_rect, state="normal")
        self.objects_canvas.tag_raise(self.objects_selection_rect)
        obj = None
        if self.current_tset:
            obj = self.current_tset.objects.get(entry["name"].upper())
        if obj:
            self.objects_status.configure(text="Object selected")
            if hasattr(self, "object_preview_canvas"):
                image = self._render_object_image(obj, self.object_scale * 4)
                self.object_preview_image = image
                self.object_preview_canvas.delete("all")
                self.object_preview_canvas.configure(width=image.width(), height=image.height())
                self.object_preview_canvas.create_image(0, 0, anchor="nw", image=image)
            self._load_object_editor(obj)
        else:
            self.objects_status.configure(text=f"Object {entry['name']}")
            if hasattr(self, "object_preview_canvas"):
                self.object_preview_canvas.delete("all")
                self.object_preview_image_id = self.object_preview_canvas.create_image(0, 0, anchor="nw")
            self._load_object_editor(None)

    def _load_object_editor(self, obj) -> None:
        self._loading_object_editor = True
        if obj is None:
            self.object_name_var.set("")
            self.object_char_var.set("")
            self._loading_object_editor = False
            return
        self.object_name_var.set(obj.name)
        self.object_char_var.set(obj.char or "")
        self._loading_object_editor = False

    def _commit_object_name(self) -> None:
        if self._loading_object_editor:
            return
        if not self.current_tset or not self.selected_object:
            return
        obj = self.current_tset.objects.get(self.selected_object.upper())
        if obj is None:
            return
        new_name = self.object_name_var.get().strip()
        if not new_name:
            return
        new_key = new_name.upper()
        old_key = obj.name.upper()
        if new_key != old_key and new_key in self.current_tset.objects:
            messagebox.showwarning("Invalid name", "Object name must be unique.")
            self.object_name_var.set(obj.name)
            return
        if new_key != old_key:
            del self.current_tset.objects[old_key]
            self.current_tset.objects[new_key] = obj
            obj.name = new_name
            self.selected_object = new_name
            if obj.char:
                stamp = self.current_tset.object_stamps.get(obj.char)
                if stamp:
                    stamp["name"] = new_name
            self._mark_tset_dirty()
            self._draw_objects_grid()

    def _commit_object_char(self) -> None:
        if self._loading_object_editor:
            return
        if not self.current_tset or not self.selected_object:
            return
        obj = self.current_tset.objects.get(self.selected_object.upper())
        if obj is None:
            return
        new_char = self.object_char_var.get().strip()
        if new_char == "":
            if obj.char and obj.char in self.current_tset.object_stamps:
                del self.current_tset.object_stamps[obj.char]
            obj.char = None
            self._mark_tset_dirty()
            return
        new_char = new_char[0]
        existing = self.current_tset.object_stamps.get(new_char)
        if existing and existing.get("name", "").upper() != obj.name.upper():
            messagebox.showwarning("Invalid char", "That char is already assigned to another object.")
            self.object_char_var.set(obj.char or "")
            return
        if obj.char and obj.char in self.current_tset.object_stamps:
            del self.current_tset.object_stamps[obj.char]
        obj.char = new_char
        tile_ids = [self.current_tset.tiles_by_name[n] for n in obj.tiles]
        self.current_tset.object_stamps[new_char] = {
            "name": obj.name,
            "w": obj.w,
            "h": obj.h,
            "tiles": tile_ids,
            "char": new_char,
        }
        self._mark_tset_dirty()


def main() -> None:
    profile_enabled = False
    env_flag = os.getenv("C64_PROFILE", "").strip().lower()
    if env_flag in ("1", "true", "yes", "on"):
        profile_enabled = True
    profile_log_path = os.getenv("C64_PROFILE_OUT")
    if "--profile" in sys.argv:
        profile_enabled = True
    for arg in sys.argv:
        if arg.startswith("--profile-out="):
            profile_log_path = arg.split("=", 1)[1]
    root = tk.Tk()
    if profile_enabled and not profile_log_path:
        profile_log_path = os.path.abspath("./profile.log")
    app = CharsetApp(root, profile_enabled=profile_enabled, profile_log_path=profile_log_path)
    root.geometry("1000x700")
    root.mainloop()


if __name__ == "__main__":
    main()
