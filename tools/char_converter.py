from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from PIL import Image

C64_PALETTE = [
    ("Black", (0x00, 0x00, 0x00)),
    ("White", (0xFF, 0xFF, 0xFF)),
    ("Red", (0x88, 0x00, 0x00)),
    ("Cyan", (0xAA, 0xFF, 0xEE)),
    ("Purple", (0xCC, 0x44, 0xCC)),
    ("Green", (0x00, 0xCC, 0x55)),
    ("Blue", (0x00, 0x00, 0xAA)),
    ("Yellow", (0xEE, 0xEE, 0x77)),
    ("Orange", (0xDD, 0x88, 0x55)),
    ("Brown", (0x66, 0x44, 0x00)),
    ("Light Red", (0xFF, 0x77, 0x77)),
    ("Dark Grey", (0x33, 0x33, 0x33)),
    ("Grey", (0x77, 0x77, 0x77)),
    ("Light Green", (0xAA, 0xFF, 0x66)),
    ("Light Blue", (0x00, 0x88, 0xFF)),
    ("Light Grey", (0xBB, 0xBB, 0xBB)),
]

PALETTE_RGB = [rgb for _name, rgb in C64_PALETTE]


@dataclass
class ConvertResult:
    charset: bytes
    screen_ram: List[int]
    color_ram: List[int]
    bg: int
    mc1: int
    mc2: int
    remap_counts: Dict[Tuple[int, int], int]


def _nearest_color_index(rgb: Tuple[int, int, int]) -> int:
    best = 0
    best_d = 10**9
    r, g, b = rgb
    for idx, (pr, pg, pb) in enumerate(PALETTE_RGB):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best = idx
    return best


def _quantize(image: Image.Image) -> List[List[int]]:
    rgb = image.convert("RGB")
    w, h = rgb.size
    pixels = rgb.load()
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            out[y][x] = _nearest_color_index(pixels[x, y])
    return out


def _pick_global(hist: List[int], exclude: set[int]) -> int:
    best = None
    best_count = -1
    for idx, count in enumerate(hist):
        if idx in exclude:
            continue
        if count > best_count:
            best_count = count
            best = idx
    if best is not None:
        return best
    for idx, count in enumerate(hist):
        if count > best_count:
            best_count = count
            best = idx
    return 0 if best is None else best


def _palette_distance(idx_a: int, idx_b: int) -> int:
    ra, ga, ba = PALETTE_RGB[idx_a]
    rb, gb, bb = PALETTE_RGB[idx_b]
    return (ra - rb) ** 2 + (ga - gb) ** 2 + (ba - bb) ** 2


def _nearest_allowed(color: int, allowed: set[int]) -> int:
    if color in allowed:
        return color
    best = None
    best_d = 10**9
    for idx in allowed:
        d = _palette_distance(color, idx)
        if d < best_d:
            best_d = d
            best = idx
    return color if best is None else best


def convert_image(
    image: Image.Image,
    mode: str,
    strategy: str,
    locks: Dict[str, int | None],
    remap: bool = True,
    placement: Dict[str, int] | None = None,
) -> ConvertResult:
    """Convert an image to C64 charset + screen/color RAM.

    When placement is provided, the source image is scaled to placement["scaled_w"/"scaled_h"]
    and placed at placement["offset_x"/"offset_y"] inside a target canvas of size
    placement["target_w"/"target_h"] without constructing the canvas in memory.
    """
    if placement:
        target_w = placement["target_w"]
        target_h = placement["target_h"]
        offset_x = placement["offset_x"]
        offset_y = placement["offset_y"]
        scaled_w = placement["scaled_w"]
        scaled_h = placement["scaled_h"]
        scaled = image.resize((scaled_w, scaled_h), Image.NEAREST)
        scaled_data = _quantize(scaled)
        hist = [0] * 16
        for row in scaled_data:
            for color in row:
                hist[color] += 1
        width, height = target_w, target_h
    else:
        data = _quantize(image)
        width, height = image.size
        hist = [0] * 16
        for row in data:
            for color in row:
                hist[color] += 1
        offset_x = 0
        offset_y = 0
        scaled_w = width
        scaled_h = height
        scaled_data = data

    cols = width // 8
    rows = height // 8

    bg = locks.get("bg") if strategy in ("lock_bg", "lock_bg_mc1", "lock_bg_mc1_mc2") else None
    if bg is None:
        bg = _pick_global(hist, set())

    mc1 = 0
    mc2 = 0
    if mode == "multicolor":
        exclude = {bg}
        if strategy in ("lock_bg_mc1", "lock_bg_mc1_mc2") and locks.get("mc1") is not None:
            mc1 = locks["mc1"]
            exclude.add(mc1)
        else:
            mc1 = _pick_global(hist, exclude)
            exclude.add(mc1)
        if strategy == "lock_bg_mc1_mc2" and locks.get("mc2") is not None:
            mc2 = locks["mc2"]
            exclude.add(mc2)
        else:
            mc2 = _pick_global(hist, exclude)
            exclude.add(mc2)

    charset = bytearray()
    screen_ram = []
    color_ram = []
    remap_counts: Dict[Tuple[int, int], int] = {}

    def add_remap(src: int, dst: int) -> None:
        if src == dst:
            return
        remap_counts[(src, dst)] = remap_counts.get((src, dst), 0) + 1

    clash_counts: Dict[Tuple[int, int], int] = {}

    for cy in range(rows):
        for cx in range(cols):
            colors = []
            for y in range(8):
                for x in range(8):
                    px = cx * 8 + x
                    py = cy * 8 + y
                    if offset_x <= px < offset_x + scaled_w and offset_y <= py < offset_y + scaled_h:
                        sx = px - offset_x
                        sy = py - offset_y
                        colors.append(scaled_data[sy][sx])
                    else:
                        colors.append(bg)
            local_hist = [0] * 16
            for c in colors:
                local_hist[c] += 1

            if mode == "hires":
                fg = _pick_global(local_hist, {bg})
                screen_ram.append((fg << 4) | bg)
                for y in range(8):
                    byte = 0
                    for x in range(8):
                        px = cx * 8 + x
                        py = cy * 8 + y
                        if offset_x <= px < offset_x + scaled_w and offset_y <= py < offset_y + scaled_h:
                            sx = px - offset_x
                            sy = py - offset_y
                            color = scaled_data[sy][sx]
                        else:
                            color = bg
                        if color not in (bg, fg):
                            if remap:
                                src_color = color
                                color = fg if _palette_distance(color, fg) <= _palette_distance(color, bg) else bg
                                add_remap(src_color, color)
                            else:
                                clash_counts[(cx, cy)] = clash_counts.get((cx, cy), 0) + 1
                        bit = 1 if color == fg else 0
                        byte |= bit << (7 - x)
                    charset.append(byte)
                color_ram.append(0)
                continue

            # multicolor
            allowed = {bg, mc1, mc2}
            local = _pick_global(local_hist, allowed)
            allowed.add(local)
            screen_ram.append(local)
            color_ram.append((mc1 << 4) | mc2)
            for y in range(8):
                byte = 0
                for xmc in range(4):
                    px = cx * 8 + xmc * 2
                    py = cy * 8 + y
                    if offset_x <= px < offset_x + scaled_w and offset_y <= py < offset_y + scaled_h:
                        sx = px - offset_x
                        sy = py - offset_y
                        color = scaled_data[sy][sx]
                    else:
                        color = bg
                    if color not in allowed:
                        if remap:
                            src_color = color
                            nearest = _nearest_allowed(color, allowed)
                            add_remap(src_color, nearest)
                            color = nearest
                        else:
                            clash_counts[(cx, cy)] = clash_counts.get((cx, cy), 0) + 1
                    if color == bg:
                        code = 0
                    elif color == mc1:
                        code = 1
                    elif color == mc2:
                        code = 2
                    else:
                        code = 3
                    byte |= (code & 0x03) << (6 - 2 * xmc)
                charset.append(byte)

    if clash_counts and not remap:
        raise ValueError(f"Too many colors in {len(clash_counts)} char(s). Enable auto-remap to continue.")

    return ConvertResult(
        charset=bytes(charset),
        screen_ram=screen_ram,
        color_ram=color_ram,
        bg=bg,
        mc1=mc1,
        mc2=mc2,
        remap_counts=remap_counts,
    )
