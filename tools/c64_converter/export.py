from __future__ import annotations

from typing import List

from PIL import Image

from .palette import PALETTE_RGB8

def render_preview(
    charset: bytes,
    screen_ram: List[int],
    color_ram: List[int],
    bg: int,
    mc1: int,
    mc2: int,
    mode: str,
    width: int,
    height: int,
    cell_modes: List[str] | None = None,
) -> Image.Image:
    cols = width // 8
    rows = height // 8
    img = Image.new("RGB", (width, height), tuple(int(v) for v in PALETTE_RGB8[bg]))

    for cy in range(rows):
        for cx in range(cols):
            idx = cy * cols + cx
            if idx >= len(screen_ram):
                continue
            char_index = screen_ram[idx]
            base = char_index * 8
            if base + 8 > len(charset):
                continue

            if cell_modes is not None:
                cell_mode = cell_modes[idx]
            else:
                cell_mode = mode

            if cell_mode == "hires":
                fg = color_ram[idx] & 0x0F if idx < len(color_ram) else 1
                fg_rgb = tuple(int(v) for v in PALETTE_RGB8[fg])
                bg_rgb = tuple(int(v) for v in PALETTE_RGB8[bg])
                for y in range(8):
                    bits = charset[base + y]
                    for x in range(8):
                        color = fg_rgb if (bits >> (7 - x)) & 1 else bg_rgb
                        img.putpixel((cx * 8 + x, cy * 8 + y), color)
            else:
                cell_color = color_ram[idx] & 0x07 if idx < len(color_ram) else 0
                colors = [
                    tuple(int(v) for v in PALETTE_RGB8[bg]),
                    tuple(int(v) for v in PALETTE_RGB8[mc1]),
                    tuple(int(v) for v in PALETTE_RGB8[mc2]),
                    tuple(int(v) for v in PALETTE_RGB8[cell_color]),
                ]
                for y in range(8):
                    codes = charset[base + y]
                    for xmc in range(4):
                        code = (codes >> (6 - 2 * xmc)) & 0x03
                        color = colors[code]
                        px = cx * 8 + xmc * 2
                        py = cy * 8 + y
                        img.putpixel((px, py), color)
                        img.putpixel((px + 1, py), color)

    return img
