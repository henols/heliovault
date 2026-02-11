from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from .palette import (
    PALETTE_OKLAB,
    PALETTE_CHROMA,
    linear_rgb_to_oklab,
    oklab_chroma,
)
from .scaling import Placement, image_to_linear_array, sample_cells_hires, sample_cells_multicolor
from .charset import (
    dedupe_patterns,
    pack_hires_bits,
    pack_multicolor_codes,
)


@dataclass
class ConvertResult:
    charset: bytes
    screen_ram: List[int]
    color_ram: List[int]
    bg: int
    mc1: int
    mc2: int
    remap_counts: Dict[Tuple[int, int], int]
    mode: str
    cell_modes: List[str]
    unique_chars: int
    error: float


def _ordered_dither_l(oklab: np.ndarray, width: int, height: int, strength: float) -> np.ndarray:
    # Apply a 4x4 Bayer dither on L channel (stable across cells)
    bayer = np.array(
        [
            [0, 8, 2, 10],
            [12, 4, 14, 6],
            [3, 11, 1, 9],
            [15, 7, 13, 5],
        ],
        dtype=np.float32,
    )
    bayer = (bayer + 0.5) / 16.0 - 0.5
    tiled = np.tile(bayer, (height // 4 + 1, width // 4 + 1))
    tiled = tiled[:height, :width]
    dither = tiled * strength
    oklab = oklab.copy()
    oklab[..., 0] = np.clip(oklab[..., 0] + dither, 0.0, 1.0)
    return oklab


def _compute_distances(
    samples_linear: np.ndarray,
    chroma_weight: float,
    dither: bool = False,
    logical_w: Optional[int] = None,
    logical_h: Optional[int] = None,
    dither_strength: float = 0.035,
) -> Tuple[np.ndarray, np.ndarray]:
    # samples_linear: (cells, h, w, 3)
    cells, h, w, _ = samples_linear.shape
    flat = samples_linear.reshape(cells * h * w, 3)
    oklab = linear_rgb_to_oklab(flat)

    if dither and logical_w is not None and logical_h is not None:
        oklab_grid = oklab.reshape(logical_h, logical_w, 3)
        oklab_grid = _ordered_dither_l(oklab_grid, logical_w, logical_h, dither_strength)
        oklab = oklab_grid.reshape(cells * h * w, 3)

    chroma_src = oklab_chroma(oklab)
    diff = oklab[:, None, :] - PALETTE_OKLAB[None, :, :]
    dist = np.sum(diff * diff, axis=2)

    if chroma_weight > 0:
        chroma_pen = np.maximum(0.0, chroma_src[:, None] - PALETTE_CHROMA[None, :])
        dist = dist + chroma_weight * (chroma_pen * chroma_pen)

    return dist.reshape(cells, h * w, 16), oklab


def _select_globals(
    dist: np.ndarray,
    locks: Dict[str, Optional[int]],
) -> Tuple[int, int, int, float]:
    # dist shape: (cells, pixels, 16)
    cells = dist.shape[0]
    bg_candidates = [locks["bg"]] if locks.get("bg") is not None else list(range(16))
    mc1_candidates = [locks["mc1"]] if locks.get("mc1") is not None else list(range(16))
    mc2_candidates = [locks["mc2"]] if locks.get("mc2") is not None else list(range(16))

    best = (0, 1, 2)
    best_error = float("inf")

    for bg in bg_candidates:
        for mc1 in mc1_candidates:
            for mc2 in mc2_candidates:
                # Avoid duplicates in auto selection, but honor explicit locks.
                if locks.get("mc1") is None and mc1 == bg:
                    continue
                if locks.get("mc2") is None and mc2 in (bg, mc1):
                    continue

                d_bg = dist[:, :, bg]
                d_mc1 = dist[:, :, mc1]
                d_mc2 = dist[:, :, mc2]
                d_base = np.minimum(d_bg, np.minimum(d_mc1, d_mc2))

                best_cell = np.full((cells,), np.inf, dtype=np.float32)
                for c in range(8):
                    d = np.minimum(d_base, dist[:, :, c])
                    cost = d.sum(axis=1)
                    best_cell = np.minimum(best_cell, cost)

                total = float(best_cell.sum())
                if total < best_error:
                    best_error = total
                    best = (bg, mc1, mc2)

    return best[0], best[1], best[2], best_error


def _solve_multicolor(
    dist: np.ndarray,
    bg: int,
    mc1: int,
    mc2: int,
    rows: int,
    cols: int,
) -> Tuple[List[bytes], List[int], np.ndarray]:
    cells = dist.shape[0]
    d_base = np.minimum(dist[:, :, bg], np.minimum(dist[:, :, mc1], dist[:, :, mc2]))

    best_color = np.zeros((cells,), dtype=np.int32)
    best_error = np.full((cells,), np.inf, dtype=np.float32)

    for c in range(8):
        d = np.minimum(d_base, dist[:, :, c])
        cost = d.sum(axis=1)
        better = cost < best_error
        best_error[better] = cost[better]
        best_color[better] = c

    patterns: List[bytes] = []
    for idx in range(cells):
        c = int(best_color[idx])
        d_candidates = np.stack(
            [dist[idx, :, bg], dist[idx, :, mc1], dist[idx, :, mc2], dist[idx, :, c]],
            axis=1,
        )
        codes = np.argmin(d_candidates, axis=1).astype(np.uint8)
        codes = codes.reshape(8, 4)
        patterns.append(pack_multicolor_codes(codes))

    return patterns, best_color.tolist(), best_error


def _solve_hires(
    dist: np.ndarray,
    bg: int,
) -> Tuple[List[bytes], List[int], np.ndarray]:
    cells = dist.shape[0]
    d_bg = dist[:, :, bg]
    best_fg = np.zeros((cells,), dtype=np.int32)
    best_error = np.full((cells,), np.inf, dtype=np.float32)

    for fg in range(16):
        d = np.minimum(d_bg, dist[:, :, fg])
        cost = d.sum(axis=1)
        better = cost < best_error
        best_error[better] = cost[better]
        best_fg[better] = fg

    patterns: List[bytes] = []
    for idx in range(cells):
        fg = int(best_fg[idx])
        d_candidates = np.stack([d_bg[idx], dist[idx, :, fg]], axis=1)
        bits = (np.argmin(d_candidates, axis=1) == 1).astype(np.uint8)
        bits = bits.reshape(8, 8)
        patterns.append(pack_hires_bits(bits))

    return patterns, best_fg.tolist(), best_error


def convert_image(
    image,
    mode: str,
    strategy: str,
    locks: Dict[str, Optional[int]],
    remap: bool = True,
    placement: Optional[Dict[str, int]] = None,
    mixed_mode: bool = False,
    dither: bool = False,
    chroma_weight: float = 0.25,
    dither_strength: float = 0.035,
) -> ConvertResult:
    # mode: "multicolor" or "hires" (mixed_mode only applies to multicolor)
    if mode not in ("multicolor", "hires"):
        raise ValueError(f"Unsupported mode: {mode}")

    src_linear = image_to_linear_array(image)

    if placement:
        placement_obj = Placement(**placement)
        target_w = placement_obj.target_w
        target_h = placement_obj.target_h
    else:
        placement_obj = None
        target_w, target_h = image.size

    cols = max(1, target_w // 8)
    rows = max(1, target_h // 8)

    # Sample for multicolor grid (4x8 logical pixels per cell)
    samples_mc = sample_cells_multicolor(
        src_linear,
        cols,
        rows,
        placement=placement_obj,
        target_w=target_w,
        target_h=target_h,
    )

    logical_w_mc = cols * 4
    logical_h_mc = rows * 8
    dist_mc, _ = _compute_distances(
        samples_mc,
        chroma_weight=chroma_weight,
        dither=dither,
        logical_w=logical_w_mc,
        logical_h=logical_h_mc,
        dither_strength=dither_strength,
    )

    # Locks use current colors; strategy retained for compatibility
    locks = dict(locks or {})

    bg, mc1, mc2, _ = _select_globals(dist_mc, locks)

    if mode == "hires":
        samples_hi = sample_cells_hires(
            src_linear,
            cols,
            rows,
            placement=placement_obj,
            target_w=target_w,
            target_h=target_h,
        )
        logical_w_hi = cols * 8
        logical_h_hi = rows * 8
        dist_hi, _ = _compute_distances(
            samples_hi,
            chroma_weight=chroma_weight,
            dither=dither,
            logical_w=logical_w_hi,
            logical_h=logical_h_hi,
            dither_strength=dither_strength,
        )
        patterns, colors, errors = _solve_hires(dist_hi, bg)
        cell_modes = ["hires"] * (rows * cols)
        screen_ram, color_ram, charset_bytes, unique_count = dedupe_patterns(
            patterns,
            colors,
            cell_modes,
            dist_hi,
            None,
            bg,
            mc1,
            mc2,
        )
        return ConvertResult(
            charset=charset_bytes,
            screen_ram=screen_ram,
            color_ram=color_ram,
            bg=bg,
            mc1=mc1,
            mc2=mc2,
            remap_counts={},
            mode="hires",
            cell_modes=cell_modes,
            unique_chars=unique_count,
            error=float(errors.sum()),
        )

    patterns_mc, colors_mc, errors_mc = _solve_multicolor(dist_mc, bg, mc1, mc2, rows, cols)

    if mixed_mode:
        samples_hi = sample_cells_hires(
            src_linear,
            cols,
            rows,
            placement=placement_obj,
            target_w=target_w,
            target_h=target_h,
        )
        logical_w_hi = cols * 8
        logical_h_hi = rows * 8
        dist_hi, _ = _compute_distances(
            samples_hi,
            chroma_weight=chroma_weight,
            dither=dither,
            logical_w=logical_w_hi,
            logical_h=logical_h_hi,
            dither_strength=dither_strength,
        )
        patterns_hi, colors_hi, errors_hi = _solve_hires(dist_hi, bg)

        use_hires = errors_hi < errors_mc
        patterns = []
        colors = []
        cell_modes = []
        for idx in range(rows * cols):
            if use_hires[idx]:
                patterns.append(patterns_hi[idx])
                colors.append(colors_hi[idx])
                cell_modes.append("hires")
            else:
                patterns.append(patterns_mc[idx])
                colors.append(colors_mc[idx])
                cell_modes.append("multicolor")
        errors = np.where(use_hires, errors_hi, errors_mc)
        screen_ram, color_ram, charset_bytes, unique_count = dedupe_patterns(
            patterns,
            colors,
            cell_modes,
            dist_mc,
            dist_hi,
            bg,
            mc1,
            mc2,
        )
        return ConvertResult(
            charset=charset_bytes,
            screen_ram=screen_ram,
            color_ram=color_ram,
            bg=bg,
            mc1=mc1,
            mc2=mc2,
            remap_counts={},
            mode="multicolor",
            cell_modes=cell_modes,
            unique_chars=unique_count,
            error=float(errors.sum()),
        )

    cell_modes = ["multicolor"] * (rows * cols)
    screen_ram, color_ram, charset_bytes, unique_count = dedupe_patterns(
        patterns_mc,
        colors_mc,
        cell_modes,
        dist_mc,
        None,
        bg,
        mc1,
        mc2,
    )

    return ConvertResult(
        charset=charset_bytes,
        screen_ram=screen_ram,
        color_ram=color_ram,
        bg=bg,
        mc1=mc1,
        mc2=mc2,
        remap_counts={},
        mode="multicolor",
        cell_modes=cell_modes,
        unique_chars=unique_count,
        error=float(errors_mc.sum()),
    )
