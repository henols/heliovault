import json
import os
import re
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

try:
    from tset_parser import parse_tset
except ImportError:
    parse_tset = None


@dataclass
class ScriptEntry:
    name: str
    kind: str
    start: int
    end: int
    lines: list[str]


@dataclass
class ObjectEntry:
    name: str
    x: int
    y: int
    type_name: str
    verbs: str
    cond: str
    props: dict
    line_index: int


@dataclass
class RoomEntry:
    rid: str
    name: str
    start: int
    end: int
    map_start: Optional[int]
    map_end: Optional[int]
    map_lines: list[str]
    objects: list[ObjectEntry]
    spawns: dict
    exits: list


@dataclass
class LevelState:
    level_line: Optional[int]
    level_tset: Optional[str]
    width: Optional[int]
    height: Optional[int]
    flags: list[str]
    vars: list[str]
    items: list[str]
    messages: list[tuple]
    sections: dict
    conds: list[ScriptEntry]
    acts: list[ScriptEntry]
    rooms: list[RoomEntry]


OBJ_TYPES = [
    "SIGN",
    "PICKUP",
    "LOCKER_KEYPAD",
    "BREAKER_PANEL",
    "HATCH_PANEL",
    "EXIT_TRIGGER",
    "NPC_INTERCOM",
]

TOKEN_KV = re.compile(r'(\w+)=(".*?"|\S+)')

OBJECT_TEMPLATES = {
    "Custom": {},
    "SIGN": {"type": "SIGN", "verbs": "LOOK", "props": {"look": "LOOK_SIGN"}},
    "PICKUP": {"type": "PICKUP", "verbs": "TAKE", "props": {"item": "ITEM_ID", "take": "TAKE_ITEM"}},
    "LOCKER_KEYPAD": {"type": "LOCKER_KEYPAD", "verbs": "LOOK|OPERATE", "props": {"code": "123", "ok": "LOCKER_OK", "bad": "LOCKER_BAD"}},
    "BREAKER_PANEL": {"type": "BREAKER_PANEL", "verbs": "OPERATE", "props": {"var": "RELAY_BITS", "expect": "0b000", "ok": "RELAY_OK", "bad": "RELAY_BAD"}},
    "HATCH_PANEL": {"type": "HATCH_PANEL", "verbs": "LOOK|USE", "props": {"fuse": "INSERT_FUSE", "badge": "SWIPE_BADGE", "reject": "NO_FIT"}},
    "NPC_INTERCOM": {"type": "NPC_INTERCOM", "verbs": "TALK", "props": {"talk": "NPC_TALK"}},
    "EXIT_TRIGGER": {"type": "EXIT_TRIGGER", "verbs": "OPERATE", "props": {"operate": "EXIT_ACTION"}},
}

class LvlEditorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("LVL Editor")

        self.current_file = None
        self.dirty = False
        self._loading = False
        self._refresh_after_id = None

        self.recent_files = []
        self.recent_dir = os.path.join(os.path.expanduser("~"), ".lvl")
        self.recent_path = os.path.join(self.recent_dir, "recent.json")
        self._level_state = None
        self._selected_script = None
        self._selected_object = None
        self._selected_room = None
        self._selected_tile = None
        self._map_cell = 24
        self._map_drag_mode = None
        self._map_drag_object = None
        self._map_drag_spawn = None
        self._map_tool = tk.StringVar(value="paint")
        self._log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".lvl_editor"))
        self._log_path = os.path.join(self._log_dir, "editor.log")

        self._build_menu()
        self._build_layout()
        self._bind_events()
        self._load_recent()
        self._init_logging()
        self._new_file(set_dirty=False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        self.recent_menu.add_command(label="(empty)", state=tk.DISABLED)
        file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Set TSET...", command=self.set_tset)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        menu.add_cascade(label="Edit", menu=edit_menu)
        self.root.config(menu=menu)

    def _build_layout(self) -> None:
        main = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(main)
        right = tk.Frame(main)
        main.add(left, minsize=220)
        main.add(right, minsize=520)

        self.sidebar_tabs = ttk.Notebook(left)
        self.sidebar_tabs.pack(fill=tk.BOTH, expand=True)

        structure_frame = tk.Frame(self.sidebar_tabs)
        self.sidebar_tabs.add(structure_frame, text="Structure")
        self.structure_tree = ttk.Treeview(structure_frame, show="tree")
        self.structure_tree.pack(fill=tk.BOTH, expand=True)

        inspector_frame = tk.Frame(self.sidebar_tabs)
        self.sidebar_tabs.add(inspector_frame, text="Inspector")
        tk.Label(inspector_frame, text="Level", anchor="w").pack(
            fill=tk.X, padx=8, pady=(8, 2)
        )
        tset_row = tk.Frame(inspector_frame)
        tset_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        tk.Label(tset_row, text="TSET", width=6, anchor="w").pack(side=tk.LEFT)
        self.tset_value = tk.Label(tset_row, text="(none)", anchor="w")
        self.tset_value.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(tset_row, text="Set", command=self.set_tset, width=6).pack(
            side=tk.LEFT, padx=(6, 2)
        )
        tk.Button(tset_row, text="Clear", command=self.clear_tset, width=6).pack(
            side=tk.LEFT
        )

        self._build_inspector(inspector_frame)

        self.editor_tabs = ttk.Notebook(right)
        self.editor_tabs.pack(fill=tk.BOTH, expand=True)

        data_frame = tk.Frame(self.editor_tabs)
        self.editor_tabs.add(data_frame, text="Data")
        self._build_data_tabs(data_frame)

        text_frame = tk.Frame(self.editor_tabs)
        self.editor_tabs.add(text_frame, text="LVL Text")
        self.text = tk.Text(text_frame, undo=True, maxundo=-1, wrap="none")
        self.text.pack(fill=tk.BOTH, expand=True)

        map_frame = tk.Frame(self.editor_tabs)
        self.editor_tabs.add(map_frame, text="Map")
        self._build_map_editor(map_frame)

        self.status = tk.Label(self.root, text="Ready.", anchor="w")
        self.status.pack(fill=tk.X)

    def _bind_events(self) -> None:
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.structure_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.map_canvas.bind("<Button-1>", self._on_map_click)
        self.map_canvas.bind("<B1-Motion>", self._on_map_drag)
        self.map_canvas.bind("<ButtonRelease-1>", self._on_map_release)
        self.root.bind("<Control-n>", lambda *_: self.new_file())
        self.root.bind("<Control-o>", lambda *_: self.open_file())
        self.root.bind("<Control-s>", lambda *_: self.save_file())
        self.root.bind("<Control-S>", lambda *_: self.save_file())
        self.root.bind("<Control-Shift-S>", lambda *_: self.save_file_as())
        self.root.bind("<Control-Shift-s>", lambda *_: self.save_file_as())
        self.root.bind("<Control-z>", lambda *_: self.undo())
        self.root.bind("<Control-y>", lambda *_: self.redo())

    def _build_data_tabs(self, parent: tk.Frame) -> None:
        self.data_tabs = ttk.Notebook(parent)
        self.data_tabs.pack(fill=tk.BOTH, expand=True)

        self.flags_list = self._build_simple_list_tab("Flags")
        self.vars_list = self._build_simple_list_tab("Vars")
        self.items_list = self._build_simple_list_tab("Items")
        self.messages_list, self.message_text = self._build_messages_tab()
        self.scripts_list, self.script_text = self._build_scripts_tab()
        self.rooms_list = self._build_rooms_tab()
        self.objects_list = self._build_objects_tab()
        self.issues_list = self._build_issues_tab()
        self.log_view = self._build_log_tab()
        self._build_workflow_tab()

    def _build_simple_list_tab(self, title: str) -> tk.Listbox:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text=title)
        listbox = tk.Listbox(frame, activestyle="dotbox")
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
        btns = tk.Frame(frame)
        btns.pack(side=tk.RIGHT, fill=tk.Y, padx=6, pady=6)
        tk.Button(btns, text="Add", command=lambda: self._add_simple_entry(title)).pack(fill=tk.X)
        tk.Button(btns, text="Rename", command=lambda: self._rename_simple_entry(title)).pack(fill=tk.X, pady=(4, 0))
        tk.Button(btns, text="Remove", command=lambda: self._remove_simple_entry(title)).pack(fill=tk.X, pady=(4, 0))
        listbox.bind("<<ListboxSelect>>", lambda *_: self._on_simple_select(title))
        return listbox

    def _build_messages_tab(self) -> tuple[tk.Listbox, tk.Text]:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Messages")
        left = tk.Frame(frame)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0), pady=6)
        listbox = tk.Listbox(left, activestyle="dotbox")
        listbox.pack(fill=tk.BOTH, expand=True)
        btns = tk.Frame(left)
        btns.pack(fill=tk.X, pady=(6, 0))
        tk.Button(btns, text="Add", command=self._add_message).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(btns, text="Rename", command=self._rename_message).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        tk.Button(btns, text="Remove", command=self._remove_message).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

        right = tk.Frame(frame)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        tk.Label(right, text="Message Text", anchor="w").pack(fill=tk.X)
        text = tk.Text(right, height=6)
        text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        tk.Button(right, text="Save Message", command=self._save_message_text).pack(pady=(6, 0), anchor="e")
        listbox.bind("<<ListboxSelect>>", lambda *_: self._on_message_select())
        return listbox, text

    def _build_scripts_tab(self) -> tuple[tk.Listbox, tk.Text]:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Scripts")
        top = tk.Frame(frame)
        top.pack(fill=tk.X, padx=6, pady=(6, 0))
        tk.Label(top, text="Kind").pack(side=tk.LEFT)
        self.script_kind_var = tk.StringVar(value="COND")
        self.script_kind_combo = ttk.Combobox(top, textvariable=self.script_kind_var, values=["COND", "ACT"], width=8, state="readonly")
        self.script_kind_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.script_kind_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_scripts_list())

        body = tk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        listbox = tk.Listbox(body, activestyle="dotbox", width=18)
        listbox.pack(side=tk.LEFT, fill=tk.Y)
        listbox.bind("<<ListboxSelect>>", lambda *_: self._on_script_select())

        editor = tk.Frame(body)
        editor.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))
        text = tk.Text(editor, height=8)
        text.pack(fill=tk.BOTH, expand=True)

        actions = tk.Frame(editor)
        actions.pack(fill=tk.X, pady=(6, 0))
        tk.Button(actions, text="Add", command=self._add_script).pack(side=tk.LEFT)
        tk.Button(actions, text="Rename", command=self._rename_script).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(actions, text="Remove", command=self._remove_script).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(actions, text="Save Script", command=self._save_script).pack(side=tk.RIGHT)

        insert_row = tk.Frame(editor)
        insert_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(insert_row, text="Op").pack(side=tk.LEFT)
        self.script_op_var = tk.StringVar()
        self.script_op_combo = ttk.Combobox(insert_row, textvariable=self.script_op_var, width=12, state="readonly")
        self.script_op_combo.pack(side=tk.LEFT, padx=(4, 6))
        self.script_param1_var = tk.StringVar()
        self.script_param1_combo = ttk.Combobox(insert_row, textvariable=self.script_param1_var, width=14)
        self.script_param1_combo.pack(side=tk.LEFT)
        self.script_param1_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_script_param_options())
        self.script_param2_var = tk.StringVar()
        self.script_param2_combo = ttk.Combobox(insert_row, textvariable=self.script_param2_var, width=10)
        self.script_param2_combo.pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(insert_row, text="Create", command=self._create_from_script_params).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(insert_row, text="Add Line", command=self._insert_script_line).pack(side=tk.RIGHT)
        self.script_op_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_script_param_options())

        return listbox, text

    def _build_rooms_tab(self) -> tk.Listbox:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Rooms")
        left = tk.Frame(frame)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0), pady=6)
        listbox = tk.Listbox(left, activestyle="dotbox")
        listbox.pack(fill=tk.BOTH, expand=True)
        listbox.bind("<<ListboxSelect>>", lambda *_: self._on_room_select())
        room_btns = tk.Frame(left)
        room_btns.pack(fill=tk.X, pady=(6, 0))
        tk.Button(room_btns, text="Add", command=self._add_room).pack(side=tk.LEFT)
        tk.Button(room_btns, text="Rename", command=self._rename_room).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(room_btns, text="Remove", command=self._remove_room).pack(side=tk.LEFT, padx=(6, 0))

        right = tk.Frame(frame)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        tk.Label(right, text="Spawns").pack(anchor="w")
        self.spawns_list = tk.Listbox(right, activestyle="dotbox", height=8)
        self.spawns_list.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
        btns = tk.Frame(right)
        btns.pack(fill=tk.X)
        tk.Button(btns, text="Add", command=self._add_spawn).pack(side=tk.LEFT)
        tk.Button(btns, text="Rename", command=self._rename_spawn).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(btns, text="Remove", command=self._remove_spawn).pack(side=tk.LEFT, padx=(6, 0))
        self.spawns_list.bind("<<ListboxSelect>>", lambda *_: self._on_spawn_select())

        tk.Label(right, text="Exits").pack(anchor="w", pady=(8, 0))
        self.exits_list = tk.Listbox(right, activestyle="dotbox", height=6)
        self.exits_list.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
        exit_btns = tk.Frame(right)
        exit_btns.pack(fill=tk.X)
        tk.Button(exit_btns, text="Add", command=self._add_exit).pack(side=tk.LEFT)
        tk.Button(exit_btns, text="Edit", command=self._edit_exit).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(exit_btns, text="Remove", command=self._remove_exit).pack(side=tk.LEFT, padx=(6, 0))
        self.exits_list.bind("<<ListboxSelect>>", lambda *_: self._on_exit_select())
        return listbox

    def _build_objects_tab(self) -> tk.Listbox:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Objects")
        top = tk.Frame(frame)
        top.pack(fill=tk.X, padx=6, pady=(6, 0))
        tk.Label(top, text="Room").pack(side=tk.LEFT)
        self.objects_room_var = tk.StringVar()
        self.objects_room_combo = ttk.Combobox(top, textvariable=self.objects_room_var, state="readonly")
        self.objects_room_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.objects_room_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_objects_list())
        tk.Button(top, text="Add", command=self._add_object).pack(side=tk.RIGHT)
        tk.Button(top, text="Remove", command=self._remove_object).pack(side=tk.RIGHT, padx=(6, 0))
        listbox = tk.Listbox(frame, activestyle="dotbox")
        listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        listbox.bind("<<ListboxSelect>>", lambda *_: self._on_object_select_from_list())
        return listbox

    def _build_issues_tab(self) -> tk.Listbox:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Issues")
        listbox = tk.Listbox(frame, activestyle="dotbox")
        listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        actions = tk.Frame(frame)
        actions.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(actions, text="Create Selected", command=self._create_issue_selected).pack(side=tk.RIGHT)
        listbox.bind("<Double-Button-1>", lambda *_: self._create_issue_selected())
        return listbox

    def _build_log_tab(self) -> tk.Text:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Log")
        text = tk.Text(frame, height=10, wrap="none")
        text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 0))
        actions = tk.Frame(frame)
        actions.pack(fill=tk.X, padx=6, pady=(4, 6))
        tk.Button(actions, text="Refresh", command=self._refresh_log_view).pack(side=tk.RIGHT)
        self._refresh_log_view()
        return text

    def _select_data_tab(self, label: str) -> None:
        for idx in range(self.data_tabs.index("end")):
            if self.data_tabs.tab(idx, "text") == label:
                self.data_tabs.select(idx)
                return

    def _select_editor_tab(self, label: str) -> None:
        for idx in range(self.editor_tabs.index("end")):
            if self.editor_tabs.tab(idx, "text") == label:
                self.editor_tabs.select(idx)
                return

    def _add_script_kind(self, kind: str) -> None:
        self.script_kind_var.set(kind)
        self._refresh_scripts_list()
        self._add_script()

    def _build_workflow_tab(self) -> None:
        frame = tk.Frame(self.data_tabs)
        self.data_tabs.add(frame, text="Workflow")
        tabs = ttk.Notebook(frame)
        tabs.pack(fill=tk.BOTH, expand=True)

        guided = tk.Frame(tabs)
        tabs.add(guided, text="Guided")
        tk.Label(guided, text="New Level Wizard", anchor="w").pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Button(guided, text="Start Wizard", command=self._start_guided_wizard).pack(anchor="w", padx=8)
        tk.Button(guided, text="Next Step", command=self._guided_next_step).pack(anchor="w", padx=8, pady=(4, 0))
        self.guided_checklist = tk.Listbox(guided, height=8)
        self.guided_checklist.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._refresh_guided_checklist()

        room_flow = tk.Frame(tabs)
        tabs.add(room_flow, text="Room-first")
        tk.Label(room_flow, text="Room workflow", anchor="w").pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Button(room_flow, text="Focus Map", command=lambda: self._select_editor_tab("Map")).pack(anchor="w", padx=8)
        tk.Button(room_flow, text="Add Room", command=self._add_room).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(room_flow, text="Add Object", command=self._add_object).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(room_flow, text="Add Spawn", command=self._add_spawn).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(room_flow, text="Add Exit", command=self._add_exit).pack(anchor="w", padx=8, pady=(4, 0))

        story_flow = tk.Frame(tabs)
        tabs.add(story_flow, text="Story-first")
        tk.Label(story_flow, text="Story workflow", anchor="w").pack(fill=tk.X, padx=8, pady=(8, 4))
        tk.Button(story_flow, text="Focus Scripts", command=lambda: self._select_data_tab("Scripts")).pack(anchor="w", padx=8)
        tk.Button(story_flow, text="Add Message", command=self._add_message).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(story_flow, text="Add Flag", command=lambda: self._add_simple_entry("Flags")).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(story_flow, text="Add Item", command=lambda: self._add_simple_entry("Items")).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(story_flow, text="Add Condition", command=lambda: self._add_script_kind("COND")).pack(anchor="w", padx=8, pady=(4, 0))
        tk.Button(story_flow, text="Add Action", command=lambda: self._add_script_kind("ACT")).pack(anchor="w", padx=8, pady=(4, 0))

    def _build_map_editor(self, parent: tk.Frame) -> None:
        top = tk.Frame(parent)
        top.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(top, text="Room").pack(side=tk.LEFT)
        self.map_room_var = tk.StringVar()
        self.map_room_combo = ttk.Combobox(top, textvariable=self.map_room_var, state="readonly")
        self.map_room_combo.pack(side=tk.LEFT, padx=(6, 0))
        self.map_room_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_map_room_change())
        tk.Label(top, text="Tool").pack(side=tk.LEFT, padx=(12, 4))
        self.map_tool_combo = ttk.Combobox(top, textvariable=self._map_tool, values=["paint", "object", "spawn", "pick"], width=8, state="readonly")
        self.map_tool_combo.pack(side=tk.LEFT)

        palette_frame = tk.Frame(parent)
        palette_frame.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        tk.Label(palette_frame, text="Tiles").pack(anchor="w")
        self.palette_container = tk.Frame(palette_frame)
        self.palette_container.pack(fill=tk.Y, expand=True)

        canvas_frame = tk.Frame(parent)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.map_canvas = tk.Canvas(canvas_frame, background="#111111")
        self.map_canvas.pack(fill=tk.BOTH, expand=True)

    def _build_inspector(self, parent: tk.Frame) -> None:
        self.obj_frame = tk.LabelFrame(parent, text="Object")
        self.obj_frame.pack(fill=tk.X, padx=8, pady=(8, 6))
        self.obj_name_var = tk.StringVar()
        self.obj_x_var = tk.StringVar()
        self.obj_y_var = tk.StringVar()
        self.obj_type_var = tk.StringVar()
        self.obj_cond_var = tk.StringVar()
        self.obj_item_var = tk.StringVar()
        self.obj_code_var = tk.StringVar()
        self.obj_var_var = tk.StringVar()
        self.obj_expect_var = tk.StringVar()

        row1 = tk.Frame(self.obj_frame)
        row1.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row1, text="Name", width=6, anchor="w").pack(side=tk.LEFT)
        tk.Entry(row1, textvariable=self.obj_name_var, width=10).pack(side=tk.LEFT)
        tk.Label(row1, text="X", width=2).pack(side=tk.LEFT, padx=(6, 2))
        tk.Entry(row1, textvariable=self.obj_x_var, width=4).pack(side=tk.LEFT)
        tk.Label(row1, text="Y", width=2).pack(side=tk.LEFT, padx=(6, 2))
        tk.Entry(row1, textvariable=self.obj_y_var, width=4).pack(side=tk.LEFT)

        row2 = tk.Frame(self.obj_frame)
        row2.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row2, text="Type", width=6, anchor="w").pack(side=tk.LEFT)
        self.obj_type_combo = ttk.Combobox(row2, textvariable=self.obj_type_var, values=self._object_type_values())
        self.obj_type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.obj_template_var = tk.StringVar(value="Custom")
        self.obj_template_combo = ttk.Combobox(
            row2,
            textvariable=self.obj_template_var,
            values=list(OBJECT_TEMPLATES.keys()),
            width=12,
            state="readonly",
        )
        self.obj_template_combo.pack(side=tk.LEFT, padx=(6, 2))
        tk.Button(row2, text="Use", width=4, command=self._apply_object_template).pack(side=tk.LEFT)
        tk.Button(row2, text="Deps", width=4, command=self._apply_template_deps).pack(side=tk.LEFT, padx=(4, 0))

        row3 = tk.Frame(self.obj_frame)
        row3.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row3, text="Cond", width=6, anchor="w").pack(side=tk.LEFT)
        self.obj_cond_combo = ttk.Combobox(row3, textvariable=self.obj_cond_var)
        self.obj_cond_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row3, text="+", width=2, command=self._create_cond_from_inspector).pack(side=tk.LEFT, padx=(4, 0))

        row4 = tk.Frame(self.obj_frame)
        row4.pack(fill=tk.X, pady=(0, 4))
        tk.Label(row4, text="Verbs", width=6, anchor="w").pack(side=tk.LEFT)
        self.obj_verbs = {}
        for verb in ["LOOK", "TAKE", "USE", "TALK", "OPERATE"]:
            var = tk.IntVar()
            self.obj_verbs[verb] = var
            tk.Checkbutton(row4, text=verb, variable=var).pack(side=tk.LEFT)

        self.obj_scripts = {}
        self.obj_script_combos = {}
        for label in ["look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject"]:
            row = tk.Frame(self.obj_frame)
            row.pack(fill=tk.X, pady=(0, 2))
            tk.Label(row, text=label, width=6, anchor="w").pack(side=tk.LEFT)
            var = tk.StringVar()
            self.obj_scripts[label] = var
            combo = ttk.Combobox(row, textvariable=var)
            combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.obj_script_combos[label] = combo
            tk.Button(row, text="+", width=2, command=lambda k=label: self._create_act_for_field(k)).pack(side=tk.LEFT, padx=(4, 0))

        misc = tk.Frame(self.obj_frame)
        misc.pack(fill=tk.X, pady=(4, 0))
        tk.Label(misc, text="Item", width=6, anchor="w").pack(side=tk.LEFT)
        ttk.Entry(misc, textvariable=self.obj_item_var, width=10).pack(side=tk.LEFT)
        tk.Button(misc, text="+", width=2, command=lambda: self._create_simple_from_field("items", self.obj_item_var)).pack(side=tk.LEFT, padx=(4, 6))
        tk.Label(misc, text="Code", width=6).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Entry(misc, textvariable=self.obj_code_var, width=6).pack(side=tk.LEFT)
        tk.Label(misc, text="Var", width=4).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Entry(misc, textvariable=self.obj_var_var, width=8).pack(side=tk.LEFT)
        tk.Button(misc, text="+", width=2, command=lambda: self._create_simple_from_field("vars", self.obj_var_var)).pack(side=tk.LEFT, padx=(4, 6))
        tk.Label(misc, text="Expect", width=6).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Entry(misc, textvariable=self.obj_expect_var, width=6).pack(side=tk.LEFT)

        tk.Button(self.obj_frame, text="Apply Object", command=self._apply_object_changes).pack(
            anchor="e", pady=(6, 0)
        )

        self.script_frame = tk.LabelFrame(parent, text="Script")
        self.script_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.script_name_var = tk.StringVar()
        self.script_kind_label = tk.Label(self.script_frame, textvariable=self.script_name_var, anchor="w")
        self.script_kind_label.pack(fill=tk.X, padx=6, pady=(6, 2))
        self.script_inspector_text = tk.Text(self.script_frame, height=6)
        self.script_inspector_text.pack(fill=tk.BOTH, expand=True, padx=6)
        tk.Button(self.script_frame, text="Save Script", command=self._save_script_from_inspector).pack(
            anchor="e", padx=6, pady=6
        )

    def _on_text_modified(self, _event=None) -> None:
        if self._loading:
            self.text.edit_modified(False)
            return
        self._set_dirty(True)
        self._schedule_structure_refresh()
        self.text.edit_modified(False)

    def _schedule_structure_refresh(self) -> None:
        if self._refresh_after_id:
            self.root.after_cancel(self._refresh_after_id)
        self._refresh_after_id = self.root.after(350, self._refresh_structure)

    def _refresh_structure(self) -> None:
        self._refresh_after_id = None
        self.structure_tree.delete(*self.structure_tree.get_children())
        self._structure_targets = {}
        self._level_tset = None

        lines = self.text.get("1.0", "end-1c").splitlines()
        data = self._parse_structure(lines)
        self._level_tset = data.get("level_tset")
        self._level_state = self._parse_level_state(lines)

        root_id = self.structure_tree.insert("", "end", text="Level")
        if data["level_line"]:
            self._structure_targets[root_id] = data["level_line"]

        self._add_section(root_id, "Flags", data["flags"])
        self._add_section(root_id, "Vars", data["vars"])
        self._add_section(root_id, "Items", data["items"])
        self._add_section(root_id, "Messages", data["messages"])
        self._add_section(root_id, "Conditions", data["conds"])
        self._add_section(root_id, "Actions", data["acts"])

        rooms_id = self.structure_tree.insert(root_id, "end", text="Rooms")
        for room in data["rooms"]:
            item_id = self.structure_tree.insert(rooms_id, "end", text=room["name"])
            self._structure_targets[item_id] = room["line"]

        self.structure_tree.item(root_id, open=True)
        self.structure_tree.item(rooms_id, open=True)
        self._update_tset_label()
        self._refresh_data_tabs()
        self._refresh_map()

    def _add_section(self, parent: str, title: str, entries: list[dict]) -> None:
        section_id = self.structure_tree.insert(parent, "end", text=title)
        for entry in entries:
            item_id = self.structure_tree.insert(section_id, "end", text=entry["name"])
            self._structure_targets[item_id] = entry["line"]
        self.structure_tree.item(section_id, open=True)

    def _parse_structure(self, lines: list[str]) -> dict:
        data = {
            "level_line": None,
            "level_tset": None,
            "flags": [],
            "vars": [],
            "items": [],
            "messages": [],
            "conds": [],
            "acts": [],
            "rooms": [],
        }
        mode = None
        for idx, raw in enumerate(lines, 1):
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            head = parts[0]

            if head == "LEVEL":
                data["level_line"] = idx
                data["level_tset"] = self._extract_tset(line)
                continue
            if head in ("FLAGS", "VARS", "ITEMS", "MESSAGES"):
                mode = head
                continue
            if head == "END":
                mode = None
                continue
            if head == "ROOM" and len(parts) >= 2:
                data["rooms"].append({"name": parts[1], "line": idx})
                mode = None
                continue
            if head == "COND" and len(parts) >= 2:
                data["conds"].append({"name": parts[1], "line": idx})
                mode = None
                continue
            if head == "ACT" and len(parts) >= 2:
                data["acts"].append({"name": parts[1], "line": idx})
                mode = None
                continue

            if mode == "FLAGS":
                data["flags"].append({"name": parts[0], "line": idx})
            elif mode == "VARS":
                data["vars"].append({"name": parts[0], "line": idx})
            elif mode == "ITEMS":
                data["items"].append({"name": parts[0], "line": idx})
            elif mode == "MESSAGES":
                name = parts[0]
                if "=" in line:
                    name = line.split("=", 1)[0].strip()
                data["messages"].append({"name": name, "line": idx})

        return data

    def _on_tree_select(self, _event=None) -> None:
        sel = self.structure_tree.selection()
        if not sel:
            return
        line = self._structure_targets.get(sel[0])
        if not line:
            return
        self.text.mark_set("insert", f"{line}.0")
        self.text.see(f"{line}.0")

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        title = "LVL Editor"
        if self.current_file:
            title += f" - {os.path.basename(self.current_file)}"
        if self.dirty:
            title += " *"
        self.root.title(title)
        if dirty:
            self._set_status("Unsaved changes.")

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        resp = messagebox.askyesnocancel(
            "Unsaved Changes",
            "Save changes before continuing?",
        )
        if resp is None:
            return False
        if resp:
            return self.save_file()
        return True

    def _new_file(self, set_dirty: bool = True) -> None:
        self._loading = True
        try:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", self._default_template())
            self.text.edit_reset()
        finally:
            self._loading = False
        self.current_file = None
        self._set_dirty(set_dirty)
        self._refresh_structure()
        self._set_status("New level created.")
        self._log("new_file")

    def new_file(self) -> None:
        if not self._confirm_discard():
            return
        self._new_file(set_dirty=False)

    def open_file(self) -> None:
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open LVL file",
            filetypes=[("LVL files", "*.lvl"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            messagebox.showerror("Open Failed", str(exc))
            return
        self._loading = True
        try:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
            self.text.edit_reset()
        finally:
            self._loading = False
        self.current_file = path
        self._set_dirty(False)
        self._push_recent(path)
        self._refresh_structure()
        self._set_status(f"Opened {path}")
        self._log("open_file", path=path)

    def save_file(self) -> bool:
        if not self.current_file:
            return self.save_file_as()
        return self._write_file(self.current_file)

    def save_file_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            title="Save LVL file",
            defaultextension=".lvl",
            filetypes=[("LVL files", "*.lvl"), ("All files", "*.*")],
        )
        if not path:
            return False
        return self._write_file(path)

    def _write_file(self, path: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
        except OSError as exc:
            messagebox.showerror("Save Failed", str(exc))
            return False
        self.current_file = path
        self._set_dirty(False)
        self._push_recent(path)
        self._set_status(f"Saved {path}")
        self._log("save_file", path=path)
        return True

    def set_tset(self) -> None:
        path = filedialog.askopenfilename(
            title="Select TSET file",
            filetypes=[("TSET files", "*.tset"), ("All files", "*.*")],
        )
        if not path:
            return
        self._apply_tset_path(path)

    def _apply_tset_path(self, path: str) -> None:
        target = self._format_tset_path(path)
        lines = self.text.get("1.0", "end-1c").splitlines()
        if not lines:
            return
        updated = False
        for idx, raw in enumerate(lines):
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            if line.startswith("LEVEL "):
                new_line = self._upsert_tset_in_level_line(raw, target)
                lines[idx] = new_line
                updated = True
                break
        if not updated:
            return
        self._loading = True
        try:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", "\n".join(lines))
        finally:
            self._loading = False
        self._set_dirty(True)
        self._refresh_structure()
        self._set_status(f"Set tset to {target}")
        self._log("set_tset", tset=target)

    def clear_tset(self) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        if not lines:
            return
        updated = False
        for idx, raw in enumerate(lines):
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            if line.startswith("LEVEL "):
                new_line = self._remove_tset_from_level_line(raw)
                lines[idx] = new_line
                updated = True
                break
        if not updated:
            return
        self._loading = True
        try:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", "\n".join(lines))
        finally:
            self._loading = False
        self._set_dirty(True)
        self._refresh_structure()
        self._set_status("Cleared tset.")
        self._log("clear_tset")

    def _remove_tset_from_level_line(self, raw_line: str) -> str:
        parts = raw_line.rstrip("\n").split()
        filtered = [part for part in parts if not part.startswith("tset=")]
        return " ".join(filtered)

    def _format_tset_path(self, path: str) -> str:
        if not self.current_file:
            return path
        base_dir = os.path.dirname(self.current_file)
        try:
            rel = os.path.relpath(path, base_dir)
        except ValueError:
            return path
        if rel.startswith(".."):
            return path
        return rel

    def _upsert_tset_in_level_line(self, raw_line: str, path: str) -> str:
        stripped = raw_line.rstrip("\n")
        if "tset=" in stripped:
            parts = stripped.split()
            new_parts = []
            for part in parts:
                if part.startswith("tset="):
                    new_parts.append(f"tset={path}")
                else:
                    new_parts.append(part)
            return " ".join(new_parts)
        return f"{stripped} tset={path}"

    def _extract_tset(self, line: str) -> str | None:
        for part in line.split():
            if part.startswith("tset="):
                return part.split("=", 1)[1]
        return None

    def _update_tset_label(self) -> None:
        if hasattr(self, "_level_tset") and self._level_tset:
            self.tset_value.config(text=self._level_tset)
        else:
            self.tset_value.config(text="(none)")

    def _object_type_values(self) -> list[str]:
        return OBJ_TYPES

    def _parse_kv(self, line: str) -> dict:
        out = {}
        for m in TOKEN_KV.finditer(line):
            val = m.group(2)
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = val[1:-1]
            out[m.group(1)] = val
        return out

    def _parse_level_state(self, lines: list[str]) -> LevelState:
        level_line = None
        level_tset = None
        level_w = None
        level_h = None
        sections = {}
        flags = []
        vars_ = []
        items = []
        messages = []
        conds = []
        acts = []
        rooms = []

        mode = None
        current_script = None
        current_room = None
        room_mode = None

        for idx, raw in enumerate(lines):
            raw_nocomment = raw.split(";", 1)[0].rstrip("\n")
            stripped = raw_nocomment.strip()
            if not stripped:
                continue
            parts = stripped.split()
            head = parts[0]

            if head == "LEVEL":
                level_line = idx
                kv = self._parse_kv(stripped)
                level_tset = kv.get("tset")
                try:
                    level_w = int(kv.get("w", "")) if "w" in kv else None
                    level_h = int(kv.get("h", "")) if "h" in kv else None
                except ValueError:
                    level_w = None
                    level_h = None
                continue

            if head == "ENDROOM":
                if current_room:
                    current_room.end = idx
                    rooms.append(current_room)
                current_room = None
                room_mode = None
                continue

            if head == "ROOM" and len(parts) >= 2:
                name = parts[1]
                kv = self._parse_kv(stripped)
                current_room = RoomEntry(
                    rid=parts[1],
                    name=kv.get("name", parts[1]),
                    start=idx,
                    end=idx,
                    map_start=None,
                    map_end=None,
                    map_lines=[],
                    objects=[],
                    spawns={},
                    exits=[],
                )
                room_mode = None
                continue

            if current_script and head == "END":
                current_script.end = idx
                if current_script.kind == "COND":
                    conds.append(current_script)
                else:
                    acts.append(current_script)
                current_script = None
                mode = None
                continue

            if current_script:
                current_script.lines.append(stripped)
                continue

            if head in ("FLAGS", "VARS", "ITEMS", "MESSAGES") and not current_room:
                mode = head
                sections[head] = {"start": idx, "end": idx}
                continue

            if head == "END" and mode in ("FLAGS", "VARS", "ITEMS", "MESSAGES"):
                sections[mode]["end"] = idx
                mode = None
                continue

            if head == "COND" and len(parts) >= 2:
                current_script = ScriptEntry(
                    name=parts[1],
                    kind="COND",
                    start=idx,
                    end=idx,
                    lines=[],
                )
                mode = None
                continue

            if head == "ACT" and len(parts) >= 2:
                current_script = ScriptEntry(
                    name=parts[1],
                    kind="ACT",
                    start=idx,
                    end=idx,
                    lines=[],
                )
                mode = None
                continue

            if current_room:
                if head in ("SPAWNS", "EXITS", "OBJECTS", "MAP"):
                    room_mode = head
                    if head == "MAP":
                        current_room.map_start = idx
                    continue
                if head == "END" and room_mode in ("SPAWNS", "EXITS", "OBJECTS", "MAP"):
                    if room_mode == "MAP":
                        current_room.map_end = idx
                    room_mode = None
                    continue
                if room_mode == "OBJECTS":
                    obj = self._parse_object_line(stripped, idx)
                    if obj:
                        current_room.objects.append(obj)
                    continue
                if room_mode == "SPAWNS":
                    if len(parts) >= 2:
                        sid = parts[0]
                        try:
                            x_str, y_str = parts[1].split(",")
                            current_room.spawns[sid] = (int(x_str), int(y_str))
                        except ValueError:
                            pass
                    continue
                if room_mode == "EXITS":
                    if len(parts) >= 2:
                        edge = parts[0]
                        dest = parts[1]
                        current_room.exits.append((edge, dest))
                    continue
                if room_mode == "MAP":
                    current_room.map_lines.append(raw_nocomment)
                    continue

            if mode == "FLAGS":
                flags.append(parts[0])
            elif mode == "VARS":
                vars_.append(parts[0])
            elif mode == "ITEMS":
                items.append(parts[0])
            elif mode == "MESSAGES":
                if "=" in stripped:
                    name, rest = stripped.split("=", 1)
                    messages.append((name.strip(), rest.strip().strip('"')))

        return LevelState(
            level_line=level_line,
            level_tset=level_tset,
            width=level_w,
            height=level_h,
            flags=flags,
            vars=vars_,
            items=items,
            messages=messages,
            sections=sections,
            conds=conds,
            acts=acts,
            rooms=rooms,
        )

    def _parse_object_line(self, line: str, idx: int) -> Optional[ObjectEntry]:
        parts = line.split()
        if len(parts) < 4 or parts[1] != "at":
            return None
        name = parts[0]
        try:
            x_str, y_str = parts[2].split(",")
            x = int(x_str)
            y = int(y_str)
        except ValueError:
            return None
        kv = self._parse_kv(line)
        type_name = kv.get("type", "")
        verbs = kv.get("verbs", "")
        cond = kv.get("cond", "ALWAYS")
        props = {}
        for k, v in kv.items():
            if k in ("type", "verbs", "cond"):
                continue
            props[k] = v
        return ObjectEntry(
            name=name,
            x=x,
            y=y,
            type_name=type_name,
            verbs=verbs,
            cond=cond,
            props=props,
            line_index=idx,
        )

    def _refresh_data_tabs(self) -> None:
        state = self._level_state
        if not state:
            return
        self._set_listbox(self.flags_list, state.flags)
        self._set_listbox(self.vars_list, state.vars)
        self._set_listbox(self.items_list, state.items)
        self._set_listbox(self.messages_list, [name for name, _ in state.messages])
        self._refresh_scripts_list()
        self._set_listbox(self.rooms_list, [room.rid for room in state.rooms])
        room_ids = [room.rid for room in state.rooms]
        self.objects_room_combo["values"] = room_ids
        self.map_room_combo["values"] = room_ids
        if room_ids:
            if not self.objects_room_var.get():
                self.objects_room_var.set(room_ids[0])
            if not self.map_room_var.get():
                self.map_room_var.set(room_ids[0])
        self._refresh_objects_list()
        self._update_object_picker_values()
        self._refresh_issues()
        self._refresh_guided_checklist()

    def _set_listbox(self, listbox: tk.Listbox, values: list[str]) -> None:
        listbox.delete(0, tk.END)
        for val in values:
            listbox.insert(tk.END, val)

    def _refresh_scripts_list(self) -> None:
        state = self._level_state
        if not state:
            return
        kind = self.script_kind_var.get()
        scripts = state.conds if kind == "COND" else state.acts
        self._set_listbox(self.scripts_list, [s.name for s in scripts])
        self.script_text.delete("1.0", tk.END)
        self._refresh_script_ops()

    def _refresh_script_ops(self) -> None:
        if self.script_kind_var.get() == "COND":
            self.script_op_combo["values"] = ["TRUE", "FLAGSET", "FLAGCLR", "HAS", "VAREQ"]
        else:
            self.script_op_combo["values"] = [
                "MSG",
                "SETFLAG",
                "CLRFLAG",
                "GIVE",
                "TAKE",
                "SETVAR",
                "SFX",
                "TRANSITION",
            ]
        self.script_op_var.set("")
        self._refresh_script_param_options()

    def _refresh_script_param_options(self) -> None:
        state = self._level_state
        if not state:
            return
        op = self.script_op_var.get()
        values = []
        param2_values = []
        param2_state = "normal"
        if self.script_kind_var.get() == "COND":
            if op in ("FLAGSET", "FLAGCLR"):
                values = state.flags
            elif op == "HAS":
                values = state.items
            elif op == "VAREQ":
                values = state.vars
        else:
            if op == "MSG":
                values = [name for name, _ in state.messages]
            elif op in ("SETFLAG", "CLRFLAG"):
                values = state.flags
            elif op in ("GIVE", "TAKE"):
                values = state.items
            elif op == "SETVAR":
                values = state.vars
            elif op == "TRANSITION":
                values = [room.rid for room in state.rooms]
                room_id = self.script_param1_var.get()
                room = self._find_room(room_id)
                if room:
                    param2_values = list(room.spawns.keys())
                else:
                    param2_values = []
                param2_state = "readonly"
        if op != "TRANSITION":
            param2_values = []
        self.script_param1_combo["values"] = values
        self.script_param2_combo["values"] = param2_values
        self.script_param2_combo.configure(state=param2_state)

    def _create_from_script_params(self) -> None:
        op = self.script_op_var.get()
        name = self.script_param1_var.get().strip()
        if self.script_kind_var.get() == "COND":
            if op in ("FLAGSET", "FLAGCLR"):
                if not name:
                    name = simpledialog.askstring("Create Flag", "Flag name:")
                if name:
                    self._create_simple_entry("flags", name)
                    self.script_param1_var.set(name)
            elif op == "HAS":
                if not name:
                    name = simpledialog.askstring("Create Item", "Item name:")
                if name:
                    self._create_simple_entry("items", name)
                    self.script_param1_var.set(name)
            elif op == "VAREQ":
                if not name:
                    name = simpledialog.askstring("Create Var", "Var name:")
                if name:
                    self._create_simple_entry("vars", name)
                    self.script_param1_var.set(name)
        else:
            if op == "MSG":
                if not name:
                    name = simpledialog.askstring("Create Message", "Message ID:")
                if name:
                    self._create_message_entry(name, "")
                    self.script_param1_var.set(name)
            elif op in ("SETFLAG", "CLRFLAG"):
                if not name:
                    name = simpledialog.askstring("Create Flag", "Flag name:")
                if name:
                    self._create_simple_entry("flags", name)
                    self.script_param1_var.set(name)
            elif op in ("GIVE", "TAKE"):
                if not name:
                    name = simpledialog.askstring("Create Item", "Item name:")
                if name:
                    self._create_simple_entry("items", name)
                    self.script_param1_var.set(name)
            elif op == "SETVAR":
                if not name:
                    name = simpledialog.askstring("Create Var", "Var name:")
                if name:
                    self._create_simple_entry("vars", name)
                    self.script_param1_var.set(name)
            elif op == "TRANSITION":
                room_id = name
                if not room_id:
                    room_id = simpledialog.askstring("Create Room", "Room ID:")
                if room_id:
                    if not self._level_state or not any(r.rid == room_id for r in self._level_state.rooms):
                        self._create_room_simple(room_id)
                    self.script_param1_var.set(room_id)
                spawn_id = self.script_param2_var.get().strip()
                if room_id and not spawn_id:
                    spawn_id = simpledialog.askstring("Create Spawn", "Spawn ID:", initialvalue="S0")
                if room_id and spawn_id:
                    room = self._find_room(room_id)
                    if room and spawn_id not in room.spawns:
                        self._update_spawn_line(room, spawn_id, 1, 1)
                    self.script_param2_var.set(spawn_id)

    def _create_message_entry(self, name: str, text: str) -> None:
        if self._is_name_taken("messages", name):
            return
        messages = list(self._level_state.messages) if self._level_state else []
        messages.append((name, text))
        self._update_messages_block(messages)
        self._log("create_message", name=name)

    def _create_room_simple(self, room_id: str) -> None:
        if self._level_state and any(r.rid == room_id for r in self._level_state.rooms):
            return
        width = self._level_state.width if self._level_state and self._level_state.width else 10
        height = self._level_state.height if self._level_state and self._level_state.height else 8
        top = "#" * width
        middle = "#" + "." * (width - 2) + "#" if width >= 2 else "." * width
        rows = [top] + [middle for _ in range(max(height - 2, 0))] + ([top] if height > 1 else [])
        map_block = "\\n".join(rows)
        lines = self.text.get("1.0", "end-1c").splitlines()
        block = [
            f"ROOM {room_id} name=\"{room_id}\"",
            "SPAWNS",
            "  S0 1,1",
            "END",
            "EXITS",
            "END",
            "OBJECTS",
            "END",
            "MAP",
            map_block,
            "END",
            "ENDROOM",
        ]
        lines += [""] + block
        self._set_text_lines(lines)
        self._log("room_add", room=room_id, source="script_create")

    def _on_script_select(self) -> None:
        state = self._level_state
        if not state:
            return
        sel = self.scripts_list.curselection()
        if not sel:
            return
        kind = self.script_kind_var.get()
        scripts = state.conds if kind == "COND" else state.acts
        script = scripts[sel[0]]
        self._selected_script = script
        self.script_text.delete("1.0", tk.END)
        self.script_text.insert("1.0", "\n".join(script.lines))
        self._load_script_inspector(script)

    def _load_script_inspector(self, script: ScriptEntry) -> None:
        self.script_name_var.set(f"{script.kind} {script.name}")
        self.script_inspector_text.delete("1.0", tk.END)
        self.script_inspector_text.insert("1.0", "\n".join(script.lines))

    def _save_script(self) -> None:
        if not self._selected_script:
            return
        lines = self.script_text.get("1.0", "end-1c").splitlines()
        self._update_script_block(self._selected_script, lines)

    def _save_script_from_inspector(self) -> None:
        if not self._selected_script:
            return
        lines = self.script_inspector_text.get("1.0", "end-1c").splitlines()
        self._update_script_block(self._selected_script, lines)

    def _insert_script_line(self) -> None:
        op = self.script_op_var.get()
        if not op:
            return
        param1 = self.script_param1_var.get()
        param2 = self.script_param2_var.get()
        line = op
        if param1:
            line += f" {param1}"
        if param2:
            line += f" {param2}"
        self.script_text.insert(tk.END, ("\n" if self.script_text.get("1.0", "end-1c") else "") + line)
        self.script_inspector_text.insert(tk.END, ("\n" if self.script_inspector_text.get("1.0", "end-1c") else "") + line)

    def _add_script(self) -> None:
        name = simpledialog.askstring("Add Script", "Script name:")
        if not name:
            return
        if self._is_name_taken("scripts", name):
            messagebox.showerror("Add", f"{name} already exists.")
            return
        kind = self.script_kind_var.get()
        lines = self.text.get("1.0", "end-1c").splitlines()
        insert_at = self._find_insert_before_room(lines)
        block = [f"{kind} {name}", "  TRUE" if kind == "COND" else "", "END"]
        if block[1] == "":
            block = [block[0], "END"]
        new_lines = lines[:insert_at] + block + lines[insert_at:]
        self._set_text_lines(new_lines)
        self._log("add_script", kind=kind, name=name)

    def _rename_script(self) -> None:
        if not self._selected_script:
            return
        name = simpledialog.askstring("Rename Script", "New name:", initialvalue=self._selected_script.name)
        if not name:
            return
        if self._is_name_taken("scripts", name) and name != self._selected_script.name:
            messagebox.showerror("Rename", f"{name} already exists.")
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        lines[self._selected_script.start] = f"{self._selected_script.kind} {name}"
        self._set_text_lines(lines)
        self._apply_rename_references("scripts", self._selected_script.name, name, kind=self._selected_script.kind)
        self._log("rename_script", old=self._selected_script.name, new=name)

    def _remove_script(self) -> None:
        if not self._selected_script:
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        start = self._selected_script.start
        end = self._selected_script.end
        new_lines = lines[:start] + lines[end + 1:]
        self._set_text_lines(new_lines)
        self._log("remove_script", name=self._selected_script.name)

    def _update_script_block(self, script: ScriptEntry, new_lines: list[str]) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        start = script.start
        end = script.end
        new_block = [lines[start]] + [f"  {ln}" if ln and not ln.startswith(" ") else ln for ln in new_lines] + [lines[end]]
        lines = lines[:start] + new_block + lines[end + 1:]
        self._set_text_lines(lines)

    def _find_insert_before_room(self, lines: list[str]) -> int:
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM "):
                return idx
        return len(lines)

    def _add_simple_entry(self, title: str) -> None:
        name = simpledialog.askstring(f"Add {title}", "Name:")
        if not name:
            return
        if self._is_name_taken(title, name):
            messagebox.showerror("Add", f"{name} already exists.")
            return
        entries = list(self._get_simple_entries(title))
        entries.append(name)
        self._update_simple_section(title.upper(), entries)
        self._log("add_entry", kind=title, name=name)

    def _rename_simple_entry(self, title: str) -> None:
        listbox = self._listbox_for_title(title)
        sel = listbox.curselection()
        if not sel:
            return
        old = listbox.get(sel[0])
        name = simpledialog.askstring(f"Rename {title}", "New name:", initialvalue=old)
        if not name:
            return
        if self._is_name_taken(title, name) and name != old:
            messagebox.showerror("Rename", f"{name} already exists.")
            return
        entries = list(self._get_simple_entries(title))
        entries[sel[0]] = name
        self._update_simple_section(title.upper(), entries)
        self._apply_rename_references(title, old, name)
        self._log("rename_entry", kind=title, old=old, new=name)

    def _remove_simple_entry(self, title: str) -> None:
        listbox = self._listbox_for_title(title)
        sel = listbox.curselection()
        if not sel:
            return
        entries = list(self._get_simple_entries(title))
        removed = entries[sel[0]]
        del entries[sel[0]]
        self._update_simple_section(title.upper(), entries)
        self._log("remove_entry", kind=title, name=removed)

    def _on_simple_select(self, _title: str) -> None:
        return

    def _get_simple_entries(self, title: str) -> list[str]:
        if not self._level_state:
            return []
        key = title.lower()
        if key == "flags":
            return self._level_state.flags
        if key == "vars":
            return self._level_state.vars
        if key == "items":
            return self._level_state.items
        return []

    def _listbox_for_title(self, title: str) -> tk.Listbox:
        if title == "Flags":
            return self.flags_list
        if title == "Vars":
            return self.vars_list
        if title == "Items":
            return self.items_list
        raise ValueError("Unknown listbox title")

    def _update_simple_section(self, section: str, entries: list[str]) -> None:
        state = self._level_state
        if not state:
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        sec = state.sections.get(section)
        if not sec:
            insert_at = self._find_insert_before_room(lines)
            block = [section] + [f"  {e}" for e in entries] + ["END"]
            new_lines = lines[:insert_at] + block + lines[insert_at:]
            self._set_text_lines(new_lines)
            return
        start = sec["start"]
        end = sec["end"]
        new_block = [lines[start]] + [f"  {e}" for e in entries] + [lines[end]]
        lines = lines[:start] + new_block + lines[end + 1:]
        self._set_text_lines(lines)

    def _add_message(self) -> None:
        name = simpledialog.askstring("Add Message", "Message ID:")
        if not name:
            return
        if self._is_name_taken("messages", name):
            messagebox.showerror("Add", f"{name} already exists.")
            return
        messages = list(self._level_state.messages) if self._level_state else []
        messages.append((name, ""))
        self._update_messages_block(messages)
        self._log("add_message", name=name)

    def _rename_message(self) -> None:
        sel = self.messages_list.curselection()
        if not sel or not self._level_state:
            return
        old = self.messages_list.get(sel[0])
        name = simpledialog.askstring("Rename Message", "New ID:", initialvalue=old)
        if not name:
            return
        if self._is_name_taken("messages", name) and name != old:
            messagebox.showerror("Rename", f"{name} already exists.")
            return
        messages = list(self._level_state.messages)
        messages[sel[0]] = (name, messages[sel[0]][1])
        self._update_messages_block(messages)
        self._apply_rename_references("messages", old, name)
        self._log("rename_message", old=old, new=name)

    def _remove_message(self) -> None:
        sel = self.messages_list.curselection()
        if not sel or not self._level_state:
            return
        messages = list(self._level_state.messages)
        removed = messages[sel[0]][0]
        del messages[sel[0]]
        self._update_messages_block(messages)
        self._log("remove_message", name=removed)

    def _on_message_select(self) -> None:
        sel = self.messages_list.curselection()
        if not sel or not self._level_state:
            return
        name, text = self._level_state.messages[sel[0]]
        self.message_text.delete("1.0", tk.END)
        self.message_text.insert("1.0", text)

    def _save_message_text(self) -> None:
        sel = self.messages_list.curselection()
        if not sel or not self._level_state:
            return
        messages = list(self._level_state.messages)
        name, _ = messages[sel[0]]
        messages[sel[0]] = (name, self.message_text.get("1.0", "end-1c"))
        self._update_messages_block(messages)

    def _update_messages_block(self, messages: list[tuple]) -> None:
        state = self._level_state
        if not state:
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        sec = state.sections.get("MESSAGES")
        if not sec:
            insert_at = self._find_insert_before_room(lines)
            block = ["MESSAGES"] + [f'  {name} = "{text}"' for name, text in messages] + ["END"]
            new_lines = lines[:insert_at] + block + lines[insert_at:]
            self._set_text_lines(new_lines)
            return
        start = sec["start"]
        end = sec["end"]
        new_block = [lines[start]] + [f'  {name} = "{text}"' for name, text in messages] + [lines[end]]
        lines = lines[:start] + new_block + lines[end + 1:]
        self._set_text_lines(lines)

    def _on_room_select(self) -> None:
        sel = self.rooms_list.curselection()
        if not sel or not self._level_state:
            return
        room = self._level_state.rooms[sel[0]]
        self._selected_room = room
        self.map_room_var.set(room.rid)
        self.objects_room_var.set(room.rid)
        self._refresh_objects_list()
        self._refresh_spawns_list(room)
        self._refresh_map()

    def _add_room(self) -> None:
        name = simpledialog.askstring("Add Room", "Room ID (e.g., R0):")
        if not name:
            return
        if self._level_state and any(r.rid == name for r in self._level_state.rooms):
            messagebox.showerror("Room Exists", f"{name} already exists.")
            return
        label = simpledialog.askstring("Add Room", "Room name:", initialvalue=name)
        if not label:
            label = name
        width = self._level_state.width if self._level_state and self._level_state.width else 10
        height = self._level_state.height if self._level_state and self._level_state.height else 8
        top = "#" * width
        middle = "#" + "." * (width - 2) + "#" if width >= 2 else "." * width
        rows = [top] + [middle for _ in range(max(height - 2, 0))] + ([top] if height > 1 else [])
        map_block = "\n".join(rows)
        lines = self.text.get("1.0", "end-1c").splitlines()
        block = [
            f"ROOM {name} name=\"{label}\"",
            "SPAWNS",
            "  S0 1,1",
            "END",
            "EXITS",
            "END",
            "OBJECTS",
            "END",
            "MAP",
            map_block,
            "END",
            "ENDROOM",
        ]
        lines += [""] + block
        self._set_text_lines(lines)
        self._log("room_add", room=name)

    def _rename_room(self) -> None:
        if not self._selected_room:
            return
        old = self._selected_room.rid
        name = simpledialog.askstring("Rename Room", "New ID:", initialvalue=old)
        if not name:
            return
        if self._level_state and any(r.rid == name for r in self._level_state.rooms if r.rid != old):
            messagebox.showerror("Room Exists", f"{name} already exists.")
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith(f"ROOM {old}"):
                parts = stripped.split()
                rest = " ".join(parts[2:]) if len(parts) > 2 else ""
                lines[idx] = f"ROOM {name} {rest}".rstrip()
                break
        for idx, raw in enumerate(lines):
            if raw.strip().startswith("LEVEL "):
                if f"start={old}:" in raw:
                    lines[idx] = raw.replace(f"start={old}:", f"start={name}:")
                break
        self._set_text_lines(lines)
        self._apply_rename_references("room", old, name)
        self._log("room_rename", old=old, new=name)

    def _remove_room(self) -> None:
        if not self._selected_room:
            return
        room_id = self._selected_room.rid
        if not messagebox.askyesno("Remove Room", f"Remove room {room_id}?"):
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        start = None
        end = None
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith(f"ROOM {room_id}"):
                start = idx
            if start is not None and stripped == "ENDROOM":
                end = idx
                break
        if start is None or end is None:
            return
        new_lines = lines[:start] + lines[end + 1:]
        self._set_text_lines(new_lines)
        self._remove_room_references(room_id)
        self._log("room_remove", room=room_id)

    def _refresh_objects_list(self) -> None:
        state = self._level_state
        if not state:
            return
        room_id = self.objects_room_var.get()
        room = self._find_room(room_id)
        names = [obj.name for obj in room.objects] if room else []
        self._set_listbox(self.objects_list, names)
        self._refresh_spawns_list(room)

    def _on_object_select_from_list(self) -> None:
        state = self._level_state
        if not state:
            return
        sel = self.objects_list.curselection()
        if not sel:
            return
        room = self._find_room(self.objects_room_var.get())
        if not room:
            return
        obj = room.objects[sel[0]]
        self._select_object(obj, room)

    def _add_object(self) -> None:
        room = self._find_room(self.objects_room_var.get())
        if not room:
            return
        self._open_object_dialog(room)

    def _remove_object(self) -> None:
        room = self._find_room(self.objects_room_var.get())
        if not room:
            return
        sel = self.objects_list.curselection()
        if not sel:
            return
        obj = room.objects[sel[0]]
        if not messagebox.askyesno("Remove Object", f"Remove {obj.name}?"):
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        if 0 <= obj.line_index < len(lines):
            del lines[obj.line_index]
        self._set_text_lines(lines)
        self._log("object_remove", room=room.rid, name=obj.name)

    def _insert_object_line(self, room: RoomEntry, name: str, x: int, y: int, type_name: str, verbs: str, props: dict | None = None) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        start_idx = None
        end_idx = None
        in_room = False
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM ") and stripped.split()[1] == room.rid:
                in_room = True
            elif in_room and stripped == "ENDROOM":
                break
            elif in_room and stripped == "OBJECTS":
                start_idx = idx
            elif start_idx is not None and in_room and stripped == "END":
                end_idx = idx
                break
        if start_idx is None or end_idx is None:
            return
        new_line = f"  {name} at {x},{y} type={type_name} verbs={verbs}"
        if props:
            for key, val in props.items():
                if val:
                    new_line += f" {key}={val}"
        lines.insert(end_idx, new_line)
        self._set_text_lines(lines)

    def _open_object_dialog(self, room: RoomEntry) -> None:
        win = tk.Toplevel(self.root)
        win.title("Add Object")
        win.transient(self.root)
        win.grab_set()

        name_var = tk.StringVar(value="O1")
        x_var = tk.StringVar(value="1")
        y_var = tk.StringVar(value="1")
        type_var = tk.StringVar(value="SIGN")
        verbs_var = tk.StringVar(value="LOOK")
        template_var = tk.StringVar(value="Custom")

        form = tk.Frame(win, padx=8, pady=8)
        form.pack(fill=tk.BOTH, expand=True)

        row = tk.Frame(form)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Template", width=10, anchor="w").pack(side=tk.LEFT)
        template_combo = ttk.Combobox(row, textvariable=template_var, values=list(OBJECT_TEMPLATES.keys()), state="readonly")
        template_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="Apply+Deps", command=lambda: apply_and_create_deps()).pack(side=tk.LEFT, padx=(6, 0))

        row = tk.Frame(form)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Name", width=10, anchor="w").pack(side=tk.LEFT)
        tk.Entry(row, textvariable=name_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = tk.Frame(form)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="X", width=10, anchor="w").pack(side=tk.LEFT)
        tk.Entry(row, textvariable=x_var, width=6).pack(side=tk.LEFT)
        tk.Label(row, text="Y", width=2, anchor="w").pack(side=tk.LEFT, padx=(6, 2))
        tk.Entry(row, textvariable=y_var, width=6).pack(side=tk.LEFT)

        row = tk.Frame(form)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Type", width=10, anchor="w").pack(side=tk.LEFT)
        type_combo = ttk.Combobox(row, textvariable=type_var, values=OBJ_TYPES, state="readonly")
        type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = tk.Frame(form)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text="Verbs", width=10, anchor="w").pack(side=tk.LEFT)
        tk.Entry(row, textvariable=verbs_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        props_frame = tk.LabelFrame(form, text="Props", padx=6, pady=6)
        props_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        props_text = tk.Text(props_frame, height=6)
        props_text.pack(fill=tk.BOTH, expand=True)

        def apply_template() -> None:
            tmpl = OBJECT_TEMPLATES.get(template_var.get(), {})
            if "type" in tmpl:
                type_var.set(tmpl["type"])
            if "verbs" in tmpl:
                verbs_var.set(tmpl["verbs"])
            props_text.delete("1.0", tk.END)
            for key, val in tmpl.get("props", {}).items():
                props_text.insert(tk.END, f"{key}={val}\n")

        def apply_and_create_deps() -> None:
            apply_template()
            props = self._parse_props_text(props_text.get("1.0", "end-1c"))
            self._ensure_object_dependencies(props)
            self._log("template_deps_create", template=template_var.get())
            self._set_status("Dependencies created.")

        def on_ok() -> None:
            name = name_var.get().strip()
            if not name:
                return
            if any(o.name == name for o in room.objects):
                messagebox.showerror("Object Exists", f"{name} already exists.")
                return
            try:
                x = int(x_var.get().strip())
                y = int(y_var.get().strip())
            except ValueError:
                messagebox.showerror("Object", "Invalid coordinates.")
                return
            type_name = type_var.get().strip() or "SIGN"
            verbs = verbs_var.get().strip() or "LOOK"
            props = self._parse_props_text(props_text.get("1.0", "end-1c"))
            self._insert_object_line(room, name, x, y, type_name, verbs, props)
            self._log("object_add", room=room.rid, name=name, template=template_var.get())
            self._ensure_object_dependencies(props)
            win.destroy()

        apply_template()
        template_combo.bind("<<ComboboxSelected>>", lambda *_: apply_template())

        actions = tk.Frame(form)
        actions.pack(fill=tk.X, pady=(6, 0))
        tk.Button(actions, text="Create", command=on_ok).pack(side=tk.RIGHT)
        tk.Button(actions, text="Cancel", command=win.destroy).pack(side=tk.RIGHT, padx=(6, 0))

    def _parse_props_text(self, text: str) -> dict:
        props = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            props[key.strip()] = val.strip()
        return props

    def _ensure_object_dependencies(self, props: dict, cond: str | None = None) -> None:
        for key in ("look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject"):
            val = props.get(key)
            if val:
                self._create_script_entry("ACT", val)
        if not cond:
            cond = props.get("cond")
        if cond:
            self._create_script_entry("COND", cond)
        item = props.get("item")
        if item:
            self._create_simple_entry("items", item)
        var = props.get("var")
        if var:
            self._create_simple_entry("vars", var)

    def _select_object(self, obj: ObjectEntry, room: RoomEntry) -> None:
        self._selected_object = obj
        self._selected_room = room
        self._load_object_inspector(obj)
        self._refresh_map()

    def _refresh_spawns_list(self, room: Optional[RoomEntry]) -> None:
        if not hasattr(self, "spawns_list"):
            return
        if not room:
            self.spawns_list.delete(0, tk.END)
            if hasattr(self, "exits_list"):
                self.exits_list.delete(0, tk.END)
            return
        spawns = [f"{sid} {coords[0]},{coords[1]}" for sid, coords in room.spawns.items()]
        self._set_listbox(self.spawns_list, spawns)
        self._refresh_exits_list(room)

    def _on_spawn_select(self) -> None:
        return

    def _add_spawn(self) -> None:
        if not self._selected_room:
            return
        sid = simpledialog.askstring("Add Spawn", "Spawn ID (e.g., S0):")
        if not sid:
            return
        if sid in self._selected_room.spawns:
            messagebox.showerror("Spawn Exists", f"{sid} already exists.")
            return
        self._update_spawn_line(self._selected_room, sid, 0, 0)
        self._log("spawn_add", room=self._selected_room.rid, spawn=sid)

    def _rename_spawn(self) -> None:
        if not self._selected_room:
            return
        sel = self.spawns_list.curselection()
        if not sel:
            return
        line = self.spawns_list.get(sel[0])
        old = line.split()[0]
        name = simpledialog.askstring("Rename Spawn", "New ID:", initialvalue=old)
        if not name:
            return
        if name in self._selected_room.spawns and name != old:
            messagebox.showerror("Spawn Exists", f"{name} already exists.")
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        start_idx = None
        end_idx = None
        in_room = False
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM ") and stripped.split()[1] == self._selected_room.rid:
                in_room = True
            elif in_room and stripped == "ENDROOM":
                break
            elif in_room and stripped == "SPAWNS":
                start_idx = idx
            elif start_idx is not None and in_room and stripped == "END":
                end_idx = idx
                break
        if start_idx is None or end_idx is None:
            return
        for idx in range(start_idx + 1, end_idx):
            if lines[idx].strip().startswith(f"{old} "):
                lines[idx] = lines[idx].replace(f"{old} ", f"{name} ", 1)
                break
        self._set_text_lines(lines)
        self._apply_rename_references("spawn", old, name)
        self._log("spawn_rename", room=self._selected_room.rid, old=old, new=name)

    def _remove_spawn(self) -> None:
        if not self._selected_room:
            return
        sel = self.spawns_list.curselection()
        if not sel:
            return
        line = self.spawns_list.get(sel[0])
        sid = line.split()[0]
        lines = self.text.get("1.0", "end-1c").splitlines()
        start_idx = None
        end_idx = None
        in_room = False
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM ") and stripped.split()[1] == self._selected_room.rid:
                in_room = True
            elif in_room and stripped == "ENDROOM":
                break
            elif in_room and stripped == "SPAWNS":
                start_idx = idx
            elif start_idx is not None and in_room and stripped == "END":
                end_idx = idx
                break
        if start_idx is None or end_idx is None:
            return
        new_lines = lines[:start_idx + 1]
        for idx in range(start_idx + 1, end_idx):
            if not lines[idx].strip().startswith(f"{sid} "):
                new_lines.append(lines[idx])
        new_lines += lines[end_idx:]
        self._set_text_lines(new_lines)

    def _refresh_exits_list(self, room: Optional[RoomEntry]) -> None:
        if not hasattr(self, "exits_list"):
            return
        if not room:
            self.exits_list.delete(0, tk.END)
            return
        exits = [f"{edge} {dest}" for edge, dest in room.exits]
        self._set_listbox(self.exits_list, exits)

    def _on_exit_select(self) -> None:
        return

    def _add_exit(self) -> None:
        if not self._selected_room or not self._level_state:
            return
        edge = simpledialog.askstring("Add Exit", "Edge (L/R/U/D):")
        if not edge:
            return
        edge = edge.strip().upper()
        if edge not in ("L", "R", "U", "D"):
            messagebox.showerror("Exit", "Edge must be L, R, U, or D.")
            return
        dest_room = simpledialog.askstring("Add Exit", "Destination room ID:")
        if not dest_room:
            return
        dest_spawn = simpledialog.askstring("Add Exit", "Destination spawn ID:")
        if not dest_spawn:
            return
        self._update_exit_line(self._selected_room, edge, f"{dest_room}:{dest_spawn}")

    def _edit_exit(self) -> None:
        if not self._selected_room:
            return
        sel = self.exits_list.curselection()
        if not sel:
            return
        line = self.exits_list.get(sel[0])
        parts = line.split()
        if len(parts) < 2:
            return
        edge = simpledialog.askstring("Edit Exit", "Edge (L/R/U/D):", initialvalue=parts[0])
        if not edge:
            return
        edge = edge.strip().upper()
        dest = simpledialog.askstring("Edit Exit", "Destination (Room:Spawn):", initialvalue=parts[1])
        if not dest:
            return
        self._update_exit_line(self._selected_room, edge, dest, index=sel[0])

    def _remove_exit(self) -> None:
        if not self._selected_room:
            return
        sel = self.exits_list.curselection()
        if not sel:
            return
        self._delete_exit_line(self._selected_room, sel[0])

    def _update_exit_line(self, room: RoomEntry, edge: str, dest: str, index: Optional[int] = None) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        start_idx = None
        end_idx = None
        in_room = False
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM ") and stripped.split()[1] == room.rid:
                in_room = True
            elif in_room and stripped == "ENDROOM":
                break
            elif in_room and stripped == "EXITS":
                start_idx = idx
            elif start_idx is not None and in_room and stripped == "END":
                end_idx = idx
                break
        if start_idx is None or end_idx is None:
            return
        new_line = f"  {edge} {dest}"
        if index is None:
            lines.insert(end_idx, new_line)
        else:
            list_idx = start_idx + 1 + index
            if list_idx < end_idx:
                lines[list_idx] = new_line
        self._set_text_lines(lines)
        self._log("exit_update", room=room.rid, edge=edge, dest=dest)
        self._set_status(f"Exit {edge} -> {dest}")

    def _delete_exit_line(self, room: RoomEntry, index: int) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        start_idx = None
        end_idx = None
        in_room = False
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM ") and stripped.split()[1] == room.rid:
                in_room = True
            elif in_room and stripped == "ENDROOM":
                break
            elif in_room and stripped == "EXITS":
                start_idx = idx
            elif start_idx is not None and in_room and stripped == "END":
                end_idx = idx
                break
        if start_idx is None or end_idx is None:
            return
        list_idx = start_idx + 1 + index
        if list_idx < end_idx:
            del lines[list_idx]
        self._set_text_lines(lines)
        self._log("exit_remove", room=room.rid, index=index)
        self._set_status("Exit removed.")

    def _load_object_inspector(self, obj: ObjectEntry) -> None:
        self.obj_name_var.set(obj.name)
        self.obj_x_var.set(str(obj.x))
        self.obj_y_var.set(str(obj.y))
        self.obj_type_var.set(obj.type_name)
        self.obj_cond_var.set(obj.cond)
        for verb, var in self.obj_verbs.items():
            var.set(1 if verb in obj.verbs.split("|") else 0)
        for key, var in self.obj_scripts.items():
            var.set(obj.props.get(key, ""))
        self.obj_item_var.set(obj.props.get("item", ""))
        self.obj_code_var.set(obj.props.get("code", ""))
        self.obj_var_var.set(obj.props.get("var", ""))
        self.obj_expect_var.set(obj.props.get("expect", ""))

    def _apply_object_changes(self) -> None:
        if not self._selected_object or not self._selected_room:
            return
        try:
            x = int(self.obj_x_var.get())
            y = int(self.obj_y_var.get())
        except ValueError:
            messagebox.showerror("Invalid Object", "X/Y must be integers.")
            return
        verbs = [verb for verb, var in self.obj_verbs.items() if var.get()]
        obj = self._selected_object
        obj.name = self.obj_name_var.get() or obj.name
        obj.x = x
        obj.y = y
        obj.type_name = self.obj_type_var.get()
        obj.cond = self.obj_cond_var.get() or "ALWAYS"
        obj.verbs = "|".join(verbs)
        props = {}
        for key, var in self.obj_scripts.items():
            val = var.get().strip()
            if val:
                props[key] = val
        if self.obj_item_var.get().strip():
            props["item"] = self.obj_item_var.get().strip()
        if self.obj_code_var.get().strip():
            props["code"] = self.obj_code_var.get().strip()
        if self.obj_var_var.get().strip():
            props["var"] = self.obj_var_var.get().strip()
        if self.obj_expect_var.get().strip():
            props["expect"] = self.obj_expect_var.get().strip()
        obj.props = props
        self._update_object_line(obj)
        self._ensure_object_dependencies(props, cond=obj.cond)

    def _apply_object_template(self) -> None:
        tmpl = OBJECT_TEMPLATES.get(self.obj_template_var.get(), {})
        if not tmpl:
            return
        if "type" in tmpl:
            self.obj_type_var.set(tmpl["type"])
        if "verbs" in tmpl:
            for verb, var in self.obj_verbs.items():
                var.set(1 if verb in tmpl["verbs"].split("|") else 0)
        for key, val in tmpl.get("props", {}).items():
            if key in self.obj_scripts:
                self.obj_scripts[key].set(val)
            elif key == "item":
                self.obj_item_var.set(val)
            elif key == "var":
                self.obj_var_var.set(val)
            elif key == "code":
                self.obj_code_var.set(val)
            elif key == "expect":
                self.obj_expect_var.set(val)
        self._log("object_template_apply", template=self.obj_template_var.get())

    def _apply_template_deps(self) -> None:
        tmpl = OBJECT_TEMPLATES.get(self.obj_template_var.get(), {})
        if not tmpl:
            return
        props = dict(tmpl.get("props", {}))
        self._ensure_object_dependencies(props, cond=self.obj_cond_var.get().strip())
        self._log("object_template_deps", template=self.obj_template_var.get())
        self._set_status("Dependencies created.")

    def _create_cond_from_inspector(self) -> None:
        name = self.obj_cond_var.get().strip()
        if not name:
            name = simpledialog.askstring("Create Condition", "COND name:")
            if not name:
                return
        self._create_script_entry("COND", name)
        self.obj_cond_var.set(name)

    def _create_act_for_field(self, field: str) -> None:
        name = self.obj_scripts[field].get().strip()
        if not name:
            name = simpledialog.askstring("Create Action", "ACT name:")
            if not name:
                return
        self._create_script_entry("ACT", name)
        self.obj_scripts[field].set(name)

    def _create_simple_from_field(self, kind: str, var: tk.StringVar) -> None:
        name = var.get().strip()
        if not name:
            name = simpledialog.askstring("Create Entry", f"{kind.upper()} name:")
            if not name:
                return
        self._create_simple_entry(kind, name)
        var.set(name)

    def _create_simple_entry(self, kind: str, name: str) -> None:
        if self._is_name_taken(kind, name):
            return
        entries = list(self._get_simple_entries(kind))
        entries.append(name)
        self._update_simple_section(kind.upper(), entries)
        self._log("create_entry", kind=kind, name=name)

    def _create_script_entry(self, kind: str, name: str) -> None:
        if self._is_name_taken("scripts", name):
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        insert_at = self._find_insert_before_room(lines)
        if kind == "COND":
            block = [f"{kind} {name}", "  TRUE", "END"]
        else:
            block = [f"{kind} {name}", "END"]
        new_lines = lines[:insert_at] + block + lines[insert_at:]
        self._set_text_lines(new_lines)
        self._log("spawn_remove", room=self._selected_room.rid, spawn=sid)
        self._log("create_script", kind=kind, name=name)

    def _update_object_line(self, obj: ObjectEntry) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        parts = [obj.name, "at", f"{obj.x},{obj.y}"]
        if obj.type_name:
            parts.append(f"type={obj.type_name}")
        if obj.verbs:
            parts.append(f"verbs={obj.verbs}")
        if obj.cond:
            parts.append(f"cond={obj.cond}")
        for key in ["look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject", "item", "code", "var", "expect"]:
            if key in obj.props:
                parts.append(f"{key}={obj.props[key]}")
        for key in sorted(obj.props.keys()):
            if key in ("look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject", "item", "code", "var", "expect"):
                continue
            parts.append(f"{key}={obj.props[key]}")
        lines[obj.line_index] = "  " + " ".join(parts)
        self._set_text_lines(lines)
        room = self._find_room(self._selected_room.rid) if self._selected_room else None
        if room:
            for updated in room.objects:
                if updated.name == obj.name:
                    self._selected_room = room
                    self._selected_object = updated
                    self._load_object_inspector(updated)
                    break
        self._log("object_update", name=obj.name, room=self._selected_room.rid if self._selected_room else None)

    def _update_object_picker_values(self) -> None:
        if not self._level_state:
            return
        conds = [script.name for script in self._level_state.conds]
        acts = [script.name for script in self._level_state.acts]
        self.obj_cond_combo["values"] = conds
        for key in self.obj_scripts:
            if key in ("look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject"):
                combo = self.obj_script_combos.get(key)
                if combo:
                    combo["values"] = acts

    def _refresh_issues(self) -> None:
        state = self._level_state
        if not state:
            return
        self._issues = []
        self._issue_actions = []
        charmap = None
        if state.level_tset and parse_tset:
            tset_full = self._resolve_tset_path(state.level_tset)
            try:
                ts = parse_tset(tset_full)
                charmap = set(ts.charmap_tiles.keys())
            except Exception:
                self._add_issue(f"TSET parse failed: {state.level_tset}")
        elif state.level_tset and not parse_tset:
            self._add_issue("TSET parser not available.")

        conds = {s.name for s in state.conds}
        acts = {s.name for s in state.acts}
        flags = set(state.flags)
        vars_ = set(state.vars)
        items = set(state.items)
        messages = {name for name, _ in state.messages}

        for room in state.rooms:
            if state.width and len(room.map_lines) != state.height:
                self._add_issue(f"{room.rid}: MAP rows != h")
            if state.width:
                for y, line in enumerate(room.map_lines):
                    if len(line) != state.width:
                        self._add_issue(f"{room.rid}: MAP row {y + 1} width != w")
                        break
            if charmap:
                for y, line in enumerate(room.map_lines):
                    for ch in line:
                        if ch not in charmap:
                            self._add_issue(f"{room.rid}: unknown tile '{ch}'")
                            break
                    if self._issues and self._issues[-1].startswith(f"{room.rid}: unknown tile"):
                        break
            for obj in room.objects:
                if obj.cond and obj.cond not in conds:
                    self._add_issue(f"{room.rid}:{obj.name} cond missing: {obj.cond}", {"kind": "cond", "name": obj.cond})
                for key in ("look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject"):
                    ref = obj.props.get(key)
                    if ref and ref not in acts:
                        self._add_issue(f"{room.rid}:{obj.name} {key} missing: {ref}", {"kind": "act", "name": ref})
            for edge, dest in room.exits:
                if ":" in dest:
                    dest_room, dest_spawn = dest.split(":", 1)
                    dest_room_obj = next((r for r in state.rooms if r.rid == dest_room), None)
                    if not dest_room_obj:
                        self._add_issue(f"{room.rid}: exit missing room {dest_room}", {"kind": "room", "name": dest_room})
                    elif dest_spawn not in dest_room_obj.spawns:
                        self._add_issue(f"{room.rid}: exit missing spawn {dest_spawn}", {"kind": "spawn", "room": dest_room, "name": dest_spawn})

        for script in state.conds:
            self._collect_cond_issues(script, flags, vars_, items)
        for script in state.acts:
            self._collect_act_issues(script, messages, flags, vars_, items, state.rooms)

        if not self._issues:
            self._issues = ["No issues found."]
            self._issue_actions = [None]
        self._set_listbox(self.issues_list, self._issues)

    def _add_issue(self, message: str, action: dict | None = None) -> None:
        self._issues.append(message)
        self._issue_actions.append(action)

    def _create_issue_selected(self) -> None:
        sel = self.issues_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if not hasattr(self, "_issue_actions") or idx >= len(self._issue_actions):
            return
        action = self._issue_actions[idx]
        if not action:
            return
        kind = action.get("kind")
        name = action.get("name")
        if kind == "flag":
            self._create_simple_entry("flags", name)
        elif kind == "var":
            self._create_simple_entry("vars", name)
        elif kind == "item":
            self._create_simple_entry("items", name)
        elif kind == "message":
            self._create_message_entry(name, "")
        elif kind == "cond":
            self._create_script_entry("COND", name)
        elif kind == "act":
            self._create_script_entry("ACT", name)
        elif kind == "room":
            self._create_room_simple(name)
        elif kind == "spawn":
            room_id = action.get("room")
            room = self._find_room(room_id) if room_id else None
            if room:
                self._update_spawn_line(room, name, 1, 1)
        self._log("issue_create", kind=kind, name=name)

    def _collect_cond_issues(
        self,
        script: ScriptEntry,
        flags: set,
        vars_: set,
        items: set,
    ) -> None:
        for line in script.lines:
            parts = line.strip().split()
            if not parts:
                continue
            op = parts[0].upper()
            if op in ("FLAGSET", "FLAGCLR") and len(parts) > 1 and parts[1] not in flags:
                self._add_issue(f"COND {script.name}: missing flag {parts[1]}", {"kind": "flag", "name": parts[1]})
            elif op == "HAS" and len(parts) > 1 and parts[1] not in items:
                self._add_issue(f"COND {script.name}: missing item {parts[1]}", {"kind": "item", "name": parts[1]})
            elif op == "VAREQ" and len(parts) > 2 and parts[1] not in vars_:
                self._add_issue(f"COND {script.name}: missing var {parts[1]}", {"kind": "var", "name": parts[1]})

    def _collect_act_issues(
        self,
        script: ScriptEntry,
        messages: set,
        flags: set,
        vars_: set,
        items: set,
        rooms: list[RoomEntry],
    ) -> None:
        room_map = {room.rid: room for room in rooms}
        for line in script.lines:
            parts = line.strip().split()
            if not parts:
                continue
            op = parts[0].upper()
            if op == "MSG" and len(parts) > 1 and parts[1] not in messages:
                self._add_issue(f"ACT {script.name}: missing message {parts[1]}", {"kind": "message", "name": parts[1]})
            elif op in ("SETFLAG", "CLRFLAG") and len(parts) > 1 and parts[1] not in flags:
                self._add_issue(f"ACT {script.name}: missing flag {parts[1]}", {"kind": "flag", "name": parts[1]})
            elif op in ("GIVE", "TAKE") and len(parts) > 1 and parts[1] not in items:
                self._add_issue(f"ACT {script.name}: missing item {parts[1]}", {"kind": "item", "name": parts[1]})
            elif op == "SETVAR" and len(parts) > 2 and parts[1] not in vars_:
                self._add_issue(f"ACT {script.name}: missing var {parts[1]}", {"kind": "var", "name": parts[1]})
            elif op == "TRANSITION" and len(parts) > 2:
                room = room_map.get(parts[1])
                if not room:
                    self._add_issue(f"ACT {script.name}: missing room {parts[1]}", {"kind": "room", "name": parts[1]})
                elif parts[2] not in room.spawns:
                    self._add_issue(f"ACT {script.name}: missing spawn {parts[2]}", {"kind": "spawn", "room": room.rid, "name": parts[2]})

    def _find_room(self, rid: str) -> Optional[RoomEntry]:
        if not self._level_state:
            return None
        for room in self._level_state.rooms:
            if room.rid == rid:
                return room
        return None

    def _on_map_room_change(self) -> None:
        rid = self.map_room_var.get()
        self._selected_room = self._find_room(rid)
        self._refresh_map()

    def _refresh_map(self) -> None:
        self.map_canvas.delete("all")
        if not self._level_state:
            return
        room = self._selected_room or self._find_room(self.map_room_var.get())
        if not room:
            return
        self._selected_room = room
        palette = self._load_palette()
        self._render_palette(palette)
        width = self._level_state.width or (len(room.map_lines[0]) if room.map_lines else 0)
        height = self._level_state.height or len(room.map_lines)
        if width <= 0 or height <= 0:
            return
        for y in range(height):
            line = room.map_lines[y] if y < len(room.map_lines) else ""
            for x in range(width):
                ch = line[x] if x < len(line) else " "
                color = self._tile_color(ch)
                x0 = x * self._map_cell
                y0 = y * self._map_cell
                self.map_canvas.create_rectangle(x0, y0, x0 + self._map_cell, y0 + self._map_cell, fill=color, outline="#222222")
                self.map_canvas.create_text(x0 + self._map_cell / 2, y0 + self._map_cell / 2, text=ch, fill="#e0e0e0")
        for obj in room.objects:
            x0 = obj.x * self._map_cell
            y0 = obj.y * self._map_cell
            self.map_canvas.create_rectangle(x0, y0, x0 + self._map_cell, y0 + self._map_cell, outline="#ff9955", width=2)
            self.map_canvas.create_text(x0 + self._map_cell / 2, y0 + 6, text=obj.name, fill="#ffcc99", anchor="n")
        for sid, (sx, sy) in room.spawns.items():
            x0 = sx * self._map_cell
            y0 = sy * self._map_cell
            self.map_canvas.create_rectangle(x0, y0, x0 + self._map_cell, y0 + self._map_cell, outline="#66ccff", width=2)
            self.map_canvas.create_text(x0 + self._map_cell / 2, y0 + self._map_cell - 4, text=sid, fill="#88ddff", anchor="s")
        self._render_exit_overlays(room, width, height)

    def _tile_color(self, ch: str) -> str:
        palette = ["#1f1f1f", "#2a2a2a", "#334455", "#445533", "#553344", "#555522", "#224455", "#333366"]
        return palette[ord(ch) % len(palette)] if ch else palette[0]

    def _render_exit_overlays(self, room: RoomEntry, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            return
        cx = (width * self._map_cell) / 2
        cy = (height * self._map_cell) / 2
        margin = self._map_cell * 0.3
        for edge, dest in room.exits:
            if edge == "L":
                x = margin
                y = cy
                points = [x, y, x + 10, y - 6, x + 10, y + 6]
            elif edge == "R":
                x = width * self._map_cell - margin
                y = cy
                points = [x, y, x - 10, y - 6, x - 10, y + 6]
            elif edge == "U":
                x = cx
                y = margin
                points = [x, y, x - 6, y + 10, x + 6, y + 10]
            elif edge == "D":
                x = cx
                y = height * self._map_cell - margin
                points = [x, y, x - 6, y - 10, x + 6, y - 10]
            else:
                continue
            self.map_canvas.create_polygon(points, fill="#ffaa44", outline="#ffcc88")
            self.map_canvas.create_text(x, y, text=dest, fill="#ffd2a0", anchor="center")

    def _load_palette(self) -> list[str]:
        chars = []
        tset_path = self._level_state.level_tset if self._level_state else None
        if tset_path and parse_tset:
            tset_full = self._resolve_tset_path(tset_path)
            try:
                ts = parse_tset(tset_full)
                chars = list(ts.charmap_tiles.keys())
            except Exception:
                chars = []
        if not chars and self._selected_room:
            for line in self._selected_room.map_lines:
                for ch in line:
                    if ch not in chars:
                        chars.append(ch)
        return chars

    def _resolve_tset_path(self, tset_path: str) -> str:
        if os.path.isabs(tset_path):
            return tset_path
        if not self.current_file:
            return tset_path
        return os.path.join(os.path.dirname(self.current_file), tset_path)

    def _render_palette(self, chars: list[str]) -> None:
        for child in self.palette_container.winfo_children():
            child.destroy()
        for ch in chars:
            btn = tk.Button(self.palette_container, text=ch, width=2, command=lambda c=ch: self._select_tile(c))
            btn.pack(side=tk.TOP, pady=2)

    def _select_tile(self, ch: str) -> None:
        self._selected_tile = ch

    def _on_map_click(self, event) -> None:
        self._map_drag_mode = None
        self._map_drag_object = None
        self._map_drag_spawn = None
        if not self._selected_room:
            return
        cell_x = event.x // self._map_cell
        cell_y = event.y // self._map_cell
        tool = self._map_tool.get()
        if tool in ("object", "paint"):
            for obj in self._selected_room.objects:
                if obj.x == cell_x and obj.y == cell_y:
                    self._map_drag_mode = "object"
                    self._map_drag_object = obj
                    self._select_object(obj, self._selected_room)
                    return
        if tool == "pick":
            self._pick_tile(cell_x, cell_y)
            return
        if tool == "spawn":
            spawn_id = self._find_spawn_at(cell_x, cell_y)
            if spawn_id:
                self._map_drag_mode = "spawn"
                self._map_drag_spawn = spawn_id
                return
            self._prompt_add_spawn(cell_x, cell_y)
            return
        self._map_drag_mode = "paint"
        self._apply_map_paint(cell_x, cell_y)

    def _on_map_drag(self, event) -> None:
        if not self._selected_room:
            return
        cell_x = event.x // self._map_cell
        cell_y = event.y // self._map_cell
        if self._map_drag_mode == "object" and self._map_drag_object:
            self._move_object_to(self._map_drag_object, cell_x, cell_y)
        elif self._map_drag_mode == "spawn" and self._map_drag_spawn:
            self._move_spawn_to(self._selected_room, self._map_drag_spawn, cell_x, cell_y)
        elif self._map_drag_mode == "paint":
            self._apply_map_paint(cell_x, cell_y)

    def _on_map_release(self, _event) -> None:
        self._map_drag_mode = None
        self._map_drag_object = None
        self._map_drag_spawn = None

    def _apply_map_paint(self, cell_x: int, cell_y: int) -> None:
        if not self._selected_room or not self._level_state or not self._selected_tile:
            return
        width = self._level_state.width or (len(self._selected_room.map_lines[0]) if self._selected_room.map_lines else 0)
        height = self._level_state.height or len(self._selected_room.map_lines)
        if cell_x < 0 or cell_x >= width or cell_y < 0 or cell_y >= height:
            return
        map_lines = self._selected_room.map_lines[:]
        while len(map_lines) < height:
            map_lines.append(" " * width)
        line = map_lines[cell_y]
        if len(line) < width:
            line = line.ljust(width)
        if cell_x < len(line) and line[cell_x] == self._selected_tile:
            return
        map_lines[cell_y] = line[:cell_x] + self._selected_tile + line[cell_x + 1:]
        self._update_room_map(self._selected_room, map_lines)
        self._log("map_paint", room=self._selected_room.rid, x=cell_x, y=cell_y, tile=self._selected_tile)

    def _pick_tile(self, cell_x: int, cell_y: int) -> None:
        if not self._selected_room:
            return
        if cell_y < 0 or cell_y >= len(self._selected_room.map_lines):
            return
        line = self._selected_room.map_lines[cell_y]
        if cell_x < 0 or cell_x >= len(line):
            return
        self._selected_tile = line[cell_x]
        self._log("tile_pick", room=self._selected_room.rid, x=cell_x, y=cell_y, tile=self._selected_tile)

    def _move_object_to(self, obj: ObjectEntry, cell_x: int, cell_y: int) -> None:
        if not self._level_state or not self._selected_room:
            return
        width = self._level_state.width or (len(self._selected_room.map_lines[0]) if self._selected_room.map_lines else 0)
        height = self._level_state.height or len(self._selected_room.map_lines)
        if cell_x < 0 or cell_x >= width or cell_y < 0 or cell_y >= height:
            return
        if obj.x == cell_x and obj.y == cell_y:
            return
        obj.x = cell_x
        obj.y = cell_y
        self._update_object_line(obj)
        self._log("object_move", name=obj.name, room=self._selected_room.rid if self._selected_room else None, x=cell_x, y=cell_y)

    def _find_spawn_at(self, cell_x: int, cell_y: int) -> Optional[str]:
        if not self._selected_room:
            return None
        for sid, (sx, sy) in self._selected_room.spawns.items():
            if sx == cell_x and sy == cell_y:
                return sid
        return None

    def _prompt_add_spawn(self, cell_x: int, cell_y: int) -> None:
        if not self._selected_room:
            return
        sid = simpledialog.askstring("Add Spawn", "Spawn ID (e.g., S0):")
        if not sid:
            return
        self._update_spawn_line(self._selected_room, sid, cell_x, cell_y)

    def _move_spawn_to(self, room: RoomEntry, sid: str, cell_x: int, cell_y: int) -> None:
        self._update_spawn_line(room, sid, cell_x, cell_y)

    def _update_spawn_line(self, room: RoomEntry, sid: str, cell_x: int, cell_y: int) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        start_idx = None
        end_idx = None
        in_room = False
        for idx, raw in enumerate(lines):
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith("ROOM ") and stripped.split()[1] == room.rid:
                in_room = True
            elif in_room and stripped == "ENDROOM":
                break
            elif in_room and stripped == "SPAWNS":
                start_idx = idx
            elif start_idx is not None and in_room and stripped == "END":
                end_idx = idx
                break
        if start_idx is None or end_idx is None:
            return
        existing_line = None
        for idx in range(start_idx + 1, end_idx):
            if lines[idx].strip().startswith(f"{sid} "):
                existing_line = idx
                break
        new_line = f"  {sid} {cell_x},{cell_y}"
        if existing_line is not None:
            lines[existing_line] = new_line
        else:
            lines.insert(end_idx, new_line)
        self._set_text_lines(lines)
        self._log("spawn_update", room=room.rid, spawn=sid, x=cell_x, y=cell_y)
        self._set_status(f"Spawn {sid} set to {cell_x},{cell_y}")

    def _apply_rename_references(self, category: str, old: str, new: str, kind: str | None = None) -> None:
        if not old or old == new:
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        updated = []
        in_messages = False
        for raw in lines:
            stripped = raw.split(";", 1)[0].strip()
            head = stripped.split()[0] if stripped else ""
            if head == "MESSAGES":
                in_messages = True
            elif head == "END":
                in_messages = False
            if in_messages and category == "messages":
                updated.append(raw)
                continue

            if category in ("Flags", "flags"):
                raw = self._replace_tokens(raw, {"FLAGSET": 1, "FLAGCLR": 1, "SETFLAG": 1, "CLRFLAG": 1}, old, new)
            elif category in ("Vars", "vars"):
                raw = self._replace_tokens(raw, {"VAREQ": 1, "SETVAR": 1}, old, new)
                raw = self._replace_kv(raw, ["var"], old, new)
            elif category in ("Items", "items"):
                raw = self._replace_tokens(raw, {"HAS": 1, "GIVE": 1, "TAKE": 1}, old, new)
                raw = self._replace_kv(raw, ["item"], old, new)
            elif category == "messages":
                raw = self._replace_tokens(raw, {"MSG": 1}, old, new)
            elif category == "scripts":
                if kind == "COND":
                    raw = self._replace_kv(raw, ["cond"], old, new)
                else:
                    raw = self._replace_kv(raw, ["look", "take", "use", "talk", "operate", "ok", "bad", "fuse", "badge", "reject"], old, new)
            elif category == "spawn":
                raw = self._replace_tokens(raw, {"TRANSITION": 2}, old, new)
            elif category == "room":
                raw = self._replace_tokens(raw, {"TRANSITION": 1}, old, new)
                raw = self._replace_exit_dest(raw, old, new)
            updated.append(raw)
        if updated != lines:
            self._set_text_lines(updated)

    def _remove_room_references(self, room_id: str) -> None:
        lines = self.text.get("1.0", "end-1c").splitlines()
        updated = []
        for raw in lines:
            stripped = raw.split(";", 1)[0].strip()
            if stripped.startswith(("L ", "R ", "U ", "D ")):
                parts = stripped.split()
                if len(parts) > 1 and parts[1].startswith(f"{room_id}:"):
                    continue
            if stripped.startswith("TRANSITION "):
                parts = stripped.split()
                if len(parts) > 1 and parts[1] == room_id:
                    continue
            updated.append(raw)
        if updated != lines:
            self._set_text_lines(updated)

    def _is_name_taken(self, category: str, name: str) -> bool:
        state = self._level_state
        if not state:
            return False
        if category in ("Flags", "flags"):
            return name in state.flags
        if category in ("Vars", "vars"):
            return name in state.vars
        if category in ("Items", "items"):
            return name in state.items
        if category == "messages":
            return any(n == name for n, _ in state.messages)
        if category == "scripts":
            return any(s.name == name for s in (state.conds + state.acts))
        return False

    def _replace_tokens(self, raw: str, token_ops: dict, old: str, new: str) -> str:
        stripped = raw.split(";", 1)[0].strip()
        if not stripped:
            return raw
        parts = stripped.split()
        op = parts[0].upper()
        if op not in token_ops:
            return raw
        target_index = token_ops.get(op, 1)
        if len(parts) > target_index and parts[target_index] == old:
            parts[target_index] = new
            return self._rebuild_line_with_indent(raw, parts)
        return raw

    def _replace_kv(self, raw: str, keys: list[str], old: str, new: str) -> str:
        def repl(match: re.Match) -> str:
            key = match.group(1)
            val = match.group(2)
            if val == old:
                return f"{key}={new}"
            return match.group(0)
        pattern = rf'({"|".join(keys)})=(\\S+)'
        return re.sub(pattern, repl, raw)

    def _replace_exit_dest(self, raw: str, old: str, new: str) -> str:
        stripped = raw.split(";", 1)[0].strip()
        if not stripped:
            return raw
        parts = stripped.split()
        if len(parts) < 2:
            return raw
        edge = parts[0].upper()
        if edge not in ("L", "R", "U", "D"):
            return raw
        if ":" not in parts[1]:
            return raw
        room_id, spawn_id = parts[1].split(":", 1)
        if room_id != old:
            return raw
        parts[1] = f"{new}:{spawn_id}"
        return self._rebuild_line_with_indent(raw, parts)

    def _rebuild_line_with_indent(self, raw: str, parts: list[str]) -> str:
        prefix = ""
        for ch in raw:
            if ch.isspace():
                prefix += ch
            else:
                break
        return prefix + " ".join(parts)

    def _update_room_map(self, room: RoomEntry, map_lines: list[str]) -> None:
        if room.map_start is None or room.map_end is None:
            return
        lines = self.text.get("1.0", "end-1c").splitlines()
        start = room.map_start
        end = room.map_end
        new_block = [lines[start]] + map_lines + [lines[end]]
        lines = lines[:start] + new_block + lines[end + 1:]
        self._set_text_lines(lines)

    def undo(self) -> None:
        try:
            self.text.edit_undo()
        except tk.TclError:
            return

    def redo(self) -> None:
        try:
            self.text.edit_redo()
        except tk.TclError:
            return

    def _load_recent(self) -> None:
        if not os.path.isfile(self.recent_path):
            return
        try:
            with open(self.recent_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, list):
            self.recent_files = [p for p in data if isinstance(p, str)]
        self._refresh_recent_menu()

    def _save_recent(self) -> None:
        os.makedirs(self.recent_dir, exist_ok=True)
        try:
            with open(self.recent_path, "w", encoding="utf-8") as f:
                json.dump(self.recent_files, f, indent=2)
        except OSError:
            pass

    def _push_recent(self, path: str) -> None:
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self._save_recent()
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.delete(0, tk.END)
        valid = [p for p in self.recent_files if os.path.isfile(p)]
        self.recent_files = valid
        if not valid:
            self.recent_menu.add_command(label="(empty)", state=tk.DISABLED)
            return
        for path in valid:
            self.recent_menu.add_command(
                label=path,
                command=lambda p=path: self._open_recent(p),
            )

    def _open_recent(self, path: str) -> None:
        if not self._confirm_discard():
            return
        self._load_file(path)

    def _on_close(self) -> None:
        if not self._confirm_discard():
            return
        self.root.destroy()

    def _default_template(self) -> str:
        w = 20
        h = 12
        top = "#" * w
        middle = "#" + "." * (w - 2) + "#"
        rows = [top] + [middle for _ in range(h - 2)] + [top]
        map_block = "\n".join(rows)
        return (
            'LEVEL name="NEW LEVEL" w=20 h=12 start=R0:S0 tset=your.tset\n\n'
            "FLAGS\n"
            "END\n\n"
            "VARS\n"
            "END\n\n"
            "ITEMS\n"
            "END\n\n"
            "MESSAGES\n"
            "END\n\n"
            "COND ALWAYS\n"
            "  TRUE\n"
            "END\n\n"
            'ROOM R0 name="Room 0"\n'
            "SPAWNS\n"
            "  S0 1,1\n"
            "END\n"
            "EXITS\n"
            "END\n"
            "OBJECTS\n"
            "END\n"
            "MAP\n"
            f"{map_block}\n"
            "END\n"
            "ENDROOM\n"
        )

    def _set_status(self, message: str) -> None:
        self.status.config(text=message)
        self.root.after(3000, lambda: self.status.config(text="Ready."))

    def _set_text_lines(self, lines: list[str], mark_dirty: bool = True) -> None:
        self._loading = True
        try:
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", "\n".join(lines))
        finally:
            self._loading = False
        if mark_dirty:
            self._set_dirty(True)
        self._refresh_structure()

    def _init_logging(self) -> None:
        try:
            os.makedirs(self._log_dir, exist_ok=True)
        except OSError:
            self._log_dir = None
            self._log_path = None
        self._log("app_start")

    def _log(self, event: str, **data) -> None:
        if not self._log_path:
            return
        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": event,
            "file": self.current_file,
        }
        payload.update(data)
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except OSError:
            return
        self._refresh_log_view()

    def _refresh_log_view(self) -> None:
        if not hasattr(self, "log_view"):
            return
        if not self._log_path or not os.path.isfile(self._log_path):
            self.log_view.delete("1.0", tk.END)
            self.log_view.insert("1.0", "Log file not available.")
            return
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return
        tail = lines[-200:]
        self.log_view.delete("1.0", tk.END)
        self.log_view.insert("1.0", "".join(tail))
        self.log_view.see(tk.END)

    def _refresh_guided_checklist(self) -> None:
        if not hasattr(self, "guided_checklist"):
            return
        self.guided_checklist.delete(0, tk.END)
        checks = self._guided_status()
        for label, done in checks:
            status = "[x]" if done else "[ ]"
            self.guided_checklist.insert(tk.END, f"{status} {label}")

    def _guided_status(self) -> list[tuple[str, bool]]:
        state = self._level_state
        has_level = bool(state and state.level_line is not None)
        has_tset = bool(state and state.level_tset)
        has_room = bool(state and state.rooms)
        has_map = bool(state and any(room.map_lines for room in state.rooms))
        has_spawns = bool(state and any(room.spawns for room in state.rooms))
        has_objects = bool(state and any(room.objects for room in state.rooms))
        has_scripts = bool(state and (state.conds or state.acts))
        has_messages = bool(state and state.messages)
        return [
            ("LEVEL header", has_level),
            ("TSET set", has_tset),
            ("At least one room", has_room),
            ("Room map data", has_map),
            ("Spawns added", has_spawns),
            ("Objects placed", has_objects),
            ("Scripts created", has_scripts),
            ("Messages created", has_messages),
        ]

    def _start_guided_wizard(self) -> None:
        self._select_data_tab("Workflow")
        self._set_status("Guided wizard: follow the prompts.")
        if not self._level_state or not self._level_state.level_tset:
            if messagebox.askyesno("Wizard", "Set TSET now?"):
                self.set_tset()
        if not self._level_state or not self._level_state.rooms:
            if messagebox.askyesno("Wizard", "Add a room now?"):
                self._add_room()
        if self._level_state and self._level_state.rooms:
            self._selected_room = self._level_state.rooms[0]
            self.map_room_var.set(self._selected_room.rid)
        if messagebox.askyesno("Wizard", "Open map editor?"):
            self._select_editor_tab("Map")
        self._refresh_guided_checklist()

    def _guided_next_step(self) -> None:
        state = self._level_state
        if not state or state.level_line is None:
            self._select_editor_tab("LVL Text")
            self._set_status("Add a LEVEL header.")
            return
        if not state.level_tset:
            self.set_tset()
            return
        if not state.rooms:
            self._add_room()
            return
        if not any(room.map_lines for room in state.rooms):
            self._select_editor_tab("Map")
            self._set_status("Draw the room map.")
            return
        if not any(room.spawns for room in state.rooms):
            self._select_data_tab("Rooms")
            self._set_status("Add spawns.")
            return
        if not any(room.objects for room in state.rooms):
            self._select_data_tab("Objects")
            self._set_status("Add objects.")
            return
        if not (state.conds or state.acts):
            self._select_data_tab("Scripts")
            self._set_status("Create scripts.")
            return
        if not state.messages:
            self._select_data_tab("Messages")
            self._set_status("Add messages.")
            return
        self._set_status("Workflow complete.")


def main() -> None:
    root = tk.Tk()
    app = LvlEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
