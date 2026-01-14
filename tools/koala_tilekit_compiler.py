#!/usr/bin/env python3
"""
koala_tilekit_compiler.py
Compile a C64 Koala image plus a tile spec into a tileset, charset, and maps.

Inputs:
  - Koala Painter .kla (images/level_maint_bg.kla)
  - Spec markdown or JSON (images/level_maint_bg.md or .json)

Outputs:
  - charset (.bin) in assets
  - tileset (.tset) with named tiles and object stamps
  - full-image metatile map (.bin) in gen/analysis
  - preview PNGs + debug info in gen/analysis
"""

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from gen_paths import ANALYSIS_ROOT
C64 = {
    0: ("black", (0, 0, 0)),
    1: ("white", (255, 255, 255)),
    2: ("red", (136, 0, 0)),
    3: ("cyan", (170, 255, 238)),
    4: ("purple", (204, 68, 204)),
    5: ("green", (0, 204, 85)),
    6: ("blue", (0, 0, 170)),
    7: ("yellow", (238, 238, 119)),
    8: ("orange", (221, 136, 85)),
    9: ("brown", (102, 68, 0)),
    10: ("light_red", (255, 119, 119)),
    11: ("dark_grey", (51, 51, 51)),
    12: ("grey", (119, 119, 119)),
    13: ("light_green", (170, 255, 102)),
    14: ("light_blue", (0, 136, 255)),
    15: ("light_grey", (187, 187, 187)),
}
PAL = np.array([C64[i][1] for i in range(16)], dtype=np.uint8)

MT_RE = re.compile(r"^METATILE\s+(\S+)\s+(.+)$", re.IGNORECASE)
SAMPLE_RE = re.compile(r"SAMPLE_C64_XY:\s*\((\d+),\s*(\d+)\)", re.IGNORECASE)
FLAGS_RE = re.compile(r"FLAGS:\s*([A-Z0-9_,| ]+)", re.IGNORECASE)
FROM_OBJ_RE = re.compile(r"FROM_OBJECT:\s*(\S+)", re.IGNORECASE)
ROLE_RE = re.compile(r"ROLE:\s*(.+)", re.IGNORECASE)
VARIANT_RE = re.compile(r"VARIANT_OF:\s*(\S+)", re.IGNORECASE)
REUSE_RE = re.compile(r"REUSE_NOTE:\s*(.+)", re.IGNORECASE)


def load_kla(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) == 10003:
        data = data[2:]
    if len(data) != 10001:
        raise ValueError(f"Unexpected Koala size {len(data)} bytes: {path}")
    bitmap = data[0:8000]
    screen = data[8000:9000]
    color = data[9000:10000]
    bg = data[10000]

    idx = np.zeros((200, 320), dtype=np.uint8)
    for cy in range(25):
        for cx in range(40):
            sc = screen[cy * 40 + cx]
            c1 = (sc >> 4) & 0x0F
            c2 = sc & 0x0F
            c3 = color[cy * 40 + cx] & 0x0F
            cell_base = (cy * 40 + cx) * 8
            for y in range(8):
                b = bitmap[cell_base + y]
                for xmc in range(4):
                    code = (b >> (6 - 2 * xmc)) & 3
                    if code == 0:
                        col = bg
                    elif code == 1:
                        col = c1
                    elif code == 2:
                        col = c2
                    else:
                        col = c3
                    px = cx * 8 + xmc * 2
                    py = cy * 8 + y
                    idx[py, px] = col
                    idx[py, px + 1] = col
    return idx


def idx_to_rgb(idx_img: np.ndarray) -> Image.Image:
    rgb = PAL[idx_img].astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def choose_global_colors(idx_img: np.ndarray):
    counts = np.bincount(idx_img.flatten(), minlength=16)
    order = counts.argsort()[::-1]
    return int(order[0]), int(order[1]), int(order[2])


def encode_mc_char_best(cell8x8: np.ndarray, bg: int, mc1: int, mc2: int):
    best_bytes = None
    best_lc = 0
    best_err = 10**9

    for lc in range(16):
        err = 0
        data = []
        for y in range(8):
            byte = 0
            for xmc in range(4):
                a = int(cell8x8[y, 2 * xmc])
                b = int(cell8x8[y, 2 * xmc + 1])

                choices = [bg, mc1, mc2, lc]
                costs = [
                    (a != choices[0]) + (b != choices[0]),
                    (a != choices[1]) + (b != choices[1]),
                    (a != choices[2]) + (b != choices[2]),
                    (a != choices[3]) + (b != choices[3]),
                ]
                ci = int(np.argmin(costs))
                err += costs[ci]
                byte |= (ci & 3) << (6 - 2 * xmc)
            data.append(byte)

        if err < best_err:
            best_err = err
            best_lc = lc
            best_bytes = bytes(data)
            if best_err == 0:
                break

    return best_bytes, best_lc, best_err


def choose_mc_colors(cells: list[np.ndarray], bg: int, fast: bool = False) -> tuple[int, int]:
    colors = [c for c in range(16) if c != bg]
    if fast:
        counts = np.bincount(np.concatenate([c.flatten() for c in cells]), minlength=16)
        counts[bg] = 0
        order = counts.argsort()[::-1]
        return int(order[0]), int(order[1])

    # Weight by unique cells to avoid recomputing identical blocks
    cell_counts = Counter([c.tobytes() for c in cells])
    unique_cells = [np.frombuffer(k, dtype=np.uint8).reshape(8, 8) for k in cell_counts.keys()]
    cell_weights = list(cell_counts.values())

    best_mc1 = colors[0]
    best_mc2 = colors[1]
    best_err = 10**9
    err_cache = {}
    for i, mc1 in enumerate(colors):
        for mc2 in colors[i + 1:]:
            err = 0
            for cell, weight in zip(unique_cells, cell_weights):
                key = (mc1, mc2, cell.tobytes())
                if key in err_cache:
                    e = err_cache[key]
                else:
                    _, _, e = encode_mc_char_best(cell, bg, mc1, mc2)
                    err_cache[key] = e
                err += e * weight
            if err < best_err:
                best_err = err
                best_mc1 = mc1
                best_mc2 = mc2
    return best_mc1, best_mc2


def render_mc_char(char8: bytes, lc: int, bg: int, mc1: int, mc2: int) -> np.ndarray:
    out = np.full((8, 8), bg, dtype=np.uint8)
    mapping = {0: bg, 1: mc1, 2: mc2, 3: lc}
    for y in range(8):
        b = char8[y]
        for xmc in range(4):
            code = (b >> (6 - 2 * xmc)) & 3
            col = mapping[int(code)]
            out[y, 2 * xmc] = col
            out[y, 2 * xmc + 1] = col
    return out


def parse_md(path: Path):
    entries = []
    cur = None
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        m = MT_RE.match(line)
        if m:
            if cur:
                entries.append(cur)
            cur = {
                "id": m.group(1),
                "name": m.group(2).strip(),
                "flags": "DECOR",
                "from_object": "",
                "role": "",
                "variant_of": "",
                "reuse_note": "",
            }
            continue
        if cur:
            sm = SAMPLE_RE.search(line)
            if sm:
                cur["sample"] = tuple(int(v) for v in sm.groups())
            fm = FLAGS_RE.search(line)
            if fm:
                cur["flags"] = normalize_flags(fm.group(1))
            om = FROM_OBJ_RE.search(line)
            if om:
                cur["from_object"] = om.group(1).strip()
            rm = ROLE_RE.search(line)
            if rm:
                cur["role"] = rm.group(1).strip()
            vm = VARIANT_RE.search(line)
            if vm:
                cur["variant_of"] = vm.group(1).strip()
            rn = REUSE_RE.search(line)
            if rn:
                cur["reuse_note"] = rn.group(1).strip()
    if cur:
        entries.append(cur)
    return entries, raw_lines


def parse_json(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    cells = data.get("cells", [])
    objects = data.get("objects", [])

    # Build occupancy map from objects first.
    obj_grid = {}
    for obj in objects:
        ox = int(obj.get("x", 0))
        oy = int(obj.get("y", 0))
        ow = int(obj.get("w", 1))
        oh = int(obj.get("h", 1))
        for dy in range(oh):
            for dx in range(ow):
                obj_grid[(ox + dx, oy + dy)] = (obj, dx, dy)

    entries = []
    seen = set()
    idx = 1

    def add_entry(name, sample, flags, from_object="", object_meta=None):
        nonlocal idx
        entry = {
            "id": f"AUTO_{idx:03d}",
            "name": name,
            "flags": flags or "DECOR",
            "from_object": from_object,
            "role": "",
            "variant_of": "",
            "reuse_note": "",
            "sample": sample,
        }
        if object_meta:
            entry.update(object_meta)
        entries.append(entry)
        idx += 1

    for cell in cells:
        x = int(cell.get("x", 0))
        y = int(cell.get("y", 0))
        if (x, y) in obj_grid:
            continue
        desc = (cell.get("description") or "CELL").strip()
        flags = normalize_flags(" ".join(cell.get("flags", [])))
        key = ("cell", desc, flags)
        if key in seen:
            continue
        seen.add(key)
        add_entry(desc, (x * 16, y * 16), flags)

    for (x, y), (obj, dx, dy) in sorted(obj_grid.items()):
        otype = (obj.get("type") or "OBJECT").strip()
        desc = (obj.get("description") or otype).strip()
        flags = normalize_flags(" ".join(obj.get("flags", [])))
        ow = int(obj.get("w", 1))
        oh = int(obj.get("h", 1))
        part = f"{dx + 1},{dy + 1}/{ow},{oh}"
        name = f"{otype} {desc} part {part}"
        key = ("obj", otype, desc, flags, dx, dy, ow, oh)
        if key in seen:
            continue
        seen.add(key)
        add_entry(
            name,
            (x * 16, y * 16),
            flags,
            from_object=obj.get("id", ""),
            object_meta={
                "object_id": obj.get("id", ""),
                "object_type": otype,
                "object_desc": desc,
                "object_w": ow,
                "object_h": oh,
                "object_dx": dx,
                "object_dy": dy,
                "role": otype,
                "variant_of": obj.get("id", ""),
            },
        )

    return entries, []


def sanitize_tile_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9_]", "_", name.upper())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "TILE"


def normalize_flags(flags: str) -> str:
    parts = [p.strip().upper() for p in re.split(r"[,\s|]+", flags) if p.strip()]
    return "|".join(parts)


def build_charset(char_patterns: list[bytes]):
    counts = Counter(char_patterns)
    uniq = list(counts.keys())
    if len(uniq) <= 256:
        charset = bytearray(256 * 8)
        mapping = {p: i for i, p in enumerate(uniq)}
        for i, p in enumerate(uniq):
            charset[i * 8:(i + 1) * 8] = p
        return uniq, charset, mapping

    kept = [p for p, _ in counts.most_common(256)]
    mapping = {p: i for i, p in enumerate(kept)}
    bitcount = [bin(i).count("1") for i in range(256)]

    def char_distance(a: bytes, b: bytes) -> int:
        return sum(bitcount[a[i] ^ b[i]] for i in range(8))

    for p in uniq:
        if p in mapping:
            continue
        best_i = 0
        best_d = 10**9
        for i, k in enumerate(kept):
            d = char_distance(p, k)
            if d < best_d:
                best_d = d
                best_i = i
                if d == 0:
                    break
        mapping[p] = best_i

    charset = bytearray(256 * 8)
    for i, p in enumerate(kept):
        charset[i * 8:(i + 1) * 8] = p
    return kept, charset, mapping


def tile_distance(a, b) -> int:
    ach, acol = a
    bch, bcol = b
    d = 0
    for i in range(4):
        d += 0 if ach[i] == bch[i] else 1
        d += 0 if acol[i] == bcol[i] else 1
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", help="Spec markdown")
    ap.add_argument("--kla", default="", help="Koala file (defaults to match md name)")
    ap.add_argument("--out-dir", default="", help="Output directory (defaults to debug/<md name>)")
    ap.add_argument("--charset", default="", help="Output charset bin (defaults to assets/<md name>_chargen.bin)")
    ap.add_argument("--tset", default="", help="Output tileset (defaults to levels/<md name>.tset)")
    ap.add_argument("--tmap", default="", help="Output full map (defaults to debug/<md name>/<md name>_tmap.bin)")
    ap.add_argument("--tile-map", default="", help="Output tile location map (defaults to debug/<md name>/<md name>_tile_locations.png)")
    ap.add_argument("--info", default="", help="Output info (defaults to debug/<md name>/<md name>_info.txt)")
    ap.add_argument("--fast", action="store_true", help="Use fast MC1/MC2 selection")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    md_path = (root / args.md).resolve()
    base_name = md_path.stem
    if not args.kla:
        args.kla = str(Path(md_path.parent) / f"{base_name}.kla")
    if not args.out_dir:
        args.out_dir = str(Path(ANALYSIS_ROOT) / base_name)
    if not args.charset:
        args.charset = str(Path("assets") / f"{base_name}_chargen.bin")
    if not args.tset:
        args.tset = str(Path("levels") / f"{base_name}.tset")
    if not args.tmap:
        args.tmap = str(Path(ANALYSIS_ROOT) / base_name / f"{base_name}_tmap.bin")
    if not args.tile_map:
        args.tile_map = str(Path(ANALYSIS_ROOT) / base_name / f"{base_name}_tile_locations.png")
    if not args.info:
        args.info = str(Path(ANALYSIS_ROOT) / base_name / f"{base_name}_info.txt")

    kla_path = (root / args.kla).resolve()
    out_dir = (root / args.out_dir).resolve()
    charset_path = (root / args.charset).resolve()
    tset_path = (root / args.tset).resolve()
    tmap_path = (root / args.tmap).resolve()
    tile_map_path = (root / args.tile_map).resolve()
    info_path = (root / args.info).resolve()

    if md_path.suffix.lower() == ".json":
        entries, _ = parse_json(md_path)
    else:
        entries, _ = parse_md(md_path)
    if not entries:
        raise SystemExit(f"No entries found in {md_path}")

    idx = load_kla(kla_path)
    bg, _, _ = choose_global_colors(idx)
    cells = []
    for cy in range(25):
        for cx in range(40):
            cell = idx[cy * 8:(cy + 1) * 8, cx * 8:(cx + 1) * 8]
            cells.append(cell)
    mc1, mc2 = choose_mc_colors(cells, bg, fast=args.fast)

    def extract_tile(px: int, py: int):
        if px < 0 or py < 0 or px + 15 >= 320 or py + 15 >= 200:
            raise ValueError(f"Sample out of bounds: ({px},{py})")
        chars = []
        cols = []
        for dy in (0, 8):
            for dx in (0, 8):
                cell = idx[py + dy:py + dy + 8, px + dx:px + dx + 8]
                p, lc, _err = encode_mc_char_best(cell, bg, mc1, mc2)
                chars.append(p)
                cols.append(lc)
        return tuple(chars), tuple(cols)

    tiles = []
    for e in entries:
        if "sample" not in e:
            raise SystemExit(f"Missing SAMPLE_C64_XY for {e['name']}")
        sx, sy = e["sample"]
        try:
            e["tile"] = extract_tile(sx, sy)
        except ValueError as exc:
            raise SystemExit(f"{e['name']}: {exc}") from exc
        tiles.append(e)

    # Build charset from selected tiles only
    char_patterns = []
    for e in tiles:
        chars, _cols = e["tile"]
        char_patterns.extend(list(chars))
    uniq_chars, charset, char_index = build_charset(char_patterns)
    charset_path.parent.mkdir(parents=True, exist_ok=True)
    charset_path.write_bytes(bytes(charset))

    lines = []
    lines.append("; Auto-generated from MD spec. Comments annotate charmap and tile intent.\n\n")
    def color_name(idx: int) -> str:
        return C64[idx][0].upper()

    lines.append(
        f'TSET name="{base_name}" tileSize=2x2 bgColor={color_name(bg)} mc1Color={color_name(mc1)} '
        f'mc2Color={color_name(mc2)} charset={args.charset}\n\n'
    )
    charmap_seed = {
        "WALL": "#",
        "FLOOR": "=",
        "PLATFORM": "=",
        "PIPE": "P",
        "LADDER": "H",
        "DOOR": "D",
        "EXIT": "E",
        "TERMINAL": "T",
        "VENT": "V",
        "TRIM": "_",
        "SEAM": "|",
        "GRILLE": "G",
        "HAZARD": "!",
        "VOID": ".",
        "CABLE": "-",
    }
    taken = set()
    available = list(".#=HPTVDE_|G!-=+0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")

    def pick_char(name: str) -> str:
        for key, ch in charmap_seed.items():
            if key in name:
                if ch not in taken:
                    return ch
        for ch in available:
            if ch not in taken:
                return ch
        return "?"

    for e in tiles:
        e["name"] = sanitize_tile_name(e["name"])
    id_to_name = {e["id"]: e["name"] for e in tiles}

    def charmap_line(e, name_override=None, role_override=None):
        name = name_override or e["name"]
        ch = pick_char(name.upper())
        taken.add(ch)
        variant = e.get("variant_of", "")
        if variant.upper() == "NONE":
            variant = ""
        if variant and variant in id_to_name:
            variant = id_to_name[variant]
        role = role_override or e.get("role", "")
        reuse = e.get("reuse_note", "")
        comment_parts = []
        if role:
            comment_parts.append(role)
        if reuse:
            comment_parts.append(reuse)
        if variant:
            comment_parts.append(f"[{variant}]")
        suffix = f" ; {' '.join(comment_parts)}" if comment_parts else ""
        return f"{ch} {name}{suffix}\n"

    non_obj = [e for e in tiles if not e.get("from_object")]
    obj = [e for e in tiles if e.get("from_object")]

    object_groups = {}
    object_order = []
    for e in obj:
        key = e.get("from_object", "")
        if key not in object_groups:
            object_groups[key] = {"entries": [], "label": "", "type": ""}
            object_order.append(key)
        object_groups[key]["entries"].append(e)
        label = e.get("object_desc", "") or e.get("from_object", "")
        if label:
            object_groups[key]["label"] = label
        obj_type = e.get("object_type", "")
        if obj_type:
            object_groups[key]["type"] = obj_type

    # CHARMAP: non-object tiles + 1x1 object tiles + object stamps
    lines.append("CHARMAP\n")
    if non_obj:
        lines.append("; NON-OBJECT TILES\n")
        for e in non_obj:
            lines.append(charmap_line(e))
        lines.append("\n")

    obj_single = []
    for key in object_order:
        og = object_groups[key]
        ow = int(og["entries"][0].get("object_w", 1))
        oh = int(og["entries"][0].get("object_h", 1))
        if ow == 1 and oh == 1:
            obj_single.extend(og["entries"])
    alias_tiles = []
    if obj_single:
        lines.append("; 1x1 OBJECT TILES\n")
        for e in obj_single:
            type_name = sanitize_tile_name(e.get("object_type", "") or "OBJECT")
            role_bits = []
            if e.get("object_type"):
                role_bits.append(e["object_type"])
            if e.get("object_desc"):
                role_bits.append(e["object_desc"])
            role_override = " - ".join(role_bits) or e.get("role", "")
            lines.append(charmap_line(e, name_override=type_name, role_override=role_override))
            alias = dict(e)
            alias["name"] = type_name
            alias["role"] = role_override
            alias_tiles.append(alias)
        lines.append("\n")

    for key in object_order:
        og = object_groups[key]
        obj_type = sanitize_tile_name(og.get("type", "") or "OBJECT")
        obj_desc = og.get("label", "") or key
        obj_name = obj_type
        ow = int(og["entries"][0].get("object_w", 1))
        oh = int(og["entries"][0].get("object_h", 1))
        if ow == 1 and oh == 1:
            continue
        ch = pick_char(obj_name.upper())
        taken.add(ch)
        og["ch"] = ch
        og["obj_name"] = obj_name
        suffix = f" ; {obj_desc}" if obj_desc else " ; object stamp"
        lines.append(f"{ch} {obj_name}{suffix}\n")
    lines.append("END\n\n")

    if object_groups:
        lines.append("OBJECTS\n")
        for obj_id in object_order:
            og = object_groups[obj_id]
            ow = int(og["entries"][0].get("object_w", 1))
            oh = int(og["entries"][0].get("object_h", 1))
            if ow == 1 and oh == 1:
                continue
            tiles_map = {}
            for e in og["entries"]:
                dx = int(e.get("object_dx", 0))
                dy = int(e.get("object_dy", 0))
                tiles_map[(dx, dy)] = e["name"]
            missing = False
            tiles_list = []
            for dy in range(oh):
                for dx in range(ow):
                    name = tiles_map.get((dx, dy))
                    if not name:
                        missing = True
                        break
                    tiles_list.append(name)
                if missing:
                    break
            if missing:
                continue
            tiles_str = ",".join(tiles_list)
            obj_name = og.get("obj_name") or sanitize_tile_name(og.get("type", "") or "OBJECT")
            lines.append(f"{obj_name} size={ow}x{oh} tiles={tiles_str}\n")
        lines.append("END\n\n")

    tile_output = []

    def emit_tile(e, include_role=False):
        name = e["name"]
        chars, cols = e["tile"]
        mapped = tuple(uniq_chars[char_index[p]] for p in chars)
        e["tile_rep"] = (mapped, cols)
        ch = ",".join(f"0x{char_index[p]:02X}" for p in chars)
        co = ",".join(color_name(c) for c in cols)
        flags = "|".join(f for f in e["flags"].split("|") if f)
        role = e.get("role", "")
        if include_role and role:
            lines.append(f"; {role}\n")
        lines.append(f"{name} chars={ch} colors={co} flags={flags}\n")
        tile_output.append(e)

    lines.append("TILES\n")
    if non_obj:
        lines.append("; NON-OBJECT TILES\n")
        for e in non_obj:
            emit_tile(e, include_role=True)

    for key in object_order:
        og = object_groups[key]
        label = og["label"] or key or "OBJECT"
        entries = []
        for e in og["entries"]:
            ow = int(e.get("object_w", 1))
            oh = int(e.get("object_h", 1))
            if ow == 1 and oh == 1:
                continue
            entries.append(e)
        if not entries:
            continue
        lines.append(f"; OBJECT {label}\n")
        for e in entries:
            emit_tile(e)

    if alias_tiles:
        lines.append("; 1x1 OBJECT TILE ALIASES\n")
        for e in alias_tiles:
            emit_tile(e)
    lines.append("\nEND\n\nEND\n")
    tset_path.parent.mkdir(parents=True, exist_ok=True)
    tset_path.write_text("".join(lines), encoding="utf-8")

    # Build full-image tmap using nearest tile
    tile_defs = [e["tile_rep"] for e in tile_output]
    tmap = np.zeros((12, 20), dtype=np.uint8)
    for my in range(12):
        for mx in range(20):
            tile = extract_tile(mx * 16, my * 16)
            best_i = 0
            best_d = 10**9
            for i, cand in enumerate(tile_defs):
                d = tile_distance(tile, cand)
                if d < best_d:
                    best_d = d
                    best_i = i
                    if d == 0:
                        break
            tmap[my, mx] = best_i

    out_dir.mkdir(parents=True, exist_ok=True)
    tmap_path.parent.mkdir(parents=True, exist_ok=True)
    tmap_path.write_bytes(tmap.flatten().tobytes())

    # Per-tile images + markdown catalog
    tiles_dir = out_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    tile_loc = np.full((200, 320), bg, dtype=np.uint8)
    tiles_md = out_dir / "tiles.md"
    md_tiles = []
    md_tiles.append(f"# {base_name} Tiles\n\n")
    md_tiles.append("## Overview\n\n")
    md_tiles.append(f"![tile locations]({tile_map_path.name})\n\n")
    orig_png = md_path.parent / f"{base_name}.png"
    if orig_png.exists():
        rel = Path(os.path.relpath(orig_png, tiles_md.parent)).as_posix()
        md_tiles.append(f"![source image]({rel})\n\n")
    md_tiles.append("## Palette\n\n")
    md_tiles.append(f"- Background: {C64[bg][0].upper()}\n")
    md_tiles.append(f"- MC1: {C64[mc1][0].upper()}\n")
    md_tiles.append(f"- MC2: {C64[mc2][0].upper()}\n\n")
    md_tiles.append("| Tile | Name | Flags | Grid | Role | Variant | Chars | Colors | Reuse |\n")
    md_tiles.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")

    object_tiles = {}

    for e in tile_output:
        name = e["name"]
        chars, cols = e["tile_rep"]
        sx, sy = e.get("sample", (0, 0))
        tile_img = np.full((16, 16), bg, dtype=np.uint8)
        for dy in range(2):
            for dx in range(2):
                ch = chars[dy * 2 + dx]
                lc = cols[dy * 2 + dx]
                tile_img[dy * 8:(dy + 1) * 8, dx * 8:(dx + 1) * 8] = render_mc_char(
                    ch, lc, bg, mc1, mc2
                )
        tile_loc[sy:sy + 16, sx:sx + 16] = tile_img
        img = idx_to_rgb(tile_img).resize((64, 64), resample=Image.NEAREST)
        safe = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").lower() or "tile"
        img_name = f"{safe}.png"
        img.save(tiles_dir / img_name)

        obj_id = e.get("object_id", "")
        if obj_id:
            obj_entry = object_tiles.setdefault(
                obj_id,
                {
                    "type": e.get("object_type", ""),
                    "desc": e.get("object_desc", ""),
                    "w": int(e.get("object_w", 1)),
                    "h": int(e.get("object_h", 1)),
                    "parts": {},
                },
            )
            obj_entry["parts"][(int(e.get("object_dx", 0)), int(e.get("object_dy", 0)))] = {
                "img": tile_img,
                "name": img_name,
            }

        sample = e.get("sample", (0, 0))
        sample_str = f"({sample[0]},{sample[1]})"
        flags = e.get("flags", "").replace("|", " &#124; ")
        grid_str = f"({sample[0]//16},{sample[1]//16})"
        role = e.get("role", "")
        variant = e.get("variant_of", "")
        reuse = e.get("reuse_note", "")
        ch_idx = ",".join(f"0x{char_index[p]:02X}" for p in e["tile"][0])
        col_str = ",".join(C64[c][0].upper() for c in e["tile"][1])

        md_tiles.append(
            f"| ![]({{tiles}}/{img_name}) | {name} | {flags} | {grid_str} | {role} | {variant} | {ch_idx} | {col_str} | {reuse} |\n"
        )

    tiles_md.write_text("".join(md_tiles).replace("{tiles}", "tiles"), encoding="utf-8")
    tile_map_path.parent.mkdir(parents=True, exist_ok=True)
    idx_to_rgb(tile_loc).resize((640, 400), resample=Image.NEAREST).save(tile_map_path)

    if object_tiles:
        md_obj = []
        md_obj.append("\n## Objects\n\n")
        md_obj.append("| Object | Type | Parts | Combined |\n")
        md_obj.append("| --- | --- | --- | --- |\n")
        for obj_id, obj in object_tiles.items():
            w = obj["w"]
            h = obj["h"]
            combo = np.full((h * 16, w * 16), bg, dtype=np.uint8)
            part_imgs = []
            for dy in range(h):
                for dx in range(w):
                    part = obj["parts"].get((dx, dy))
                    if part:
                        combo[dy * 16:(dy + 1) * 16, dx * 16:(dx + 1) * 16] = part["img"]
                        part_imgs.append(f"![](tiles/{part['name']})")
            combo_img = idx_to_rgb(combo).resize((w * 64, h * 64), resample=Image.NEAREST)
            safe = re.sub(r"[^A-Za-z0-9_]+", "_", obj_id).strip("_").lower() or "object"
            combo_name = f"object_{safe}.png"
            combo_img.save(tiles_dir / combo_name)
            label = f"{obj_id} {obj['desc']}".strip()
            obj_type = obj["type"]
            md_obj.append(f"| {label} | {obj_type} | {' '.join(part_imgs)} | ![](tiles/{combo_name}) |\n")
        tiles_md.write_text("".join(md_tiles).replace("{tiles}", "tiles") + "".join(md_obj), encoding="utf-8")

    info = "\n".join([
        f"INPUT: {kla_path.name}",
        f"SOURCE: {md_path.name}",
        "",
        "Multicolor character mode setup:",
        "  $D016 bit4 = 1",
        f"  $D021 BG  = {bg} ({C64[bg][0]})",
        f"  $D022 MC1 = {mc1} ({C64[mc1][0]})",
        f"  $D023 MC2 = {mc2} ({C64[mc2][0]})",
        "",
        f"Chars used: {len(uniq_chars)}",
        f"Tiles used: {len(tile_defs)}",
    ])
    info_path.write_text(info, encoding="utf-8")

    print(f"Wrote charset: {charset_path}")
    print(f"Wrote tileset: {tset_path}")
    print(f"Wrote tmap: {tmap_path}")
    print(f"Wrote tiles: {tiles_dir}")
    print(f"Wrote tiles md: {tiles_md}")
    print(f"Wrote tile map: {tile_map_path}")


if __name__ == "__main__":
    main()
