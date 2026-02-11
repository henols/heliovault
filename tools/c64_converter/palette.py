from __future__ import annotations

import numpy as np

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

PALETTE_RGB8 = np.array([rgb for _name, rgb in C64_PALETTE], dtype=np.uint8)
PALETTE_RGB = PALETTE_RGB8.astype(np.float32) / 255.0


def srgb_to_linear(srgb: np.ndarray) -> np.ndarray:
    srgb = np.clip(srgb, 0.0, 1.0)
    cutoff = 0.04045
    below = srgb <= cutoff
    out = np.empty_like(srgb)
    out[below] = srgb[below] / 12.92
    out[~below] = ((srgb[~below] + 0.055) / 1.055) ** 2.4
    return out


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    linear = np.clip(linear, 0.0, 1.0)
    cutoff = 0.0031308
    below = linear <= cutoff
    out = np.empty_like(linear)
    out[below] = linear[below] * 12.92
    out[~below] = 1.055 * np.power(linear[~below], 1 / 2.4) - 0.055
    return out


def rgb8_to_linear(rgb8: np.ndarray) -> np.ndarray:
    return srgb_to_linear(rgb8.astype(np.float32) / 255.0)


def linear_to_rgb8(linear: np.ndarray) -> np.ndarray:
    srgb = linear_to_srgb(linear)
    return np.clip(np.round(srgb * 255.0), 0, 255).astype(np.uint8)


def linear_rgb_to_oklab(rgb_linear: np.ndarray) -> np.ndarray:
    r = rgb_linear[..., 0]
    g = rgb_linear[..., 1]
    b = rgb_linear[..., 2]

    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_ = np.cbrt(l)
    m_ = np.cbrt(m)
    s_ = np.cbrt(s)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    return np.stack([L, a, b], axis=-1)


def oklab_chroma(oklab: np.ndarray) -> np.ndarray:
    a = oklab[..., 1]
    b = oklab[..., 2]
    return np.sqrt(a * a + b * b)


PALETTE_OKLAB = linear_rgb_to_oklab(PALETTE_RGB)
PALETTE_CHROMA = oklab_chroma(PALETTE_OKLAB)
