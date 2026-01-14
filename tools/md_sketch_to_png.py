#!/usr/bin/env python3
"""
md_sketch_to_png.py
Render fenced code blocks from a markdown file into a single PNG image.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_code_blocks(text: str) -> list[list[str]]:
    blocks = []
    cur = None
    for raw in text.splitlines():
        if raw.strip().startswith("```"):
            if cur is None:
                cur = []
            else:
                blocks.append(cur)
                cur = None
            continue
        if cur is not None:
            cur.append(raw.rstrip("\n"))
    if cur is not None:
        blocks.append(cur)
    return [b for b in blocks if any(line.strip() for line in b)]


def _font_metrics(font: ImageFont.ImageFont) -> tuple[int, int]:
    box = font.getbbox("M")
    return box[2] - box[0], box[3] - box[1]


def render_blocks(blocks: list[list[str]], scale: int) -> Image.Image:
    font = ImageFont.load_default()
    ch_w, ch_h = _font_metrics(font)
    pad_x = 8
    pad_y = 8
    line_gap = 2
    block_gap = 8

    flat_lines = []
    for bi, block in enumerate(blocks):
        if bi != 0:
            flat_lines.append("")
            flat_lines.append("")
        flat_lines.extend(block)

    max_cols = max((len(line) for line in flat_lines), default=1)
    width = pad_x * 2 + max_cols * ch_w
    height = pad_y * 2 + len(flat_lines) * (ch_h + line_gap)

    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = pad_y
    for line in flat_lines:
        draw.text((pad_x, y), line, font=font, fill=(0, 0, 0))
        y += ch_h + line_gap

    if scale != 1:
        img = img.resize((width * scale, height * scale), resample=Image.NEAREST)
    return img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("md", help="Input markdown file")
    ap.add_argument("out", help="Output PNG path")
    ap.add_argument("--scale", type=int, default=2, help="Scale factor")
    args = ap.parse_args()

    md_path = Path(args.md)
    out_path = Path(args.out)
    text = md_path.read_text(encoding="utf-8")
    blocks = _load_code_blocks(text)
    if not blocks:
        raise SystemExit(f"No fenced code blocks found in {md_path}")
    img = render_blocks(blocks, max(1, args.scale))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
