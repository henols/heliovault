#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

from c64_converter import convert_image
from c64_converter.export import render_preview


SAMPLES = [
    "images/level_lab_bg.png",
    "images/level_compliance_bg.png",
    "images/boot_audit.png",
]

TARGET_COLS = 40
TARGET_ROWS = 25
TARGET_W = TARGET_COLS * 8
TARGET_H = TARGET_ROWS * 8


def _placement_for(image: Image.Image):
    scale = min(TARGET_W / image.width, TARGET_H / image.height)
    scaled_w = max(1, int(image.width * scale))
    scaled_h = max(1, int(image.height * scale))
    return {
        "target_w": TARGET_W,
        "target_h": TARGET_H,
        "offset_x": (TARGET_W - scaled_w) // 2,
        "offset_y": (TARGET_H - scaled_h) // 2,
        "scaled_w": scaled_w,
        "scaled_h": scaled_h,
    }


def run_sample(path: str, output_dir: Path) -> None:
    image = Image.open(path).convert("RGB")
    placement = _placement_for(image)
    result = convert_image(
        image,
        mode="multicolor",
        strategy="auto",
        locks={"bg": None, "mc1": None, "mc2": None},
        remap=True,
        placement=placement,
        mixed_mode=True,
        dither=True,
    )

    hires_count = sum(1 for m in result.cell_modes if m == "hires")
    mc_count = len(result.cell_modes) - hires_count

    print(
        f"{path}: bg={result.bg} mc1={result.mc1} mc2={result.mc2} "
        f"unique={result.unique_chars} hires={hires_count} mc={mc_count} "
        f"error={result.error:.2f}"
    )

    preview = render_preview(
        result.charset,
        result.screen_ram,
        result.color_ram,
        result.bg,
        result.mc1,
        result.mc2,
        result.mode,
        TARGET_W,
        TARGET_H,
        cell_modes=result.cell_modes,
    )
    output_path = output_dir / (Path(path).stem + "_preview.png")
    preview.save(output_path)


if __name__ == "__main__":
    out_dir = Path("build")
    out_dir.mkdir(parents=True, exist_ok=True)
    for sample in SAMPLES:
        if not os.path.exists(sample):
            print(f"Skipping missing sample: {sample}")
            continue
        run_sample(sample, out_dir)
