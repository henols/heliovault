from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .palette import rgb8_to_linear


@dataclass
class Placement:
    target_w: int
    target_h: int
    offset_x: int
    offset_y: int
    scaled_w: int
    scaled_h: int


def image_to_linear_array(image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    return rgb8_to_linear(rgb)


def _integral_image(src: np.ndarray) -> np.ndarray:
    # src shape: (H, W, 3)
    integral = np.cumsum(np.cumsum(src, axis=0), axis=1)
    # pad to simplify area sampling at edges
    return np.pad(integral, ((1, 0), (1, 0), (0, 0)), mode="constant")


def _integral_sample(integral: np.ndarray, x: float, y: float) -> np.ndarray:
    h = integral.shape[0] - 1
    w = integral.shape[1] - 1
    x = float(np.clip(x, 0.0, w))
    y = float(np.clip(y, 0.0, h))
    x0 = int(np.floor(x))
    y0 = int(np.floor(y))
    x1 = min(x0 + 1, w)
    y1 = min(y0 + 1, h)
    dx = x - x0
    dy = y - y0
    v00 = integral[y0, x0]
    v10 = integral[y0, x1]
    v01 = integral[y1, x0]
    v11 = integral[y1, x1]
    return (
        v00 * (1.0 - dx) * (1.0 - dy)
        + v10 * dx * (1.0 - dy)
        + v01 * (1.0 - dx) * dy
        + v11 * dx * dy
    )


def _integral_area(integral: np.ndarray, x0: float, x1: float, y0: float, y1: float) -> np.ndarray:
    return (
        _integral_sample(integral, x1, y1)
        - _integral_sample(integral, x0, y1)
        - _integral_sample(integral, x1, y0)
        + _integral_sample(integral, x0, y0)
    )


def _map_rect_to_source(
    tx0: float,
    tx1: float,
    ty0: float,
    ty1: float,
    src_w: int,
    src_h: int,
    placement: Optional[Placement],
) -> tuple[float, float, float, float] | None:
    px0 = placement.offset_x
    py0 = placement.offset_y
    px1 = placement.offset_x + placement.scaled_w
    py1 = placement.offset_y + placement.scaled_h

    if tx1 <= px0 or tx0 >= px1 or ty1 <= py0 or ty0 >= py1:
        return None

    cx0 = max(tx0, px0)
    cx1 = min(tx1, px1)
    cy0 = max(ty0, py0)
    cy1 = min(ty1, py1)

    scale_x = src_w / float(placement.scaled_w)
    scale_y = src_h / float(placement.scaled_h)

    sx0 = (cx0 - placement.offset_x) * scale_x
    sx1 = (cx1 - placement.offset_x) * scale_x
    sy0 = (cy0 - placement.offset_y) * scale_y
    sy1 = (cy1 - placement.offset_y) * scale_y

    return sx0, sx1, sy0, sy1


def sample_grid_linear(
    src_linear: np.ndarray,
    target_w: int,
    target_h: int,
    logical_w: int,
    logical_h: int,
    x_scale: int,
    placement: Optional[Placement] = None,
) -> np.ndarray:
    src_h, src_w, _ = src_linear.shape
    integral = _integral_image(src_linear)
    out = np.zeros((logical_h, logical_w, 3), dtype=np.float32)
    scale_x = src_w / float(target_w) if target_w > 0 else 1.0
    scale_y = src_h / float(target_h) if target_h > 0 else 1.0

    for y in range(logical_h):
        ty0 = float(y)
        ty1 = ty0 + 1.0
        for x in range(logical_w):
            tx0 = float(x * x_scale)
            tx1 = tx0 + float(x_scale)
            if placement is None:
                sx0 = tx0 * scale_x
                sx1 = tx1 * scale_x
                sy0 = ty0 * scale_y
                sy1 = ty1 * scale_y
            else:
                mapped = _map_rect_to_source(tx0, tx1, ty0, ty1, src_w, src_h, placement)
                if mapped is None:
                    continue
                sx0, sx1, sy0, sy1 = mapped
            area = (sx1 - sx0) * (sy1 - sy0)
            if area <= 0:
                continue
            sum_rgb = _integral_area(integral, sx0, sx1, sy0, sy1)
            out[y, x] = sum_rgb / area

    return out


def sample_cells_multicolor(
    src_linear: np.ndarray,
    cols: int,
    rows: int,
    placement: Optional[Placement] = None,
    target_w: Optional[int] = None,
    target_h: Optional[int] = None,
) -> np.ndarray:
    if target_w is None:
        target_w = cols * 8
    if target_h is None:
        target_h = rows * 8
    logical_w = cols * 4
    logical_h = rows * 8
    grid = sample_grid_linear(
        src_linear,
        target_w,
        target_h,
        logical_w,
        logical_h,
        x_scale=2,
        placement=placement,
    )
    grid = grid.reshape(rows, 8, cols, 4, 3)
    grid = grid.transpose(0, 2, 1, 3, 4)
    return grid.reshape(rows * cols, 8, 4, 3)


def sample_cells_hires(
    src_linear: np.ndarray,
    cols: int,
    rows: int,
    placement: Optional[Placement] = None,
    target_w: Optional[int] = None,
    target_h: Optional[int] = None,
) -> np.ndarray:
    if target_w is None:
        target_w = cols * 8
    if target_h is None:
        target_h = rows * 8
    logical_w = cols * 8
    logical_h = rows * 8
    grid = sample_grid_linear(
        src_linear,
        target_w,
        target_h,
        logical_w,
        logical_h,
        x_scale=1,
        placement=placement,
    )
    grid = grid.reshape(rows, 8, cols, 8, 3)
    grid = grid.transpose(0, 2, 1, 3, 4)
    return grid.reshape(rows * cols, 8, 8, 3)
