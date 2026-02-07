import json
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tset_parser import TileDef, TilesetParseError, parse_tset
except ImportError:
    TileDef = None
    TilesetParseError = Exception
    parse_tset = None


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
    def __init__(self, root: tk.Tk) -> None:
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
        self._loading_tile_editor = False
        self.swatch_enabled = {}
        self.tile_flag_vars = {}

        self.grid_scale = 3
        self.preview_scale = 16
        self.charset_columns = 16
        self.columns = self.charset_columns
        self.page_chars = 256
        self.total_chars = 0
        self.has_second_tab = True
        self.selection_rects = [None, None]
        self.tile_selection_rects = [[None, None, None, None], [None, None, None, None]]
        self.tile_scale = 3
        self.tile_columns = 4
        self.object_scale = 2
        self.object_columns = 2

        self.mode_var = tk.StringVar(value="hires")
        self.bg_var = tk.StringVar(value="Black")
        self.fg_var = tk.StringVar(value="White")
        self.mc1_var = tk.StringVar(value="Light Red")
        self.mc2_var = tk.StringVar(value="Light Green")

        self.selected_index = 0
        self.selected_tile = None
        self.selected_object = None
        self.paint_value = None
        self.tile_images = []
        self.object_images = []
        self.tile_entries = []
        self.object_entries = []

        self._build_menu()
        self._build_layout()
        self._bind_events()
        self._load_recent()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.mode_var.trace_add("write", lambda *_: self._update_color_states())
        self._enforce_min_size()


    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
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

        self.left_frame = tk.Frame(self.content_frame)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        self.left_frame.pack_propagate(False)

        right = tk.Frame(self.content_frame, padx=10, pady=10)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

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

        tile_editor_frame = tk.LabelFrame(editor_row, text="Tile Editor")
        tile_editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        self._build_tile_editor(tile_editor_frame)

        browser_frame = tk.LabelFrame(right_stack, text="Tiles and Objects")

        self.browser_tabs = ttk.Notebook(browser_frame)
        self.browser_tabs.pack(fill=tk.BOTH, expand=True)

        tiles_tab = tk.Frame(self.browser_tabs)
        objects_tab = tk.Frame(self.browser_tabs)
        self.browser_tabs.add(tiles_tab, text="Tiles")
        self.browser_tabs.add(objects_tab, text="Objects")

        self.tiles_view = tk.Frame(tiles_tab)
        self.tiles_view.grid(row=0, column=0, sticky="nsew")
        self.tiles_view.grid_propagate(False)
        self.tiles_view.configure(width=16 * self.tile_scale * self.tile_columns + 20)
        self.tiles_canvas = tk.Canvas(self.tiles_view, background="#0f0f0f")
        self.tiles_canvas.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        tiles_scroll = tk.Scrollbar(self.tiles_view, orient=tk.VERTICAL, command=self.tiles_canvas.yview)
        self.tiles_canvas.configure(yscrollcommand=tiles_scroll.set)
        tiles_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tiles_scrollbar = tiles_scroll

        tiles_info = tk.Frame(tiles_tab, padx=8)
        tiles_info.grid(row=0, column=1, sticky="nsew")
        self.tiles_status = tk.Label(tiles_info, text="No tiles loaded.", anchor="w")
        self.tiles_status.pack(fill=tk.X)
        self.tile_flags_frame = tk.Frame(tiles_info)
        self.tile_flags_frame.pack(fill=tk.X, pady=(4, 2))
        tk.Label(self.tile_flags_frame, text="Flags:").pack(side=tk.LEFT, padx=(0, 6))
        self.tile_flags_placeholder = tk.Label(self.tile_flags_frame, text="(no tileset loaded)")
        self.tile_flags_placeholder.pack(side=tk.LEFT)
        tiles_tab.columnconfigure(0, weight=0)
        tiles_tab.columnconfigure(1, weight=1)
        tiles_tab.rowconfigure(0, weight=1)

        self.objects_view = tk.Frame(objects_tab)
        self.objects_view.pack(side=tk.TOP, fill=tk.BOTH, expand=False)
        self.objects_view.pack_propagate(True)
        self.objects_canvas = tk.Canvas(self.objects_view, background="#0f0f0f")
        self.objects_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        objects_scroll = tk.Scrollbar(
            self.objects_view, orient=tk.VERTICAL, command=self.objects_canvas.yview
        )
        self.objects_canvas.configure(yscrollcommand=objects_scroll.set)
        objects_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.objects_scrollbar = objects_scroll
        self.objects_status = tk.Label(objects_tab, text="No objects loaded.")
        self.objects_status.pack(fill=tk.X)

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
        swatch = tk.Canvas(parent, width=12, height=12, highlightthickness=0)
        swatch.pack(side=tk.LEFT)
        rect = swatch.create_rectangle(1, 1, 11, 11, outline="#333333", fill=self._color_hex(var.get()))
        swatch._rect_id = rect
        self._set_swatch_enabled(swatch, True)
        swatch.bind("<Button-1>", lambda _e: self._on_swatch_click(swatch, var))
        var.trace_add("write", lambda *_: swatch.itemconfigure(rect, fill=self._color_hex(var.get())))
        return swatch

    def _build_tile_color_swatch(self, parent: tk.Widget, var: tk.StringVar) -> tk.Canvas:
        swatch = tk.Canvas(parent, width=12, height=12, highlightthickness=0)
        rect = swatch.create_rectangle(1, 1, 11, 11, outline="#333333", fill=self._color_hex(var.get()))
        swatch._rect_id = rect
        swatch.bind("<Button-1>", lambda _e: self._open_color_palette(var))
        var.trace_add("write", lambda *_: swatch.itemconfigure(rect, fill=self._color_hex(var.get())))
        return swatch

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
        var.set(name)
        self._on_color_change()
        dialog.destroy()

    def _build_tile_editor(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent)
        header.pack(fill=tk.X, pady=(2, 6))
        self.tile_id_var = tk.StringVar(value="-")
        self.tile_name_var = tk.StringVar(value="")
        name_entry = tk.Entry(header, textvariable=self.tile_name_var, width=28)
        name_entry.pack(side=tk.LEFT, padx=(4, 6))
        self.tile_color_mode_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            header,
            text="Per-quadrant colors",
            variable=self.tile_color_mode_var,
        ).pack(side=tk.LEFT, padx=(8, 0))
        self.tile_color_mode_var.trace_add("write", lambda *_: self._update_tile_preview())
        self.tile_color_mode_var.trace_add("write", lambda *_: self._sync_tile_from_editor(update_name=False))

        self.tile_char_vars = []
        self.tile_color_vars = []
        self.tile_hex_labels = []
        self.tile_selected_quadrant = 0
        preview_row = tk.Frame(parent)
        preview_row.pack(fill=tk.X, pady=(4, 6))
        self.tile_preview_size = 128
        self.tile_preview_canvas = tk.Canvas(
            preview_row, width=self.tile_preview_size, height=self.tile_preview_size, background="#111111"
        )
        self.tile_preview_canvas.pack(side=tk.LEFT, padx=(4, 8))
        self.tile_preview_canvas.bind("<Button-1>", self._on_tile_preview_click)

        selectors = tk.Frame(preview_row)
        selectors.pack(side=tk.LEFT)
        labels = ["TL", "TR", "BL", "BR"]
        for idx in range(4):
            cell = tk.LabelFrame(selectors, text=labels[idx])
            cell.grid(row=idx // 2, column=idx % 2, padx=4, pady=4, sticky="nsew")
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

        actions = tk.Frame(parent)
        actions.pack(fill=tk.X, pady=(4, 6))
        tk.Button(actions, text="New", command=self._new_tile).pack(side=tk.LEFT)
        tk.Button(actions, text="Duplicate", command=self._duplicate_tile).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(actions, text="Delete", command=self._delete_tile).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(actions, text="Edit Flags...", command=self._open_flags_modal).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        tk.Button(actions, text="Apply", command=self._apply_tile_edits).pack(side=tk.RIGHT)

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

    def _on_tile_preview_click(self, event: tk.Event) -> None:
        size = self.tile_preview_size
        if not (0 <= event.x < size and 0 <= event.y < size):
            return
        col = 0 if event.x < size / 2 else 1
        row = 0 if event.y < size / 2 else 1
        self.tile_selected_quadrant = row * 2 + col
        self._update_tile_preview()


    def _load_tile_editor(self, tile) -> None:
        self._loading_tile_editor = True
        self.tile_id_var.set(str(tile.tid))
        self.tile_name_var.set(tile.name)
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
        self._sync_tile_from_editor(update_name=True)

    def _sync_tile_from_editor(self, update_name: bool) -> None:
        if self._loading_tile_editor:
            return
        if not self.current_tset or self.selected_tile is None:
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if tile is None:
            return

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

        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        if update_name:
            self._load_tile_editor(tile)

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
        )
        self.current_tset.tiles[tid] = tile
        self.current_tset.tiles_by_name[name.upper()] = tid
        self.selected_tile = tid
        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._load_tile_editor(tile)

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
        )
        self.current_tset.tiles[tid] = tile
        self.current_tset.tiles_by_name[name.upper()] = tid
        self.selected_tile = tid
        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._load_tile_editor(tile)

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
        self._mark_tset_dirty()
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._load_tile_editor(self.current_tset.tiles[default_id])

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
            self._update_tile_flags_display()
            return
        self.tile_flag_vars = {}
        for name, bit in sorted(self.current_tset.flagbits.items(), key=lambda item: item[1]):
            self.tile_flag_vars[name] = (tk.IntVar(value=0), bit)

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
        if not self.current_tset or self.selected_tile is None:
            self.tile_flags_placeholder.configure(text="(no tileset loaded)")
            return
        if not self.current_tset.tiles.get(self.selected_tile):
            self.tile_flags_placeholder.configure(text="(no tile selected)")
            return
        self.tile_flags_placeholder.configure(text="")
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
            return
        for name in labels:
            tk.Label(self.tile_flags_frame, text=name).pack(anchor="w")

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
            canvas.bind("<Button-1>", self._on_grid_click)
        self.charset_tabs.bind("<<NotebookTabChanged>>", self._on_charset_tab_change)
        self.preview_canvas.bind("<Button-1>", self._on_preview_click)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)
        self.tiles_canvas.bind("<Button-1>", self._on_tile_click)
        self.objects_canvas.bind("<Button-1>", self._on_object_click)
        self.tiles_canvas.bind("<MouseWheel>", self._on_tiles_wheel)
        self.objects_canvas.bind("<MouseWheel>", self._on_objects_wheel)

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
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            messagebox.showerror("Open failed", str(exc))
            return

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
        self.current_file = path
        self.selected_index = 0
        if add_recent:
            self._add_recent(path)
        if not keep_tset:
            self.current_tset = None
            self.current_tset_path = None
            self.current_tset_charset = None
            self.mode_var.set("hires")
            self.bg_var.set("Black")
            self.fg_var.set("White")
            self.mc1_var.set("Light Red")
            self.mc2_var.set("Light Green")
            self._init_flag_vars(clear=True)
        self.dirty = False
        self._update_title()
        self._draw_grid()
        self.refresh_selected()
        if not keep_tset:
            self._clear_tiles_objects()

    def load_tset(self, path: str, add_recent: bool = True) -> None:
        if parse_tset is None:
            messagebox.showerror("Open failed", "tset_parser is not available.")
            return
        try:
            tset = parse_tset(path)
        except TilesetParseError as exc:
            messagebox.showerror(
                "Open failed",
                f"{exc.path}:{exc.line}:{exc.col} {exc.message}",
            )
            return
        self.current_tset = tset
        self.current_tset_path = path
        self.current_tset_charset = self._resolve_tset_charset(path, tset.charset_path)
        self.tset_dirty = False
        self._init_flag_vars(clear=True)
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
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self._update_title()

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

    def refresh_selected(self) -> None:
        if not self.charset_bytes:
            self.status_label.configure(text="No charset loaded.")
            return
        if self.selected_index >= self.total_chars:
            self.selected_index = 0
        image = self._render_char_image(self.selected_index, self.preview_scale)
        self.preview_image = image
        self.preview_canvas.itemconfigure(self.preview_image_id, image=image)
        self._update_selection_rect()
        dirty_marker = " *" if self.dirty else ""
        self.status_label.configure(
            text=f"Char {self.selected_index:03d} (0x{self.selected_index:02X}){dirty_marker}"
        )

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
        canvas.tag_raise(selection_rect)
        self._update_tile_highlights()

    def _on_grid_click(self, event: tk.Event) -> None:
        if not self.charset_bytes:
            return
        canvas = event.widget
        page = 0 if canvas == self.grid_canvases[0] else 1
        if page == 1 and self.total_chars <= self.page_chars:
            return
        x = int(canvas.canvasx(event.x))
        y = int(canvas.canvasy(event.y))
        cell_size = 8 * self.grid_scale
        col = x // cell_size
        row = y // cell_size
        index = row * self.columns + col
        if 0 <= index < self.page_chars:
            self.selected_index = page * self.page_chars + index
            self.refresh_selected()

    def _on_preview_click(self, event: tk.Event) -> None:
        if not self.charset_bytes:
            return
        row, col = self._preview_to_cell(event.x, event.y)
        if row is None or col is None:
            return
        current = self._get_pixel_value(self.selected_index, row, col)
        if self.mode_var.get() == "multicolor":
            self.paint_value = (current + 1) % 4
        else:
            self.paint_value = 0 if current else 1
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
            self._mark_dirty()

    def _apply_paint(self, row: int, col: int) -> None:
        value = self.paint_value
        if value is None:
            return
        self._set_pixel_value(self.selected_index, row, col, value)
        self._update_char_image(self.selected_index)
        self._draw_tiles_grid()
        self._draw_objects_grid()
        self.refresh_selected()

    def _update_char_image(self, index: int) -> None:
        page = index // self.page_chars
        local = index % self.page_chars
        if page >= len(self.char_images):
            return
        image = self._render_char_image(index, self.grid_scale)
        if local >= len(self.char_images[page]):
            return
        self.char_images[page][local] = image
        self.grid_canvases[page].itemconfigure(self.char_image_items[page][local], image=image)

    def _on_tile_click(self, event: tk.Event) -> None:
        if not self.tile_entries:
            return
        x = int(self.tiles_canvas.canvasx(event.x))
        y = int(self.tiles_canvas.canvasy(event.y))
        for entry in self.tile_entries:
            x0, y0, x1, y1 = entry["bbox"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.selected_tile = entry["id"]
                self._update_tile_selection(entry)
                if self.current_tset and entry["id"] in self.current_tset.tiles:
                    self._load_tile_editor(self.current_tset.tiles[entry["id"]])
                return

    def _on_object_click(self, event: tk.Event) -> None:
        if not self.object_entries:
            return
        x = int(self.objects_canvas.canvasx(event.x))
        y = int(self.objects_canvas.canvasy(event.y))
        for entry in self.object_entries:
            x0, y0, x1, y1 = entry["bbox"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.selected_object = entry["name"]
                self._update_object_selection(entry)
                return

    def _on_color_change(self) -> None:
        self.refresh_all()

    def _on_charset_tab_change(self, event: tk.Event) -> None:
        page = self.charset_tabs.index("current")
        if page == 1 and self.total_chars <= self.page_chars:
            return
        self.selected_index = page * self.page_chars + (self.selected_index % self.page_chars)
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

    def open_charset(self) -> None:
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            title="Open Charset",
            filetypes=[("Charset binary", "*.bin"), ("All files", "*.*")],
        )
        if path:
            keep_tset = self.current_tset is not None
            self.load_charset(path, keep_tset=keep_tset)

    def open_tset(self) -> None:
        if not self._confirm_discard_changes():
            return
        path = filedialog.askopenfilename(
            title="Open TSET",
            filetypes=[("Tileset", "*.tset"), ("All files", "*.*")],
        )
        if path:
            self.load_tset(path)

    def save_file(self) -> None:
        if not self.current_file:
            self.save_file_as()
            return
        if self._write_charset(self.current_file):
            self._clear_dirty()

    def save_file_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save Charset As",
            defaultextension=".bin",
            filetypes=[("Charset binary", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.current_file = path
            if self._write_charset(path):
                self._clear_dirty()
            self._update_title()

    def _write_charset(self, path: str) -> bool:
        try:
            with open(path, "wb") as handle:
                handle.write(self.charset_bytes)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
        return True

    def save_tset(self) -> bool:
        if not self.current_tset_path or not self.current_tset:
            messagebox.showwarning("Save failed", "No TSET loaded.")
            return False
        try:
            with open(self.current_tset_path, "w", encoding="utf-8") as handle:
                handle.write(self._serialize_tset())
        except OSError as exc:
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
        self.tile_images = []
        self.object_images = []
        self.tile_entries = []
        self.object_entries = []
        self.selected_tile = None
        self.selected_object = None

    def _draw_tiles_grid(self) -> None:
        if not self.current_tset or not self.charset_bytes:
            self._clear_tiles_objects()
            return
        tiles = [self.current_tset.tiles[tid] for tid in sorted(self.current_tset.tiles)]
        self.tiles_canvas.delete("all")
        self.tile_images = []
        self.tile_entries = []
        selected_id = self.selected_tile

        cell_size = 16 * self.tile_scale
        columns = self.tile_columns
        rows = int(math.ceil(len(tiles) / columns))
        width = columns * cell_size
        height = rows * cell_size

        for index, tile in enumerate(tiles):
            col = index % columns
            row = index // columns
            x = col * cell_size
            y = row * cell_size
            image = self._render_tile_image(tile, self.tile_scale)
            self.tile_images.append(image)
            self.tiles_canvas.create_image(x, y, anchor="nw", image=image)
            bbox = (x, y, x + cell_size, y + cell_size)
            self.tile_entries.append({"id": tile.tid, "name": tile.name, "bbox": bbox})
            self.tiles_canvas.create_rectangle(*bbox, outline="#333333")

        self.tiles_selection_rect = self.tiles_canvas.create_rectangle(
            0, 0, cell_size, cell_size, outline="#FFFF00", width=2
        )
        self.tiles_canvas.itemconfigure(self.tiles_selection_rect, state="hidden")
        self.tiles_canvas.configure(scrollregion=(0, 0, width, height), width=width)
        if hasattr(self, "tiles_view"):
            scrollbar_width = self.tiles_scrollbar.winfo_reqwidth() if hasattr(self, "tiles_scrollbar") else 16
            self.tiles_view.configure(width=width + scrollbar_width)
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

    def _draw_objects_grid(self) -> None:
        if not self.current_tset or not self.charset_bytes:
            self._clear_tiles_objects()
            return
        objects = [self.current_tset.objects[name] for name in sorted(self.current_tset.objects)]
        self.objects_canvas.delete("all")
        self.object_images = []
        self.object_entries = []
        self.selected_object = None

        columns = self.object_columns
        padding = 8
        x = padding
        y = padding
        max_row_height = 0
        canvas_width = columns * (16 * self.object_scale + padding * 2)

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
        self.objects_canvas.configure(scrollregion=(0, 0, canvas_width, height))
        if hasattr(self, "objects_view"):
            self.objects_view.configure(width=canvas_width + 16)
        self.objects_status.configure(text=f"{len(objects)} objects loaded.")

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

    def _update_tile_highlights(self) -> None:
        for page, canvas in enumerate(self.grid_canvases):
            for rect in self.tile_selection_rects[page]:
                if rect:
                    canvas.itemconfigure(rect, state="hidden")
        if not self.current_tset or self.selected_tile is None:
            return
        tile = self.current_tset.tiles.get(self.selected_tile)
        if not tile:
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

    def _update_object_selection(self, entry: dict) -> None:
        x0, y0, x1, y1 = entry["bbox"]
        self.objects_canvas.coords(self.objects_selection_rect, x0, y0, x1, y1)
        self.objects_canvas.itemconfigure(self.objects_selection_rect, state="normal")
        self.objects_canvas.tag_raise(self.objects_selection_rect)
        self.objects_status.configure(
            text=f"Object {entry['name']}"
        )


def main() -> None:
    root = tk.Tk()
    app = CharsetApp(root)
    root.geometry("1000x700")
    root.mainloop()


if __name__ == "__main__":
    main()
