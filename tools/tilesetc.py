#!/usr/bin/env python3
"""
tilesetc.py - Compile a metatile tileset definition (.tset) into a binary blob.

Outputs:
  - .o/.bin   TSET blob: header + metatile records (+ optional names)
  - *_ids.h   Flag masks + tile id constants
  - .sym      Human-readable dump (offsets, decoded tiles)
  - .json     Optional debug

Usage:
  python tools/tilesetc.py tileset.tset -o tileset.bin \
      --ids tileset_ids.h --sym tileset.sym --json tileset.json

Format:
  TSET name="..." tileSize=2x2 count=16   ; count is optional
  TILES
    FLOOR_A chars=0x51,0x52,0x53,0x54 color=6 flags=FLOOR|SOLID
    WALL    chars=... colors=6,6,7,7 flags=...
  END
"""

from __future__ import annotations
import argparse
import json
import os
import re
import struct
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from tset_parser import parse_tset as parse_tset_shared, TilesetParseError
from gen_paths import GEN_ROOT, ANALYSIS_ROOT

MAGIC = b"TSET"
VERSION = 1

# id(1) + chars(4) + colorMode(1) + colors(4) + flags(2) = 12 bytes
RECORD_SIZE = 12

TOKEN_KV = re.compile(r'(\w+)=(".*?"|\S+)')

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

def parse_tset(path: str):
    return parse_tset_shared(path)


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
    "gray": 12,
    "lightgreen": 13,
    "lightblue": 14,
    "lightgray": 15,
}


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


@dataclass
class Tile:
    tid: int
    name: str
    chars: List[int]          # 4 values TL,TR,BL,BR
    color_mode: int           # 0 single, 1 per-quadrant
    colors: List[int]         # 4 values (if single: [c,0,0,0])
    flags: int


@dataclass
class TileSet:
    name: str
    tile_w: int
    tile_h: int
    declared_count: int
    bg_color: int
    mc1_color: int
    mc2_color: int
    charset_path: str
    flagbits: Dict[str, int] = field(default_factory=dict)
    tiles: Dict[int, Tile] = field(default_factory=dict)  # tid->Tile
    objects: List[dict] = field(default_factory=list)


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


def _parse_tset_legacy(path: str) -> TileSet:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.readlines()

    lines: List[Tuple[int, str, str]] = []
    for idx, ln in enumerate(raw, 1):
        raw_line = strip_comment(ln).rstrip("\n")
        s = raw_line.strip()
        if s:
            lines.append((idx, raw_line, s))

    def err(message: str, line_no: int = 1, col: int = 1) -> None:
        raise TilesetParseError(path, line_no, col, message)

    ts: Optional[TileSet] = None
    mode: Optional[str] = None
    next_id = 0
    tile_names: Dict[str, int] = {}
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
            ts = TileSet(
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

        # color vs colors
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

        # flags
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

        tile = Tile(
            tid=tid,
            name=name,
            chars=chars,
            color_mode=color_mode,
            colors=colors,
            flags=flags_mask
        )
        name_key = name.strip().upper()
        if name_key.startswith("TILE_"):
            name_key = name_key[5:]
        if name_key in tile_names:
            err(f"Duplicate TILE name: {name}", line_no, _col_for_token(raw_line, name))
        tile_names[name_key] = tid
        if tid in ts.tiles:
            err(f"Duplicate TILE id={tid}", line_no, _col_for_token(raw_line, "id"))
        ts.tiles[tid] = tile
        continue

    if ts is None:
        err("No TSET header found", 1)


    # Validate tile count (declared count is a sanity check)
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
                if tname not in tile_names:
                    err(f"OBJECTS unknown tile name: {tname}", line_no, _col_for_kv_value(raw_line, "tiles"))
                    continue
            ts.objects.append(
                {
                    "name": name,
                    "w": ow,
                    "h": oh,
                    "tiles": tiles_list,
                }
            )

    if charmap_entries:
        obj_by_name = {o["name"].upper(): o for o in ts.objects}
        for line_no, ch, tile_name in charmap_entries:
            if tile_name in tile_names:
                continue
            obj = obj_by_name.get(tile_name)
            if obj is None:
                err(f"CHARMAP unknown tile/object name: {tile_name}", line_no, 1)
                continue
            if "char" in obj and obj["char"] != ch:
                err(f"OBJECT '{tile_name}' bound to multiple chars", line_no, 1)
                continue
            obj["char"] = ch

    return ts


def compile_tset(ts: TileSet) -> tuple[bytes, str, dict, str, str, str]:
    # Sort tiles by ID for stable output
    tiles_sorted = [ts.tiles[k] for k in sorted(ts.tiles.keys())]
    tile_count = len(tiles_sorted)

    # Header layout:
    # magic(4) version(1) tileW(1) tileH(1) tileCount(1) recSize(1) ofsRecords(u16) ofsNames(u16) reserved(u32)
    header_fmt = "<4sBBBBBHHI"
    header_size = struct.calcsize(header_fmt)
    ofs_records = header_size
    ofs_names = 0  # not used in v1 (names are for tooling headers/sym only)
    reserved = (ts.bg_color & 0xFF) | ((ts.mc1_color & 0xFF) << 8) | ((ts.mc2_color & 0xFF) << 16)

    blob = bytearray()
    blob += struct.pack(
        header_fmt,
        MAGIC,
        VERSION & 0xFF,
        ts.tile_w & 0xFF,
        ts.tile_h & 0xFF,
        tile_count & 0xFF,
        RECORD_SIZE & 0xFF,
        ofs_records & 0xFFFF,
        ofs_names & 0xFFFF,
        reserved & 0xFFFFFFFF,
    )

    # Records
    # Correct format: id (B) + chars (4B) + color_mode (B) + colors (4B) + flags (H)
    rec_fmt = "<B4BB4BH"
    for t in tiles_sorted:
        rec = struct.pack(
            rec_fmt,
            t.tid & 0xFF,
            t.chars[0] & 0xFF, t.chars[1] & 0xFF, t.chars[2] & 0xFF, t.chars[3] & 0xFF,
            t.color_mode & 0xFF,
            t.colors[0] & 0xFF, t.colors[1] & 0xFF, t.colors[2] & 0xFF, t.colors[3] & 0xFF,
            t.flags & 0xFFFF,
        )
        assert len(rec) == RECORD_SIZE, f"Record size mismatch: {len(rec)} != {RECORD_SIZE}"
        blob += rec

    # IDs header: flag masks + tile IDs
    h: List[str] = []
    h.append("// Auto-generated by tilesetc.py\n#pragma once\n#include <stdint.h>\n\n")
    h.append("/* Tile IDs */\n")
    for t in tiles_sorted:
        ident = re.sub(r'[^A-Za-z0-9_]', "_", t.name).upper()
        h.append(f"#define TILE_{ident} {t.tid}\n")
    h.append("\n")
    ids_h = "".join(h)

    # Debug
    def objects_for_debug(objects):
        if isinstance(objects, dict):
            items = list(objects.values())
        elif isinstance(objects, list):
            items = objects
        else:
            return []
        out = []
        for obj in items:
            out.append(asdict(obj) if hasattr(obj, "__dataclass_fields__") else obj)
        return out

    debug = {
        "name": ts.name,
        "tile_w": ts.tile_w,
        "tile_h": ts.tile_h,
        "bg_color": ts.bg_color,
        "mc1_color": ts.mc1_color,
        "mc2_color": ts.mc2_color,
        "charset": ts.charset_path,
        "tile_count": tile_count,
        "record_size": RECORD_SIZE,
        "ofs_records": ofs_records,
        "flagbits": ts.flagbits,
        "objects": objects_for_debug(ts.objects),
        "tiles": [
            {
                "id": t.tid,
                "name": t.name,
                "chars": t.chars,
                "color_mode": t.color_mode,
                "colors": t.colors,
                "flags": t.flags,
            } for t in tiles_sorted
        ],
        "blob_size": len(blob),
    }

    # .sym
    sym: List[str] = []
    sym.append(f'TSET name="{ts.name}" blob_size={len(blob)}\n')
    sym.append(f"GLOBAL bg={ts.bg_color} mc1={ts.mc1_color} mc2={ts.mc2_color}\n")
    if ts.charset_path:
        sym.append(f"CHARSET {ts.charset_path}\n")
    sym.append(f"HDR records={ofs_records} tileCount={tile_count} recordSize={RECORD_SIZE}\n\n")
    sym.append("TILES\n")
    for t in tiles_sorted:
        sym.append(
            f"  id={t.tid:3d} name={t.name} chars="
            f"{t.chars[0]:02X},{t.chars[1]:02X},{t.chars[2]:02X},{t.chars[3]:02X} "
            f"colorMode={t.color_mode} colors="
            f"{t.colors[0]},{t.colors[1]},{t.colors[2]},{t.colors[3]} "
            f"flags=0x{t.flags:04X}\n"
        )
    sym_text = "".join(sym)

    base = re.sub(r'[^A-Za-z0-9_]', "_", ts.name)
    blob_h = (
        "#pragma once\n"
        f"extern const unsigned char {base}_tset_blob[];\n"
        f"extern const unsigned long {base}_tset_blob_size;\n"
    )
    blob_c = (
        "// Auto-generated by tilesetc.py\n"
        f"#include \"tilesets/{base}_tset-blob.h\"\n"
        f"const unsigned char {base}_tset_blob[] = {{\n"
        f"    #embed \"../../{GEN_ROOT}/assets/{ts.name}.bin\"\n"
        "};\n"
        f"const unsigned long {base}_tset_blob_size = (unsigned long)sizeof({base}_tset_blob);\n"
    )

    return bytes(blob), ids_h, debug, sym_text, blob_h, blob_c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Input .tset file")
    ap.add_argument("-o", "--output", default="", help="Output blob (.o/.bin)")
    ap.add_argument("--ids", default="", help="Output *_ids.h")
    ap.add_argument("--blob-h", default="", help="Output *_tset-blob.h")
    ap.add_argument("--blob-c", default="", help="Output *_tset.c")
    ap.add_argument("--charset-h", default="", help="Output *_charset-blob.h")
    ap.add_argument("--charset-c", default="", help="Output *_charset.c")
    ap.add_argument("--sym", default="AUTO", help="Output .sym")
    ap.add_argument("--json", default="AUTO", help="Output debug .json")
    args = ap.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    try:
        ts = parse_tset(args.input)
    except TilesetParseError as e:
        path = os.path.abspath(e.path)
        print(f"{path}:{e.line}:{e.col}: error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        path = os.path.abspath(args.input)
        print(f"{path}:1:1: error: {e}", file=sys.stderr)
        sys.exit(1)
    blob, ids_h, debug, sym_text, blob_h, blob_c = compile_tset(ts)

    if not args.output:
        args.output = os.path.join(GEN_ROOT, "assets", f"{ts.name}.bin")
    if not args.ids:
        args.ids = os.path.join(GEN_ROOT, "include", f"{ts.name}_tset_ids.h")
    if not args.blob_h:
        args.blob_h = os.path.join(GEN_ROOT, "include", "tilesets", f"{ts.name}_tset-blob.h")
    if not args.blob_c:
        args.blob_c = os.path.join(GEN_ROOT, "src", "tilesets", f"{ts.name}_tset.c")
    if ts.charset_path:
        if not args.charset_h:
            args.charset_h = os.path.join(GEN_ROOT, "include", "tilesets", f"{ts.name}_charset-blob.h")
        if not args.charset_c:
            args.charset_c = os.path.join(GEN_ROOT, "src", "tilesets", f"{ts.name}_charset.c")
    if args.sym:
        args.sym = os.path.normpath(args.sym)
    if args.json:
        args.json = os.path.normpath(args.json)

    if not os.path.isabs(args.output):
        args.output = os.path.join(project_root, args.output)
    if not os.path.isabs(args.ids):
        args.ids = os.path.join(project_root, args.ids)
    if args.blob_h and not os.path.isabs(args.blob_h):
        args.blob_h = os.path.join(project_root, args.blob_h)
    if args.blob_c and not os.path.isabs(args.blob_c):
        args.blob_c = os.path.join(project_root, args.blob_c)
    if args.charset_h and not os.path.isabs(args.charset_h):
        args.charset_h = os.path.join(project_root, args.charset_h)
    if args.charset_c and not os.path.isabs(args.charset_c):
        args.charset_c = os.path.join(project_root, args.charset_c)
    if args.sym == "AUTO":
        args.sym = os.path.join(project_root, ANALYSIS_ROOT, "tilesets", f"{ts.name}.sym")
    if args.json == "AUTO":
        args.json = os.path.join(project_root, ANALYSIS_ROOT, "tilesets", f"{ts.name}.json")

    if args.sym and not os.path.isabs(args.sym):
        args.sym = os.path.join(project_root, args.sym)
    if args.json and not os.path.isabs(args.json):
        args.json = os.path.join(project_root, args.json)

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
    if args.sym:
        os.makedirs(os.path.dirname(args.sym), exist_ok=True)
    if args.json:
        os.makedirs(os.path.dirname(args.json), exist_ok=True)
    if args.blob_h:
        os.makedirs(os.path.dirname(args.blob_h), exist_ok=True)
    if args.blob_c:
        os.makedirs(os.path.dirname(args.blob_c), exist_ok=True)
    if args.charset_h:
        os.makedirs(os.path.dirname(args.charset_h), exist_ok=True)
    if args.charset_c:
        os.makedirs(os.path.dirname(args.charset_c), exist_ok=True)

    with open(args.output, "wb") as f:
        f.write(blob)
    print(f"Wrote {args.output} ({len(blob)} bytes)")

    with open(args.ids, "w", encoding="utf-8") as f:
        f.write(ids_h)
    print(f"Wrote {args.ids}")

    if args.blob_h:
        with open(args.blob_h, "w", encoding="utf-8") as f:
            f.write(blob_h)
        print(f"Wrote {args.blob_h}")

    if args.blob_c:
        base = re.sub(r'[^A-Za-z0-9_]', "_", ts.name)
        rel_blob = os.path.relpath(args.output, os.path.dirname(args.blob_c) or ".")
        rel_blob = rel_blob.replace("\\", "/")
        blob_c_local = (
            "// Auto-generated by tilesetc.py\n"
            f"#include \"tilesets/{base}_tset-blob.h\"\n"
            f"const unsigned char {base}_tset_blob[] = {{\n"
            f"    #embed \"{rel_blob}\"\n"
            "};\n"
            f"const unsigned long {base}_tset_blob_size = (unsigned long)sizeof({base}_tset_blob);\n"
        )
        with open(args.blob_c, "w", encoding="utf-8") as f:
            f.write(blob_c_local)
        print(f"Wrote {args.blob_c}")

    if ts.charset_path and args.charset_h and args.charset_c:
        charset_src = ts.charset_path
        if not os.path.isabs(charset_src):
            charset_src = os.path.join(os.path.dirname(args.input), charset_src)
            if not os.path.isfile(charset_src):
                charset_src = os.path.join(os.path.dirname(args.input), "..", ts.charset_path)
        charset_src = os.path.normpath(charset_src)
        rel = os.path.relpath(charset_src, os.path.dirname(args.charset_c))
        base = re.sub(r'[^A-Za-z0-9_]', "_", ts.name)
        charset_h = (
            "#pragma once\n"
            f"extern const unsigned char {base}_charset_blob[];\n"
            f"extern const unsigned long {base}_charset_blob_size;\n"
        )
        charset_c = (
            "// Auto-generated by tilesetc.py\n"
            f"#include \"tilesets/{base}_charset-blob.h\"\n"
            f"const unsigned char {base}_charset_blob[] = {{\n"
            f"    #embed \"{rel}\"\n"
            "};\n"
            f"const unsigned long {base}_charset_blob_size = (unsigned long)sizeof({base}_charset_blob);\n"
        )
        with open(args.charset_h, "w", encoding="utf-8") as f:
            f.write(charset_h)
        print(f"Wrote {args.charset_h}")
        with open(args.charset_c, "w", encoding="utf-8") as f:
            f.write(charset_c)
        print(f"Wrote {args.charset_c}")

    if args.sym:
        with open(args.sym, "w", encoding="utf-8") as f:
            f.write(sym_text)
        print(f"Wrote {args.sym}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(debug, f, indent=2)
        print(f"Wrote {args.json}")


if __name__ == "__main__":
    main()
