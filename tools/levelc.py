#!/usr/bin/env python3
"""
levelc.py - LVLTEXT -> packed binary level blob + generated C headers/C blob + .sym map.

Outputs:
  - .bin           Packed binary level blob (offset-based)
  - *_ids.h        Enums for flags/vars/items/messages + ObjType constants
  - .sym           Human-readable symbol map (offsets, rooms, objects, scripts, messages)
  - .c/.h          Embeds blob as C uint8_t array + exports size
  - level_format.h Inline accessors/constants for reading the blob in C

Usage:
  python tools/levelc.py levels/level1.lvl

By default this writes all required output files into the tools/ folder, using the
LEVEL name as the base filename (sanitized to a safe identifier).

Notes:
- Comments start with ';' (so '#' is safe for tiles).
- MAP rows must match w,h exactly, and all chars must exist in TILES mapping.
- Conditions are AND-only bytecode. Actions are linear bytecode.
- Approach A routing:
    * LOCKER_KEYPAD: p0/p1 = code (hundreds, remainder); alt0=ok script; alt1=bad script
    * BREAKER_PANEL: p0 = varId to write; p1 = expectedBits (0..7) from expect=; alt0=ok; alt1=bad
    * HATCH_PANEL: alt0=fuse script, alt1=badge script, use=reject script (optional)

LVLTEXT format summary (minimal):
  LEVEL name="..." w=20 h=12 start=R0:S0
  TILES
    . 0
    # 1
  END
  FLAGS ... END
  VARS  ... END
  ITEMS ... END
  MESSAGES
    MSGID = "text"
  END
  COND NAME
    TRUE | FLAGSET X | FLAGCLR X | HAS ITEM | VAREQ VAR value
  END
  ACT NAME
    MSG ID | SETFLAG X | CLRFLAG X | GIVE ITEM | TAKE ITEM | SETVAR VAR value | SFX n | TRANSITION Rn Sn
  END
  ROOM R0 name="..."
    SPAWNS ... END
    EXITS  ... END
    OBJECTS ... END
    MAP ... END
  ENDROOM
"""

from __future__ import annotations
import argparse
import json
import os
import re
import struct
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ----------------------------
# Error collection
# ----------------------------

class ErrorCollector:
    """Collects errors during parsing and compilation instead of immediately raising exceptions."""

    def __init__(self):
        self.errors: List[str] = []

    def add_error(self, error: str):
        """Add an error to the collection."""
        self.errors.append(error)

    def has_errors(self) -> bool:
        """Check if any errors have been collected."""
        return len(self.errors) > 0

    def report_and_exit(self, prefix: str = ""):
        """Report all collected errors and exit if any exist."""
        if not self.has_errors():
            return

        print(f"\n{prefix}Found {len(self.errors)} error(s):", file=sys.stderr)
        for i, error in enumerate(self.errors, 1):
            print(f"  {i}. {error}", file=sys.stderr)
        print("", file=sys.stderr)
        sys.exit(1)


# ----------------------------
# Bytecode opcodes
# ----------------------------

# Conditions: [op,a,b] ... C_END
C_END = 0
C_TRUE = 1
C_FLAG_SET = 2
C_FLAG_CLR = 3
C_HAS_ITEM = 4
C_VAR_EQ = 5

COND_OPS = {
    "END": C_END,
    "TRUE": C_TRUE,
    "FLAGSET": C_FLAG_SET,
    "FLAGCLR": C_FLAG_CLR,
    "HAS": C_HAS_ITEM,
    "VAREQ": C_VAR_EQ,
}

# Actions: [op,a,b] ... A_END
A_END = 0
A_SHOW_MSG = 1
A_SET_FLAG = 2
A_CLR_FLAG = 3
A_GIVE_ITEM = 4
A_TAKE_ITEM = 5
A_SET_VAR = 6
A_SFX = 7
A_TRANSITION = 8

ACT_OPS = {
    "END": A_END,
    "MSG": A_SHOW_MSG,
    "SETFLAG": A_SET_FLAG,
    "CLRFLAG": A_CLR_FLAG,
    "GIVE": A_GIVE_ITEM,
    "TAKE": A_TAKE_ITEM,
    "SETVAR": A_SET_VAR,
    "SFX": A_SFX,
    "TRANSITION": A_TRANSITION,
}

VERB_BITS = {
    "LOOK": 1 << 0,
    "TAKE": 1 << 1,
    "USE": 1 << 2,
    "TALK": 1 << 3,
    "OPERATE": 1 << 4,
}

EXIT_TYPES = {"L": 0, "R": 1, "U": 2, "D": 3}

# Object types: keep in sync with engine.
OBJ_TYPES = {
    "SIGN": 1,
    "PICKUP": 2,
    "LOCKER_KEYPAD": 3,
    "BREAKER_PANEL": 4,
    "HATCH_PANEL": 5,
    "EXIT_TRIGGER": 6,
    "NPC_INTERCOM": 7,
}

# Binary format constants
LEVEL_MAGIC = b"LVL1"
LEVEL_VERSION = 1

# Header layout (packed):
# <4s 10B 4H = 22 bytes
HEADER_SIZE = 22

# Offsets in header (bytes)
HDR_OFS_MAGIC = 0
HDR_OFS_VERSION = 4
HDR_OFS_ROOMCOUNT = 5
HDR_OFS_MAPW = 6
HDR_OFS_MAPH = 7
HDR_OFS_FLAGCOUNT = 8
HDR_OFS_VARCOUNT = 9
HDR_OFS_ITEMCOUNT = 10
HDR_OFS_MSGCOUNT = 11
HDR_OFS_STARTROOM = 12
HDR_OFS_STARTSPAWN = 13
HDR_OFS_ROOMDIR = 14  # uint16_t
HDR_OFS_CONDSTREAM = 16  # uint16_t
HDR_OFS_ACTSTREAM = 18  # uint16_t
HDR_OFS_MSGTABLE = 20  # uint16_t

ROOM_DIRENTRY_SIZE = 8  # 4x uint16_t
OBJ_RECORD_SIZE = 22  # fixed in this tool


# ----------------------------
# Data models
# ----------------------------


@dataclass
class ScriptDef:
    name: str
    kind: str  # "COND" or "ACT"
    lines: List[str] = field(default_factory=list)


@dataclass
class ObjDef:
    name: str
    x: int
    y: int
    type_name: str
    verbs: int
    props: Dict[str, str] = field(default_factory=dict)
    cond_name: str = "ALWAYS"
    # script refs (actions)
    look: str = ""
    take: str = ""
    use: str = ""  # under Approach A this is often "reject"
    talk: str = ""
    operate: str = ""
    # alt scripts (type-specific)
    alt0: str = ""  # keypad/breaker ok, hatch fuse
    alt1: str = ""  # keypad/breaker bad, hatch badge


@dataclass
class RoomDef:
    room_id: str
    name: str
    spawns: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # "S0" -> (x,y)
    exits: List[Tuple[str, str, str]] = field(
        default_factory=list
    )  # (edge "L", destRoomId, destSpawnId)
    objects: List[ObjDef] = field(default_factory=list)
    map_lines: List[str] = field(default_factory=list)


@dataclass
class LevelDef:
    name: str
    w: int
    h: int
    start_room: str
    start_spawn: str
    tiles: Dict[str, int] = field(default_factory=dict)
    flags: List[str] = field(default_factory=list)
    vars: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    messages: Dict[str, str] = field(default_factory=dict)
    conds: Dict[str, ScriptDef] = field(default_factory=dict)
    acts: Dict[str, ScriptDef] = field(default_factory=dict)
    rooms: Dict[str, RoomDef] = field(default_factory=dict)


# ----------------------------
# Parser
# ----------------------------

TOKEN_KV = re.compile(r'(\w+)=(".*?"|\S+)')


def _strip_comment(line: str) -> str:
    # Comments start with ';' so '#' can be used for tiles.
    if ";" in line:
        return line.split(";", 1)[0].rstrip()
    return line.rstrip()


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _parse_kv(line: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in TOKEN_KV.finditer(line):
        out[m.group(1)] = _unquote(m.group(2))
    return out


def parse_lvltext(path: str, errors: ErrorCollector) -> Optional[LevelDef]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        errors.add_error(f"Input file not found: {path}")
        return None
    except PermissionError:
        errors.add_error(f"Permission denied reading file: {path}")
        return None
    except UnicodeDecodeError as e:
        errors.add_error(f"File encoding error: {e}")
        return None
    except Exception as e:
        errors.add_error(f"Error reading file: {e}")
        return None

    lines: List[str] = []
    for ln in raw_lines:
        s = _strip_comment(ln)
        if s.strip():
            lines.append(s)

    level: Optional[LevelDef] = None
    cur_room: Optional[RoomDef] = None
    mode: Optional[str] = None
    cur_script: Optional[ScriptDef] = None
    level_found = False

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1

        if line == "END":
            if cur_script:
                if cur_script.kind == "COND":
                    level.conds[cur_script.name] = cur_script
                else:
                    level.acts[cur_script.name] = cur_script
                cur_script = None
            mode = None
            continue

        if line == "ENDROOM":
            if not level or not cur_room:
                errors.add_error("ENDROOM without ROOM")
                continue
            level.rooms[cur_room.room_id] = cur_room
            cur_room = None
            mode = None
            continue

        if cur_script is not None:
            cur_script.lines.append(line)
            continue

        if mode == "MAP":
            if not cur_room:
                errors.add_error("MAP outside ROOM")
                continue
            cur_room.map_lines.append(line)
            continue

        parts = line.split()
        if not parts:
            continue  # Skip empty lines
        head = parts[0]

        if head == "LEVEL":
            level_found = True
            kv = _parse_kv(line)
            if "w" not in kv or "h" not in kv or "start" not in kv:
                errors.add_error("LEVEL requires w=, h=, start=R?:S?")
                continue
            try:
                start_room, start_spawn = kv["start"].split(":")
                level = LevelDef(
                    name=kv.get("name", "UNNAMED"),
                    w=int(kv["w"]),
                    h=int(kv["h"]),
                    start_room=start_room,
                    start_spawn=start_spawn,
                )
            except ValueError as e:
                errors.add_error(f"Invalid LEVEL values: {e}")
            continue

        if not level_found:
            errors.add_error(f"Expected LEVEL block, found: {line}")
            # Don't break - continue parsing to find more errors
            continue

        if level is None:
            # Level block was found but was invalid, continue parsing but skip level-dependent operations
            continue

        if head in ("TILES", "FLAGS", "VARS", "ITEMS", "MESSAGES"):
            mode = head
            continue

        if head == "COND":
            if len(parts) < 2:
                errors.add_error(f"COND missing name: {line}")
                continue
            cur_script = ScriptDef(name=parts[1], kind="COND")
            continue

        if head == "ACT":
            if len(parts) < 2:
                errors.add_error(f"ACT missing name: {line}")
                continue
            cur_script = ScriptDef(name=parts[1], kind="ACT")
            continue

        if head == "ROOM":
            if len(parts) < 2:
                errors.add_error(f"ROOM missing id: {line}")
                continue
            kv = _parse_kv(line)
            rid = parts[1]
            cur_room = RoomDef(room_id=rid, name=kv.get("name", rid))
            mode = None
            continue

        if head in ("SPAWNS", "EXITS", "OBJECTS", "MAP"):
            if not cur_room:
                errors.add_error(f"{head} outside ROOM")
                continue
            mode = head
            continue

        # --- Mode handlers ---
        if mode == "TILES":
            ch = parts[0]
            if len(ch) != 1:
                errors.add_error(f"TILES key must be a single char: {ch}")
                continue
            try:
                level.tiles[ch] = int(parts[1], 0)
            except ValueError:
                errors.add_error(f"TILES invalid value for '{ch}': {parts[1]}")
            continue

        if mode == "FLAGS":
            level.flags.append(parts[0])
            continue

        if mode == "VARS":
            level.vars.append(parts[0])
            continue

        if mode == "ITEMS":
            level.items.append(parts[0])
            continue

        if mode == "MESSAGES":
            m = re.match(r'^(\w+)\s*=\s*"(.*)"$', line)
            if not m:
                errors.add_error(f"Bad message line: {line}")
                continue
            level.messages[m.group(1)] = m.group(2)
            continue

        if mode == "SPAWNS":
            if len(parts) < 2:
                errors.add_error(f"SPAWNS line missing position: {line}")
                continue
            sid = parts[0]
            try:
                x, y = parts[1].split(",")
                cur_room.spawns[sid] = (int(x), int(y))
            except ValueError:
                errors.add_error(f"SPAWNS invalid position for '{sid}': {parts[1]}")
            continue

        if mode == "EXITS":
            if len(parts) < 2:
                errors.add_error(f"EXITS line missing destination: {line}")
                continue
            edge = parts[0]
            try:
                dest_room, dest_spawn = parts[1].split(":")
                cur_room.exits.append((edge, dest_room, dest_spawn))
            except ValueError:
                errors.add_error(f"EXITS invalid destination format: {parts[1]}")
            continue

        if mode == "OBJECTS":
            # O1 at 3,2 type=SIGN verbs=LOOK|OPERATE look=... cond=...
            if len(parts) < 4 or parts[1] != "at":
                errors.add_error(f"Bad OBJECT line: {line}")
                continue

            oname = parts[0]
            try:
                x_str, y_str = parts[2].split(",")
            except ValueError:
                errors.add_error(f"Bad OBJECT position in line: {line}")
                continue

            kv = _parse_kv(line)

            type_name = kv.get("type", "")
            verbs_str = kv.get("verbs", "")
            if not type_name or not verbs_str:
                errors.add_error(f"Object missing type/verbs: {line}")
                continue

            verbs = 0
            for v in verbs_str.split("|"):
                v = v.strip().upper()
                if v not in VERB_BITS:
                    errors.add_error(f"Unknown verb {v} in {line}")
                    continue
                verbs |= VERB_BITS[v]

            try:
                obj = ObjDef(
                    name=oname,
                    x=int(x_str),
                    y=int(y_str),
                    type_name=type_name,
                    verbs=verbs,
                )
            except ValueError:
                errors.add_error(f"Invalid OBJECT coordinates for '{oname}': {x_str},{y_str}")
                continue

            obj.cond_name = kv.get("cond", "ALWAYS")
            obj.look = kv.get("look", "")
            obj.take = kv.get("take", "")
            obj.use = kv.get("use", "")  # generic use; often unused in Approach A
            obj.talk = kv.get("talk", "")
            obj.operate = kv.get("operate", "")

            # Type-specific scripts:
            # keypad/breaker: ok/bad -> alt0/alt1
            if "ok" in kv:
                obj.alt0 = kv["ok"]
            if "bad" in kv:
                obj.alt1 = kv["bad"]

            # hatch: fuse/badge -> alt0/alt1, reject -> use
            if "fuse" in kv:
                obj.alt0 = kv["fuse"]
            if "badge" in kv:
                obj.alt1 = kv["badge"]
            if "reject" in kv:
                obj.use = kv["reject"]

            # Remaining properties
            for k, v in kv.items():
                if k in (
                    "type",
                    "verbs",
                    "cond",
                    "look",
                    "take",
                    "use",
                    "talk",
                    "operate",
                    "ok",
                    "bad",
                    "fuse",
                    "badge",
                    "reject",
                ):
                    continue
                obj.props[k] = v

            cur_room.objects.append(obj)
            continue

        errors.add_error(f"Unexpected line: {line}")

    if level is None:
        errors.add_error("No LEVEL block found")
        # Create a minimal level structure so compilation can still run and find more errors
        level = LevelDef(
            name="INVALID_LEVEL",
            w=1, h=1,
            start_room="R0",
            start_spawn="S0"
        )

    # Don't return None here - let compilation run to find more errors
    # The error collector will handle reporting all errors at the end

    # Ensure default ALWAYS condition exists
    if "ALWAYS" not in level.conds:
        level.conds["ALWAYS"] = ScriptDef(name="ALWAYS", kind="COND", lines=["TRUE"])

    return level


# ----------------------------
# Compiler helpers
# ----------------------------


def _u16(n: int) -> bytes:
    return struct.pack("<H", n & 0xFFFF)


def _ascii_bytes(s: str) -> bytes:
    # Keep it simple: ASCII + null terminator.
    return s.encode("ascii", errors="replace") + b"\x00"


def _pack_enum_header(name: str, entries: List[str]) -> str:
    out = [f"typedef enum {name} : unsigned char {{\n"]
    for idx, e in enumerate(entries):
        out.append(f"  {e} = {idx},\n")
    out.append(f"  {name}__COUNT = {len(entries)}\n")
    out.append(f"}} {name};\n\n")
    return "".join(out)


def _resolve_id(name: str, table: Dict[str, int], kind: str, errors: Optional[ErrorCollector] = None) -> int:
    if name not in table:
        if errors:
            errors.add_error(f"Unknown {kind} id: {name}")
            return 0  # Return a safe default
        else:
            # For backwards compatibility when no error collector is provided
            raise ValueError(f"Unknown {kind} id: {name}")
    return table[name]


def compile_cond_script(
    lines: List[str],
    flag_ids: Dict[str, int],
    var_ids: Dict[str, int],
    item_ids: Dict[str, int],
    errors: ErrorCollector,
) -> bytes:
    b = bytearray()
    for raw in lines:
        parts = raw.strip().split()
        if not parts:
            continue
        op = parts[0].upper()
        if op not in COND_OPS:
            errors.add_error(f"Unknown COND op: {op}")
            continue
        code = COND_OPS[op]
        a = 0
        c = 0
        if code in (C_FLAG_SET, C_FLAG_CLR):
            if len(parts) < 2:
                errors.add_error(f"COND op {op} requires a flag name")
                continue
            a = _resolve_id(parts[1], flag_ids, "FLAG", errors)
        elif code == C_HAS_ITEM:
            if len(parts) < 2:
                errors.add_error(f"COND op {op} requires an item name")
                continue
            a = _resolve_id(parts[1], item_ids, "ITEM", errors)
        elif code == C_VAR_EQ:
            if len(parts) < 3:
                errors.add_error(f"COND op {op} requires a var name and value")
                continue
            a = _resolve_id(parts[1], var_ids, "VAR", errors)
            try:
                c = int(parts[2], 0) & 0xFF
            except ValueError:
                errors.add_error(f"COND op {op} has invalid value: {parts[2]}")
        elif code == C_TRUE:
            pass
        elif code == C_END:
            break
        b += bytes([code, a & 0xFF, c & 0xFF])
    b += bytes([C_END, 0, 0])
    return bytes(b)


def compile_act_script(
    lines: List[str],
    msg_ids: Dict[str, int],
    flag_ids: Dict[str, int],
    var_ids: Dict[str, int],
    item_ids: Dict[str, int],
    room_ids: Dict[str, int],
    spawn_ids_by_room: Dict[str, Dict[str, int]],
    errors: ErrorCollector,
) -> bytes:
    b = bytearray()
    for raw in lines:
        parts = raw.strip().split()
        if not parts:
            continue
        op = parts[0].upper()
        if op not in ACT_OPS:
            errors.add_error(f"Unknown ACT op: {op}")
            continue
        code = ACT_OPS[op]
        a = 0
        c = 0

        if code == A_SHOW_MSG:
            if len(parts) < 2:
                errors.add_error(f"ACT op {op} requires a message name")
                continue
            a = _resolve_id(parts[1], msg_ids, "MSG", errors)
        elif code in (A_SET_FLAG, A_CLR_FLAG):
            if len(parts) < 2:
                errors.add_error(f"ACT op {op} requires a flag name")
                continue
            a = _resolve_id(parts[1], flag_ids, "FLAG", errors)
        elif code in (A_GIVE_ITEM, A_TAKE_ITEM):
            if len(parts) < 2:
                errors.add_error(f"ACT op {op} requires an item name")
                continue
            a = _resolve_id(parts[1], item_ids, "ITEM", errors)
        elif code == A_SET_VAR:
            if len(parts) < 3:
                errors.add_error(f"ACT op {op} requires a var name and value")
                continue
            a = _resolve_id(parts[1], var_ids, "VAR", errors)
            try:
                c = int(parts[2], 0) & 0xFF
            except ValueError:
                errors.add_error(f"ACT op {op} has invalid value: {parts[2]}")
        elif code == A_SFX:
            if len(parts) < 2:
                errors.add_error(f"ACT op {op} requires a sound id")
                continue
            try:
                a = int(parts[1], 0) & 0xFF
            except ValueError:
                errors.add_error(f"ACT op {op} has invalid sound id: {parts[1]}")
        elif code == A_TRANSITION:
            if len(parts) < 3:
                errors.add_error(f"ACT op {op} requires room and spawn")
                continue
            dest_room = parts[1]
            dest_spawn = parts[2]
            a = _resolve_id(dest_room, room_ids, "ROOM", errors)
            if (
                dest_room not in spawn_ids_by_room
                or dest_spawn not in spawn_ids_by_room[dest_room]
            ):
                errors.add_error(
                    f"Unknown spawn {dest_spawn} in room {dest_room} for TRANSITION"
                )
            else:
                c = spawn_ids_by_room[dest_room][dest_spawn] & 0xFF
        elif code == A_END:
            break

        b += bytes([code, a & 0xFF, c & 0xFF])
    b += bytes([A_END, 0, 0])
    return bytes(b)


# ----------------------------
# C generation helpers
# ----------------------------


def blob_to_c_array(blob: bytes, array_name: str) -> str:
    # 12 bytes per line is readable
    lines: List[str] = []
    lines.append(f"const uint8_t {array_name}[] = {{\n")
    for i in range(0, len(blob), 12):
        chunk = blob[i : i + 12]
        hexes = ",".join(f"0x{b:02X}" for b in chunk)
        lines.append(f"  {hexes},\n")
    lines.append("};\n")
    lines.append(
        f"const uint32_t {array_name}_size = (uint32_t)sizeof({array_name});\n"
    )
    return "".join(lines)


def blob_to_c_embed(bin_path: str, array_name: str) -> str:
    return (
        f"const uint8_t {array_name}[] = {{\n"
        f"#embed \"{bin_path}\"\n"
        f"}};\n"
        f"const uint32_t {array_name}_size = (uint32_t)sizeof({array_name});\n"
    )


def make_blob_h(array_name: str) -> str:
    guard = array_name.upper() + "_H"
    return (
        f"#pragma once\n"
        f"#include <stdint.h>\n\n"
        f"extern const uint8_t {array_name}[];\n"
        f"extern const uint32_t {array_name}_size;\n"
    )


def make_format_h() -> str:
    # This is your “easy implementation” glue: stable constants + safe rd8/rd16 + accessors.
    return f"""#pragma once
#include <stdint.h>

/* Auto-generated (or tool-provided) format header for LVL1 blobs.
   Keep this in sync with levelc.py. */

#define LVL_MAGIC_0 'L'
#define LVL_MAGIC_1 'V'
#define LVL_MAGIC_2 'L'
#define LVL_MAGIC_3 '1'
#define LVL_VERSION 1

#define LVL_HEADER_SIZE {HEADER_SIZE}
#define LVL_ROOM_DIRENTRY_SIZE {ROOM_DIRENTRY_SIZE}
#define LVL_OBJ_RECORD_SIZE {OBJ_RECORD_SIZE}

/* Header field offsets (byte offsets into blob) */
#define LVL_HDR_OFS_VERSION      {HDR_OFS_VERSION}
#define LVL_HDR_OFS_ROOMCOUNT    {HDR_OFS_ROOMCOUNT}
#define LVL_HDR_OFS_MAPW         {HDR_OFS_MAPW}
#define LVL_HDR_OFS_MAPH         {HDR_OFS_MAPH}
#define LVL_HDR_OFS_FLAGCOUNT    {HDR_OFS_FLAGCOUNT}
#define LVL_HDR_OFS_VARCOUNT     {HDR_OFS_VARCOUNT}
#define LVL_HDR_OFS_ITEMCOUNT    {HDR_OFS_ITEMCOUNT}
#define LVL_HDR_OFS_MSGCOUNT     {HDR_OFS_MSGCOUNT}
#define LVL_HDR_OFS_STARTROOM    {HDR_OFS_STARTROOM}
#define LVL_HDR_OFS_STARTSPAWN   {HDR_OFS_STARTSPAWN}
#define LVL_HDR_OFS_ROOMDIR      {HDR_OFS_ROOMDIR}
#define LVL_HDR_OFS_CONDSTREAM   {HDR_OFS_CONDSTREAM}
#define LVL_HDR_OFS_ACTSTREAM    {HDR_OFS_ACTSTREAM}
#define LVL_HDR_OFS_MSGTABLE     {HDR_OFS_MSGTABLE}

/* Object record field offsets (byte offsets relative to object record base) */
#define LVL_OBJ_OFS_X        0
#define LVL_OBJ_OFS_Y        1
#define LVL_OBJ_OFS_TYPE     2
#define LVL_OBJ_OFS_VERBS    3
#define LVL_OBJ_OFS_P0       4
#define LVL_OBJ_OFS_P1       5
#define LVL_OBJ_OFS_CONDS    6   /* uint16_t */
#define LVL_OBJ_OFS_LOOK     8   /* uint16_t */
#define LVL_OBJ_OFS_TAKE     10  /* uint16_t */
#define LVL_OBJ_OFS_USE      12  /* uint16_t */
#define LVL_OBJ_OFS_TALK     14  /* uint16_t */
#define LVL_OBJ_OFS_OPERATE  16  /* uint16_t */
#define LVL_OBJ_OFS_ALT0     18  /* uint16_t */
#define LVL_OBJ_OFS_ALT1     20  /* uint16_t */

/* Condition opcodes (bytecode triples [op,a,b]) */
#define C_END       {C_END}
#define C_TRUE      {C_TRUE}
#define C_FLAG_SET  {C_FLAG_SET}
#define C_FLAG_CLR  {C_FLAG_CLR}
#define C_HAS_ITEM  {C_HAS_ITEM}
#define C_VAR_EQ    {C_VAR_EQ}

/* Action opcodes (bytecode triples [op,a,b]) */
#define A_END        {A_END}
#define A_SHOW_MSG   {A_SHOW_MSG}
#define A_SET_FLAG   {A_SET_FLAG}
#define A_CLR_FLAG   {A_CLR_FLAG}
#define A_GIVE_ITEM  {A_GIVE_ITEM}
#define A_TAKE_ITEM  {A_TAKE_ITEM}
#define A_SET_VAR    {A_SET_VAR}
#define A_SFX        {A_SFX}
#define A_TRANSITION {A_TRANSITION}

/* Verbs bitmask */
#define VB_LOOK    (1<<0)
#define VB_TAKE    (1<<1)
#define VB_USE     (1<<2)
#define VB_TALK    (1<<3)
#define VB_OPERATE (1<<4)

/* Exits */
#define EXIT_L 0
#define EXIT_R 1
#define EXIT_U 2
#define EXIT_D 3

static inline uint8_t lvl_rd8(const uint8_t* b, uint16_t o) {{
  return b[o];
}}
static inline uint16_t lvl_rd16(const uint8_t* b, uint16_t o) {{
  return (uint16_t)b[o] | ((uint16_t)b[o+1] << 8);
}}

static inline uint16_t lvl_roomdir_ofs(const uint8_t* b) {{
  return lvl_rd16(b, LVL_HDR_OFS_ROOMDIR);
}}
static inline uint16_t lvl_condstream_ofs(const uint8_t* b) {{
  return lvl_rd16(b, LVL_HDR_OFS_CONDSTREAM);
}}
static inline uint16_t lvl_actstream_ofs(const uint8_t* b) {{
  return lvl_rd16(b, LVL_HDR_OFS_ACTSTREAM);
}}
static inline uint16_t lvl_msgtable_ofs(const uint8_t* b) {{
  return lvl_rd16(b, LVL_HDR_OFS_MSGTABLE);
}}

static inline uint16_t lvl_roomdir_entry_base(const uint8_t* b, uint8_t roomId) {{
  return (uint16_t)(lvl_roomdir_ofs(b) + (uint16_t)roomId * LVL_ROOM_DIRENTRY_SIZE);
}}

static inline uint16_t lvl_room_map_ofs(const uint8_t* b, uint8_t roomId) {{
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 0);
}}
static inline uint16_t lvl_room_spawns_ofs(const uint8_t* b, uint8_t roomId) {{
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 2);
}}
static inline uint16_t lvl_room_exits_ofs(const uint8_t* b, uint8_t roomId) {{
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 4);
}}
static inline uint16_t lvl_room_objects_ofs(const uint8_t* b, uint8_t roomId) {{
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 6);
}}

static inline uint8_t lvl_spawns_count(const uint8_t* b, uint16_t spawnsOfs) {{
  return lvl_rd8(b, spawnsOfs);
}}
static inline void lvl_spawn_xy(const uint8_t* b, uint16_t spawnsOfs, uint8_t idx, uint8_t* outX, uint8_t* outY) {{
  uint16_t base = (uint16_t)(spawnsOfs + 1 + (uint16_t)idx * 2);
  *outX = lvl_rd8(b, base + 0);
  *outY = lvl_rd8(b, base + 1);
}}

static inline uint8_t lvl_exits_count(const uint8_t* b, uint16_t exitsOfs) {{
  return lvl_rd8(b, exitsOfs);
}}
static inline void lvl_exit(const uint8_t* b, uint16_t exitsOfs, uint8_t idx, uint8_t* outType, uint8_t* outDestRoom, uint8_t* outDestSpawn) {{
  uint16_t base = (uint16_t)(exitsOfs + 1 + (uint16_t)idx * 3);
  *outType = lvl_rd8(b, base + 0);
  *outDestRoom = lvl_rd8(b, base + 1);
  *outDestSpawn = lvl_rd8(b, base + 2);
}}

static inline uint8_t lvl_objects_count(const uint8_t* b, uint16_t objsOfs) {{
  return lvl_rd8(b, objsOfs);
}}
static inline uint16_t lvl_object_base(const uint8_t* b, uint16_t objsOfs, uint8_t idx) {{
  return (uint16_t)(objsOfs + 1 + (uint16_t)idx * LVL_OBJ_RECORD_SIZE);
}}
"""


def sanitize_level_name(name: str) -> str:
    # Lowercase, ASCII-only, replace non-alnum with underscores.
    base = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip())
    base = base.strip("_").lower()
    return base if base else "level"


def make_c_identifier(name: str) -> str:
    ident = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not ident or ident[0].isdigit():
        ident = f"lvl_{ident}"
    return ident


# ----------------------------
# .sym writer
# ----------------------------


def write_sym(path: str, level: LevelDef, debug: dict) -> None:
    def verb_str(mask: int) -> str:
        parts = []
        for n, b in [
            ("LOOK", 1 << 0),
            ("TAKE", 1 << 1),
            ("USE", 1 << 2),
            ("TALK", 1 << 3),
            ("OPERATE", 1 << 4),
        ]:
            if mask & b:
                parts.append(n)
        return "|".join(parts) if parts else "NONE"

    with open(path, "w", encoding="utf-8") as f:
        f.write(f'LEVEL name="{level.name}" blob_size={debug["blob_size"]}\n')
        f.write(
            "HDR "
            f'room_dir={debug["offsets"]["room_dir"]} '
            f'cond_stream={debug["offsets"]["cond_stream"]} '
            f'act_stream={debug["offsets"]["act_stream"]} '
            f'msg_table={debug["offsets"]["msg_table"]}\n'
        )
        f.write("\n")

        # Rooms
        for r_idx, r in enumerate(debug["room_sym"]):
            f.write(f'ROOM[{r_idx}] id={r["rid"]} name="{r["name"]}"\n')
            f.write(f'  MAP ofs={r["ofs_map"]} size={r["map_size"]}\n')
            f.write(
                f'  SPAWNS ofs={r["ofs_spawns"]} count={len(r["spawn_keys"])} keys={",".join(r["spawn_keys"])}\n'
            )
            f.write(f'  EXITS ofs={r["ofs_exits"]} count={len(r["exits"])}\n')
            for e_idx, (edge, dest_room, dest_spawn) in enumerate(r["exits"]):
                f.write(f"    EXIT[{e_idx}] edge={edge} -> {dest_room}:{dest_spawn}\n")
            f.write(
                f'  OBJS ofs={r["ofs_objects"]} count={len(r["objects"])} recsize={OBJ_RECORD_SIZE}\n'
            )

            for o_idx, o in enumerate(r["objects"]):
                f.write(
                    f'    OBJ[{o_idx}] name={o["name"]} pos={o["x"]},{o["y"]} '
                    f'type={o["type_name"]}({o["type_id"]}) verbs={verb_str(o["verbs"])} '
                    f'p0={o["p0"]} p1={o["p1"]}\n'
                )
                f.write(f'      cond={o["cond_name"]}@{o["ofs_conds"]}\n')
                f.write(
                    "      "
                    f'look={o["look"]}@{o["ofs_look"]} '
                    f'take={o["take"]}@{o["ofs_take"]} '
                    f'use={o["use"]}@{o["ofs_use"]} '
                    f'talk={o["talk"]}@{o["ofs_talk"]} '
                    f'operate={o["operate"]}@{o["ofs_op"]} '
                    f'alt0={o["alt0"]}@{o["ofs_alt0"]} '
                    f'alt1={o["alt1"]}@{o["ofs_alt1"]}\n'
                )
            f.write("\n")

        # Scripts
        f.write("SCRIPTS\n")
        for name, ofs in sorted(debug["cond_offsets"].items(), key=lambda kv: kv[1]):
            f.write(f"  COND@{ofs} {name}\n")
        for name, ofs in sorted(debug["act_offsets"].items(), key=lambda kv: kv[1]):
            f.write(f"  ACT@{ofs} {name}\n")
        f.write("\n")

        # Messages
        f.write("MESSAGES\n")
        msg_names = debug.get("msg_names", [])
        msg_ofs = debug.get("msg_string_offsets", [])
        for i, (mn, mo) in enumerate(zip(msg_names, msg_ofs)):
            f.write(f"  MSG[{i}] {mn} ofs={mo}\n")


# ----------------------------
# Main compiler
# ----------------------------


def compile_level(level: LevelDef, errors: ErrorCollector) -> Tuple[Optional[bytes], str, dict]:
    # IDs in file order
    flag_ids = {n: i for i, n in enumerate(level.flags)}
    var_ids = {n: i for i, n in enumerate(level.vars)}
    item_ids = {n: i for i, n in enumerate(level.items)}
    msg_names = list(level.messages.keys())
    msg_ids = {n: i for i, n in enumerate(msg_names)}

    room_names = list(level.rooms.keys())
    room_ids = {rid: i for i, rid in enumerate(room_names)}

    # Spawn index per room (order in file)
    spawn_ids_by_room: Dict[str, Dict[str, int]] = {}
    for rid, room in level.rooms.items():
        spawn_ids_by_room[rid] = {sid: i for i, sid in enumerate(room.spawns.keys())}

    # Compile scripts to streams with offsets
    cond_stream = bytearray()
    cond_ofs: Dict[str, int] = {}
    for name, sdef in level.conds.items():
        cond_ofs[name] = len(cond_stream)
        cond_stream += compile_cond_script(sdef.lines, flag_ids, var_ids, item_ids, errors)

    act_stream = bytearray()
    act_ofs: Dict[str, int] = {}

    # Add built-in NOOP action (does nothing - just A_END)
    act_ofs["NOOP"] = len(act_stream)
    act_stream += bytes([A_END, 0, 0])

    for name, sdef in level.acts.items():
        act_ofs[name] = len(act_stream)
        act_stream += compile_act_script(
            sdef.lines,
            msg_ids,
            flag_ids,
            var_ids,
            item_ids,
            room_ids,
            spawn_ids_by_room,
            errors,
        )

    def act_offset(name: str) -> int:
        if not name:
            return 0
        if name not in act_ofs:
            errors.add_error(f"Unknown ACT script: {name}")
            return 0  # Return safe default
        return act_ofs[name]

    def cond_offset(name: str) -> int:
        if not name:
            return 0
        if name not in cond_ofs:
            errors.add_error(f"Unknown COND script: {name}")
            return 0  # Return safe default
        return cond_ofs[name]

    blob = bytearray()
    blob += b"\x00" * HEADER_SIZE

    # Room directory placeholder
    room_dir_ofs = len(blob)
    room_count = len(level.rooms)
    blob += b"\x00" * (room_count * ROOM_DIRENTRY_SIZE)

    room_dir_entries: List[Tuple[int, int, int, int]] = []
    room_sym: List[dict] = []

    for rid in room_names:
        room = level.rooms[rid]

        room_sym_entry = {
            "rid": rid,
            "name": room.name,
            "ofs_map": 0,
            "map_size": level.w * level.h,
            "ofs_spawns": 0,
            "spawn_keys": list(room.spawns.keys()),
            "ofs_exits": 0,
            "exits": list(room.exits),
            "ofs_objects": 0,
            "objects": [],
        }

        # Map
        if len(room.map_lines) != level.h:
            errors.add_error(
                f"{rid}: MAP has {len(room.map_lines)} lines, expected {level.h}"
            )
        map_bytes = bytearray()
        for y, row in enumerate(room.map_lines):
            if len(row) != level.w:
                errors.add_error(
                    f"{rid}: MAP line {y} length {len(row)}, expected {level.w}"
                )
                continue
            for ch in row:
                if ch not in level.tiles:
                    errors.add_error(
                        f"{rid}: MAP uses char '{ch}' with no TILES mapping"
                    )
                    map_bytes.append(0)  # Safe fallback value
                else:
                    map_bytes.append(level.tiles[ch] & 0xFF)

        ofs_map = len(blob)
        room_sym_entry["ofs_map"] = ofs_map
        blob += map_bytes

        # Spawns
        ofs_spawns = len(blob)
        room_sym_entry["ofs_spawns"] = ofs_spawns

        spawn_keys = list(room.spawns.keys())
        blob.append(len(spawn_keys) & 0xFF)
        for sid in spawn_keys:
            x, y = room.spawns[sid]
            blob += bytes([x & 0xFF, y & 0xFF])

        # Exits
        ofs_exits = len(blob)
        room_sym_entry["ofs_exits"] = ofs_exits

        blob.append(len(room.exits) & 0xFF)
        for edge, dest_room, dest_spawn in room.exits:
            if edge not in EXIT_TYPES:
                errors.add_error(f"{rid}: bad exit edge {edge}")
                continue
            if dest_room not in room_ids:
                errors.add_error(f"{rid}: exit dest room unknown {dest_room}")
                continue
            if dest_spawn not in spawn_ids_by_room[dest_room]:
                errors.add_error(
                    f"{rid}: exit dest spawn unknown {dest_room}:{dest_spawn}"
                )
                continue
            blob += bytes(
                [
                    EXIT_TYPES[edge] & 0xFF,
                    room_ids[dest_room] & 0xFF,
                    spawn_ids_by_room[dest_room][dest_spawn] & 0xFF,
                ]
            )

        # Objects
        ofs_objects = len(blob)
        room_sym_entry["ofs_objects"] = ofs_objects

        blob.append(len(room.objects) & 0xFF)

        for obj in room.objects:
            if obj.type_name not in OBJ_TYPES:
                errors.add_error(f"{rid}: unknown object type {obj.type_name}")
                continue
            otype = OBJ_TYPES[obj.type_name]

            # Default params
            try:
                p0 = int(obj.props.get("p0", "0"), 0) & 0xFF
                p1 = int(obj.props.get("p1", "0"), 0) & 0xFF
            except ValueError:
                errors.add_error(f"{rid}: invalid p0/p1 values for object {obj.name}")
                p0, p1 = 0, 0

            # PICKUP item= -> p0=itemId
            if obj.type_name == "PICKUP" and "item" in obj.props:
                p0 = _resolve_id(obj.props["item"], item_ids, "ITEM", errors) & 0xFF

            # LOCKER_KEYPAD code=729 -> p0=7, p1=29
            if obj.type_name == "LOCKER_KEYPAD" and "code" in obj.props:
                try:
                    code = int(obj.props["code"], 10)
                    if not (0 <= code <= 999):
                        errors.add_error(f"{rid}: keypad code out of range 0..999")
                    else:
                        p0 = (code // 100) & 0xFF
                        p1 = (code % 100) & 0xFF
                except ValueError:
                    errors.add_error(f"{rid}: invalid keypad code: {obj.props['code']}")

            # BREAKER_PANEL var=VARNAME -> p0=varId; expect=0b101 -> p1 expected bits (0..7)
            if obj.type_name == "BREAKER_PANEL":
                if "var" in obj.props:
                    p0 = _resolve_id(obj.props["var"], var_ids, "VAR", errors) & 0xFF
                if "expect" in obj.props:
                    try:
                        exp = int(obj.props["expect"], 0)
                        if not (0 <= exp <= 7):
                            errors.add_error(f"{rid}: breaker expect must be 0..7")
                        else:
                            p1 = exp & 0xFF
                    except ValueError:
                        errors.add_error(f"{rid}: invalid breaker expect value: {obj.props['expect']}")

            ofs_conds = cond_offset(obj.cond_name)

            ofs_look = act_offset(obj.look)
            ofs_take = act_offset(obj.take)
            ofs_use = act_offset(obj.use)
            ofs_talk = act_offset(obj.talk)
            ofs_op = act_offset(obj.operate)

            ofs_alt0 = act_offset(obj.alt0)
            ofs_alt1 = act_offset(obj.alt1)

            # Emit object record
            blob += bytes(
                [obj.x & 0xFF, obj.y & 0xFF, otype & 0xFF, obj.verbs & 0xFF, p0, p1]
            )
            blob += _u16(ofs_conds)
            blob += _u16(ofs_look)
            blob += _u16(ofs_take)
            blob += _u16(ofs_use)
            blob += _u16(ofs_talk)
            blob += _u16(ofs_op)
            blob += _u16(ofs_alt0)
            blob += _u16(ofs_alt1)

            room_sym_entry["objects"].append(
                {
                    "name": obj.name,
                    "x": obj.x,
                    "y": obj.y,
                    "type_name": obj.type_name,
                    "type_id": otype,
                    "verbs": obj.verbs,
                    "p0": p0,
                    "p1": p1,
                    "cond_name": obj.cond_name,
                    "ofs_conds": ofs_conds,
                    "look": obj.look,
                    "ofs_look": ofs_look,
                    "take": obj.take,
                    "ofs_take": ofs_take,
                    "use": obj.use,
                    "ofs_use": ofs_use,
                    "talk": obj.talk,
                    "ofs_talk": ofs_talk,
                    "operate": obj.operate,
                    "ofs_op": ofs_op,
                    "alt0": obj.alt0,
                    "ofs_alt0": ofs_alt0,
                    "alt1": obj.alt1,
                    "ofs_alt1": ofs_alt1,
                }
            )

        room_dir_entries.append((ofs_map, ofs_spawns, ofs_exits, ofs_objects))
        room_sym.append(room_sym_entry)

    # Append streams
    ofs_cond_stream = len(blob)
    blob += cond_stream

    ofs_act_stream = len(blob)
    blob += act_stream

    # Messages: table + offsets + strings
    ofs_msg_table = len(blob)
    blob.append(len(msg_names) & 0xFF)
    msg_ofs_pos = len(blob)
    blob += b"\x00" * (2 * len(msg_names))

    msg_string_offsets: List[int] = []
    for mid in msg_names:
        msg_string_offsets.append(len(blob))
        blob += _ascii_bytes(level.messages[mid])

    # Patch message offsets
    for idx, sofs in enumerate(msg_string_offsets):
        struct.pack_into("<H", blob, msg_ofs_pos + idx * 2, sofs)

    # Patch room directory
    for rindex, (ofs_map, ofs_spawns, ofs_exits, ofs_objects) in enumerate(
        room_dir_entries
    ):
        base = room_dir_ofs + rindex * ROOM_DIRENTRY_SIZE
        struct.pack_into(
            "<HHHH", blob, base, ofs_map, ofs_spawns, ofs_exits, ofs_objects
        )

    # Patch header
    start_room_idx = _resolve_id(level.start_room, room_ids, "ROOM", errors)
    if (
        level.start_room not in spawn_ids_by_room
        or level.start_spawn not in spawn_ids_by_room[level.start_room]
    ):
        errors.add_error(f"Start spawn unknown: {level.start_room}:{level.start_spawn}")
        start_spawn_idx = 0  # Safe fallback
    else:
        start_spawn_idx = spawn_ids_by_room[level.start_room][level.start_spawn]

    # Don't return None here - continue so all errors can be collected and reported
    # If there are errors, we'll create a minimal output but let error reporting handle it

    header = struct.pack(
        "<4sBBBBBBBBBBHHHH",
        LEVEL_MAGIC,
        LEVEL_VERSION,
        room_count & 0xFF,
        level.w & 0xFF,
        level.h & 0xFF,
        len(level.flags) & 0xFF,
        len(level.vars) & 0xFF,
        len(level.items) & 0xFF,
        len(msg_names) & 0xFF,
        start_room_idx & 0xFF,
        start_spawn_idx & 0xFF,
        room_dir_ofs & 0xFFFF,
        ofs_cond_stream & 0xFFFF,
        ofs_act_stream & 0xFFFF,
        ofs_msg_table & 0xFFFF,
    )
    if len(header) != HEADER_SIZE:
        errors.add_error(
            f"Internal error: Header pack size mismatch: {len(header)} != {HEADER_SIZE}"
        )
        # Create minimal header anyway and continue error collection
        header = b'\x00' * HEADER_SIZE
    blob[0:HEADER_SIZE] = header

    # Generate IDs header
    header_c: List[str] = []
    header_c.append("// Auto-generated by levelc.py\n#pragma once\n\n")
    header_c.append(_pack_enum_header("FlagId", level.flags))
    header_c.append(_pack_enum_header("VarId", level.vars))
    header_c.append(_pack_enum_header("ItemId", level.items))
    header_c.append(_pack_enum_header("MsgId", msg_names))
    header_c.append("typedef enum ObjType : unsigned char {\n")
    for k, v in OBJ_TYPES.items():
        header_c.append(f"  OBJ_{k} = {v},\n")
    header_c.append("} ObjType;\n\n")
    header_c_str = "".join(header_c)

    debug = {
        "name": level.name,
        "w": level.w,
        "h": level.h,
        "rooms": room_names,
        "ids": {
            "flags": flag_ids,
            "vars": var_ids,
            "items": item_ids,
            "msgs": msg_ids,
            "rooms": room_ids,
        },
        "offsets": {
            "room_dir": room_dir_ofs,
            "cond_stream": ofs_cond_stream,
            "act_stream": ofs_act_stream,
            "msg_table": ofs_msg_table,
        },
        "cond_offsets": cond_ofs,
        "act_offsets": act_ofs,
        "room_sym": room_sym,
        "msg_names": msg_names,
        "msg_string_offsets": msg_string_offsets,
        "blob_size": len(blob),
    }

    return bytes(blob), header_c_str, debug


# ----------------------------
# CLI
# ----------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Input LVLTEXT file (.lvl)")
    ap.add_argument("-o", "--output", default="", help="Output binary (.bin)")
    ap.add_argument(
        "--out-assets",
        default="assets/levels",
        help="Output directory for .bin blobs",
    )
    ap.add_argument(
        "--out-src",
        default="src/levels",
        help="Output directory for generated .c blobs",
    )
    ap.add_argument(
        "--out-include",
        default="include/levels",
        help="Output directory for generated headers (.h)",
    )
    ap.add_argument(
        "--out-debug",
        default="build/levels",
        help="Output directory for .sym and .json",
    )

    ap.add_argument("--ids", default="", help="Output generated IDs header (.h)")
    ap.add_argument("--json", default="", help="Output debug JSON (.json)")
    ap.add_argument("--sym", default="", help="Output symbol map (.sym)")

    ap.add_argument("--blob-c", default="", help="Output C file embedding blob (.c)")
    ap.add_argument("--blob-h", default="", help="Output header for blob (.h)")
    ap.add_argument(
        "--blob-name",
        default="",
        help="C array name for blob (default: <input_basename>_blob)",
    )

    ap.add_argument(
        "--format-h", default="", help="Output level_format.h (accessors/constants)"
    )

    args = ap.parse_args()

    # Create error collector
    errors = ErrorCollector()

    # Parse input file
    level = parse_lvltext(args.input, errors)

    # Don't exit after parsing errors - continue to compilation to find more errors
    if level is None:
        # If parsing completely failed, we can't continue
        errors.report_and_exit("Parsing failed completely: ")

    # Compile the level (may add more errors)
    blob, ids_h, debug = compile_level(level, errors)

    # Report ALL errors (both parsing and compilation) together
    errors.report_and_exit("Found errors: ")

    base_name = sanitize_level_name(level.name)
    c_ident = make_c_identifier(base_name)

    os.makedirs(args.out_assets, exist_ok=True)
    os.makedirs(args.out_src, exist_ok=True)
    os.makedirs(args.out_include, exist_ok=True)
    os.makedirs(args.out_debug, exist_ok=True)

    if not args.output:
        args.output = os.path.join(args.out_assets, f"{base_name}.bin")
    if not args.ids:
        args.ids = os.path.join(args.out_include, f"{base_name}.h")
    if not args.sym:
        args.sym = os.path.join(args.out_debug, f"{base_name}.sym")
    if not args.json:
        args.json = os.path.join(args.out_debug, f"{base_name}.json")
    if not args.blob_c:
        args.blob_c = os.path.join(args.out_src, f"{base_name}.c")
    if not args.blob_h:
        args.blob_h = os.path.join(args.out_include, f"{base_name}-blob.h")
    if not args.format_h:
        args.format_h = os.path.join("include", "level_format.h")
    if not args.blob_name:
        args.blob_name = f"{c_ident}_blob"

    # .bin
    try:
        with open(args.output, "wb") as f:
            f.write(blob)
        print(f"Wrote {args.output} ({len(blob)} bytes)")
    except Exception as e:
        print(f"Error writing binary file {args.output}: {e}", file=sys.stderr)
        sys.exit(1)

    # ids header
    try:
        with open(args.ids, "w", encoding="utf-8") as f:
            f.write(ids_h)
        print(f"Wrote {args.ids}")
    except Exception as e:
        print(f"Error writing IDs header {args.ids}: {e}", file=sys.stderr)
        sys.exit(1)

    # debug JSON
    try:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(debug, f, indent=2)
        print(f"Wrote {args.json}")
    except Exception as e:
        print(f"Error writing JSON file {args.json}: {e}", file=sys.stderr)
        sys.exit(1)

    # .sym
    try:
        write_sym(args.sym, level, debug)
        print(f"Wrote {args.sym}")
    except Exception as e:
        print(f"Error writing symbol file {args.sym}: {e}", file=sys.stderr)
        sys.exit(1)

    # blob C/H
    array_name = args.blob_name
    try:
        with open(args.blob_h, "w", encoding="utf-8") as f:
            f.write(make_blob_h(array_name))
        print(f"Wrote {args.blob_h}")
    except Exception as e:
        print(f"Error writing blob header {args.blob_h}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        rel_bin = os.path.relpath(args.output, os.path.dirname(args.blob_c) or ".")
        rel_bin = rel_bin.replace("\\", "/")
        csrc = (
            "// Auto-generated by levelc.py\n"
            "#include <stdint.h>\n"
            f'#include "levels/{os.path.basename(args.blob_h)}"\n'
            "\n"
            + blob_to_c_embed(rel_bin, array_name)
        )
        with open(args.blob_c, "w", encoding="utf-8") as f:
            f.write(csrc)
        print(f"Wrote {args.blob_c}")
    except Exception as e:
        print(f"Error writing blob C file {args.blob_c}: {e}", file=sys.stderr)
        sys.exit(1)

    # format/accessor header
    try:
        with open(args.format_h, "w", encoding="utf-8") as f:
            f.write("// Provided by levelc.py\n")
            f.write(make_format_h())
        print(f"Wrote {args.format_h}")
    except Exception as e:
        print(f"Error writing format header {args.format_h}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
