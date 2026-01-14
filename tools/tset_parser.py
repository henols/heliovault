#!/usr/bin/env python3
"""
tset_parser.py - Shared .tset parser for tilesetc.py and levelc.py.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


class TilesetParseError(Exception):
    def __init__(self, path: str, line: int, col: int, message: str):
        super().__init__(message)
        self.path = path
        self.line = line
        self.col = col
        self.message = message


FIXED_FLAGBITS = {
    "SOLID": 0,
    "DECOR": 1,
    "STANDABLE": 2,
    "LADDER": 3,
    "DOOR": 4,
    "INTERACTABLE": 5,
    "FLOOR": 6,
    "HAZARD": 7,
}

COLOR_NAMES = {
    "black": 0,
    "white": 1,
    "red": 2,
    "cyan": 3,
    "purple": 4,
    "green": 5,
    "blue": 6,
    "yellow": 7,
    "orange": 8,
    "brown": 9,
    "lightred": 10,
    "darkgray": 11,
    "darkgrey": 11,
    "gray": 12,
    "grey": 12,
    "lightgreen": 13,
    "lightblue": 14,
    "lightgray": 15,
    "lightgrey": 15,
}

TOKEN_KV = re.compile(r'(\w+)=(".*?"|\S+)')


@dataclass
class TileDef:
    tid: int
    name: str
    chars: List[int]          # 4 values TL,TR,BL,BR
    color_mode: int           # 0 single, 1 per-quadrant
    colors: List[int]         # 4 values (if single: [c,0,0,0])
    flags: int


@dataclass
class ObjectDef:
    name: str
    w: int
    h: int
    tiles: List[str]          # tile names (upper)
    char: str | None = None


@dataclass
class TsetParseResult:
    name: str
    tile_w: int
    tile_h: int
    declared_count: int
    bg_color: int
    mc1_color: int
    mc2_color: int
    charset_path: str
    flagbits: Dict[str, int] = field(default_factory=dict)
    tiles: Dict[int, TileDef] = field(default_factory=dict)
    tiles_by_name: Dict[str, int] = field(default_factory=dict)
    objects: Dict[str, ObjectDef] = field(default_factory=dict)  # name->def
    charmap_tiles: Dict[str, int] = field(default_factory=dict)
    object_stamps: Dict[str, dict] = field(default_factory=dict)  # char->def


def strip_comment(line: str) -> str:
    if ";" in line:
        return line.split(";", 1)[0].rstrip()
    return line.rstrip()


def unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def parse_kv(line: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in TOKEN_KV.finditer(line):
        out[m.group(1)] = unquote(m.group(2))
    return out


def parse_kv_fragment(line: str) -> Dict[str, str]:
    return parse_kv(line)


def parse_num(s: str) -> int:
    s = s.strip()
    if s.startswith("$"):
        return int(s[1:], 16)
    return int(s, 0)


def parse_color(s: str) -> int:
    s = s.strip()
    key = s.lower().replace("_", "").replace("-", "").replace(" ", "")
    if key in COLOR_NAMES:
        return COLOR_NAMES[key]
    return parse_num(s)


def parse_char_or_num(s: str) -> int:
    s = s.strip()
    if len(s) == 1 and s.isalpha():
        return ord(s.upper()) - ord("A") + 1
    return parse_num(s)


def parse_int_list(s: str, count: int, parse_fn=parse_num) -> List[int]:
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != count:
        raise ValueError(f"Expected {count} values, got {len(parts)}: {s}")
    return [parse_fn(p) for p in parts]


def _col_for_token(line: str, token: str) -> int:
    if not token:
        return 1
    idx = line.find(token)
    return idx + 1 if idx >= 0 else 1


def _col_for_kv_value(line: str, key: str) -> int:
    if not key:
        return 1
    m = re.search(rf'(?<!\\w){re.escape(key)}\\s*=\\s*(".*?"|\\S+)', line)
    if not m:
        return _col_for_token(line, key)
    return m.start(1) + 1


def parse_tset(path: str, error_cb: Optional[Callable[[str, int, int], None]] = None) -> TsetParseResult:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.readlines()

    lines: List[Tuple[int, str, str]] = []
    for idx, ln in enumerate(raw, 1):
        raw_line = strip_comment(ln).rstrip("\n")
        s = raw_line.strip()
        if s:
            lines.append((idx, raw_line, s))

    def err(message: str, line_no: int = 1, col: int = 1) -> None:
        if error_cb:
            error_cb(message, line_no, col)
            return
        raise TilesetParseError(path, line_no, col, message)

    ts: Optional[TsetParseResult] = None
    mode: Optional[str] = None
    next_id = 0
    charmap_entries: List[Tuple[int, str, str]] = []
    charmap_keys: Dict[str, int] = {}
    object_entries: List[Tuple[int, str, str]] = []

    i = 0
    while i < len(lines):
        line_no, raw_line, line = lines[i]
        i += 1

        if line == "END":
            mode = None
            continue

        parts = line.split()
        head = parts[0]

        if head == "TSET":
            kv = parse_kv(line)
            name = kv.get("name", os.path.splitext(os.path.basename(path))[0])
            if "tileSize" not in kv:
                err("TSET requires tileSize=2x2", line_no, _col_for_token(raw_line, "TSET"))
            size = kv["tileSize"].lower()
            if "x" not in size:
                err("tileSize must look like 2x2", line_no, _col_for_token(raw_line, "tileSize"))
            tw, th = size.split("x", 1)
            if "count" in kv:
                try:
                    declared_count = parse_num(kv["count"])
                except ValueError:
                    err(f"Invalid count value: {kv['count']}", line_no, _col_for_kv_value(raw_line, "count"))
                if declared_count is None:
                    declared_count = 0
            else:
                declared_count = 0
            try:
                tile_w = int(tw)
                tile_h = int(th)
            except ValueError:
                err(f"tileSize must contain integers: {size}", line_no, _col_for_token(raw_line, "tileSize"))
            ts = TsetParseResult(
                name=name,
                tile_w=tile_w,
                tile_h=tile_h,
                declared_count=declared_count,
                bg_color=0,
                mc1_color=0,
                mc2_color=0,
                charset_path="",
                flagbits=dict(FIXED_FLAGBITS),
            )
            if ts.tile_w != 2 or ts.tile_h != 2:
                err("This tool currently expects tileSize=2x2", line_no, _col_for_token(raw_line, "tileSize"))
            if "bgColor" not in kv:
                err("TSET requires bgColor=", line_no, _col_for_token(raw_line, "TSET"))
            if "mc1Color" not in kv:
                err("TSET requires mc1Color=", line_no, _col_for_token(raw_line, "TSET"))
            if "mc2Color" not in kv:
                err("TSET requires mc2Color=", line_no, _col_for_token(raw_line, "TSET"))
            try:
                ts.bg_color = parse_color(kv["bgColor"])
            except ValueError:
                err(f"Invalid bgColor value: {kv['bgColor']}", line_no, _col_for_kv_value(raw_line, "bgColor"))
            try:
                ts.mc1_color = parse_color(kv["mc1Color"])
            except ValueError:
                err(f"Invalid mc1Color value: {kv['mc1Color']}", line_no, _col_for_kv_value(raw_line, "mc1Color"))
            try:
                ts.mc2_color = parse_color(kv["mc2Color"])
            except ValueError:
                err(f"Invalid mc2Color value: {kv['mc2Color']}", line_no, _col_for_kv_value(raw_line, "mc2Color"))
            if not (0 <= ts.bg_color <= 15):
                err("bgColor must be 0..15", line_no, _col_for_kv_value(raw_line, "bgColor"))
            if not (0 <= ts.mc1_color <= 15):
                err("mc1Color must be 0..15", line_no, _col_for_kv_value(raw_line, "mc1Color"))
            if not (0 <= ts.mc2_color <= 15):
                err("mc2Color must be 0..15", line_no, _col_for_kv_value(raw_line, "mc2Color"))
            if "charset" in kv:
                ts.charset_path = kv["charset"]
                charset_path = ts.charset_path
                if not os.path.isabs(charset_path):
                    charset_path = os.path.join(os.path.dirname(path), charset_path)
                    if not os.path.isfile(charset_path):
                        charset_path = os.path.join(os.path.dirname(path), "..", ts.charset_path)
                if not os.path.isfile(charset_path):
                    err(f"charset file not found: {ts.charset_path}", line_no, _col_for_kv_value(raw_line, "charset"))
            continue

        if ts is None:
            err("File must start with TSET ...", line_no)

        if head == "FLAGBITS":
            err("FLAGBITS section is not allowed in .tset files", line_no, _col_for_token(raw_line, "FLAGBITS"))
        if head == "TILES":
            mode = head
            continue
        if head == "CHARMAP":
            mode = head
            continue
        if head == "OBJECTS":
            mode = head
            continue

        if mode == "TILES":
            name = parts[0]
            rest = line[len(name):].strip()
            kv = parse_kv_fragment(rest)
            if "id" in kv:
                try:
                    tid = parse_num(kv["id"])
                except ValueError:
                    err(f"Invalid TILE id: {kv['id']}", line_no, _col_for_kv_value(raw_line, "id"))
                if tid >= next_id:
                    next_id = tid + 1
            else:
                tid = next_id
                next_id += 1
            kv["id"] = str(tid)
            if not name:
                name = f"TILE_{tid}"
        elif head == "TILE":
            kv = parse_kv(line)
            if "id" not in kv:
                err(f"TILE missing id=: {line}", line_no, _col_for_token(raw_line, "TILE"))
            try:
                tid = parse_num(kv["id"])
            except ValueError:
                err(f"Invalid TILE id: {kv['id']}", line_no, _col_for_kv_value(raw_line, "id"))
            if not (0 <= tid <= 255):
                err("TILE id must be 0..255", line_no, _col_for_kv_value(raw_line, "id"))
            name = kv.get("name", f"TILE_{tid}")
        else:
            if mode == "CHARMAP":
                if len(parts) < 2:
                    err(f"CHARMAP line missing tile name: {line}", line_no, _col_for_token(raw_line, "CHARMAP"))
                ch = parts[0]
                if len(ch) != 1:
                    err(f"CHARMAP key must be a single char: {ch}", line_no, _col_for_token(raw_line, ch))
                tile_name = parts[1].strip().upper()
                if tile_name.startswith("TILE_"):
                    tile_name = tile_name[5:]
                if ch in charmap_keys:
                    err(f"Duplicate CHARMAP key: {ch}", line_no, _col_for_token(raw_line, ch))
                charmap_keys[ch] = line_no
                charmap_entries.append((line_no, ch, tile_name))
                continue
            if mode == "OBJECTS":
                name = parts[0]
                object_entries.append((line_no, line, name))
                continue
            err(f"Unexpected line: {line}", line_no, 1)

        if not (0 <= tid <= 255):
            err("TILE id must be 0..255", line_no, _col_for_kv_value(raw_line, "id"))

        if not name:
            name = f"TILE_{tid}"

        if "chars" not in kv:
            err(f"TILE missing chars=: {line}", line_no, _col_for_token(raw_line, "chars"))
        try:
            chars = parse_int_list(kv["chars"], 4, parse_fn=parse_char_or_num)
        except ValueError as e:
            err(str(e), line_no, _col_for_kv_value(raw_line, "chars"))
        for c in chars:
            if not (0 <= c <= 255):
                err(f"Char code out of range 0..255 in: {line}", line_no, _col_for_kv_value(raw_line, "chars"))

        if "colors" in kv:
            color_mode = 1
            try:
                colors = parse_int_list(kv["colors"], 4, parse_fn=parse_color)
            except ValueError as e:
                err(str(e), line_no, _col_for_kv_value(raw_line, "colors"))
        elif "color" in kv:
            color_mode = 0
            try:
                c = parse_color(kv["color"])
            except ValueError:
                err(f"Invalid color value: {kv['color']}", line_no, _col_for_kv_value(raw_line, "color"))
            colors = [c, 0, 0, 0]
        else:
            err(f"TILE must have color= or colors=: {line}", line_no, _col_for_token(raw_line, "TILE"))

        for c in colors:
            if not (0 <= c <= 15):
                err(f"Color out of range 0..15 in: {line}", line_no, _col_for_kv_value(raw_line, "color"))

        flags_mask = 0
        flags_str = kv.get("flags", "")
        if flags_str:
            for fn in flags_str.split("|"):
                fn = fn.strip().upper()
                if not fn:
                    continue
                if fn not in ts.flagbits:
                    err(f"Unknown flag '{fn}' in: {line}", line_no, _col_for_token(raw_line, fn))
                bit = ts.flagbits[fn]
                if not (0 <= bit <= 15):
                    err(f"Flag bit out of range 0..15 for {fn}", line_no, _col_for_token(raw_line, fn))
                flags_mask |= (1 << bit)

        tile = TileDef(
            tid=tid,
            name=name,
            chars=chars,
            color_mode=color_mode,
            colors=colors,
            flags=flags_mask,
        )
        name_key = name.strip().upper()
        if name_key.startswith("TILE_"):
            name_key = name_key[5:]
        if name_key in ts.tiles_by_name:
            err(f"Duplicate TILE name: {name}", line_no, _col_for_token(raw_line, name))
        ts.tiles_by_name[name_key] = tid
        if tid in ts.tiles:
            err(f"Duplicate TILE id={tid}", line_no, _col_for_token(raw_line, "id"))
        ts.tiles[tid] = tile
        continue

    if ts is None:
        err("No TSET header found", 1)

    if len(ts.tiles) == 0:
        err("No TILE definitions found", 1)
    if ts.declared_count == 0:
        ts.declared_count = len(ts.tiles)
    if len(ts.tiles) > ts.declared_count:
        err(f"Defined {len(ts.tiles)} tiles but TSET count={ts.declared_count}", 1)
    if len(ts.tiles) > 255:
        err("Too many tiles: max 255 (count stored as u8)", 1)

    if object_entries:
        for line_no, raw_line, name in object_entries:
            rest = raw_line[len(name):].strip()
            kv = parse_kv_fragment(rest)
            if "char" in kv:
                err(
                    f"OBJECTS entry must not include char=: {raw_line}",
                    line_no,
                    _col_for_kv_value(raw_line, "char"),
                )
                continue
            if "size" not in kv or "tiles" not in kv:
                err(
                    f"OBJECTS entry requires size= tiles=: {raw_line}",
                    line_no,
                    _col_for_token(raw_line, "OBJECTS"),
                )
                continue
            size = kv["size"].lower()
            if "x" not in size:
                err(f"OBJECTS size must look like WxH: {size}", line_no, _col_for_kv_value(raw_line, "size"))
                continue
            try:
                w_str, h_str = size.split("x", 1)
                ow = int(w_str)
                oh = int(h_str)
            except ValueError:
                err(f"OBJECTS size must be integers: {size}", line_no, _col_for_kv_value(raw_line, "size"))
                continue
            tiles_list = [t.strip().upper() for t in kv["tiles"].split(",") if t.strip()]
            if len(tiles_list) != ow * oh:
                err(
                    f"OBJECTS tiles count {len(tiles_list)} does not match size {ow}x{oh}",
                    line_no,
                    _col_for_kv_value(raw_line, "tiles"),
                )
                continue
            for tname in tiles_list:
                if tname not in ts.tiles_by_name:
                    err(f"OBJECTS unknown tile name: {tname}", line_no, _col_for_kv_value(raw_line, "tiles"))
                    continue
            ts.objects[name.upper()] = ObjectDef(
                name=name,
                w=ow,
                h=oh,
                tiles=tiles_list,
            )

    for line_no, ch, tile_name in charmap_entries:
        if tile_name in ts.tiles_by_name:
            ts.charmap_tiles[ch] = ts.tiles_by_name[tile_name]
            continue
        obj = ts.objects.get(tile_name)
        if obj is None:
            err(f"CHARMAP unknown tile/object name: {tile_name}", line_no, 1)
            continue
        if obj.char and obj.char != ch:
            err(f"OBJECT '{tile_name}' bound to multiple chars", line_no, 1)
            continue
        obj.char = ch

    for obj in ts.objects.values():
        if obj.char:
            tile_ids = [ts.tiles_by_name[n] for n in obj.tiles]
            ts.object_stamps[obj.char] = {
                "name": obj.name,
                "w": obj.w,
                "h": obj.h,
                "tiles": tile_ids,
                "char": obj.char,
            }

    return ts
