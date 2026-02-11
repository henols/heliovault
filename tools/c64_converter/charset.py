from __future__ import annotations

from collections import Counter
from typing import List, Tuple

import numpy as np


def pack_multicolor_codes(codes: np.ndarray) -> bytes:
    # codes shape (8, 4) with 2-bit values
    out = bytearray(8)
    for y in range(8):
        byte = 0
        for x in range(4):
            code = int(codes[y, x]) & 0x03
            byte |= code << (6 - 2 * x)
        out[y] = byte
    return bytes(out)


def unpack_multicolor_bytes(pattern: bytes) -> np.ndarray:
    codes = np.zeros((8, 4), dtype=np.uint8)
    for y in range(8):
        b = pattern[y]
        for x in range(4):
            codes[y, x] = (b >> (6 - 2 * x)) & 0x03
    return codes


def pack_hires_bits(bits: np.ndarray) -> bytes:
    out = bytearray(8)
    for y in range(8):
        byte = 0
        for x in range(8):
            if bits[y, x]:
                byte |= 1 << (7 - x)
        out[y] = byte
    return bytes(out)


def unpack_hires_bytes(pattern: bytes) -> np.ndarray:
    bits = np.zeros((8, 8), dtype=np.uint8)
    for y in range(8):
        b = pattern[y]
        for x in range(8):
            bits[y, x] = (b >> (7 - x)) & 1
    return bits


def _pattern_error_multicolor(
    dist: np.ndarray,
    pattern: bytes,
    bg: int,
    mc1: int,
    mc2: int,
) -> Tuple[float, int]:
    # dist shape: (32, 16)
    codes = unpack_multicolor_bytes(pattern).reshape(-1)
    idx0 = codes == 0
    idx1 = codes == 1
    idx2 = codes == 2
    idx3 = codes == 3

    err = 0.0
    if idx0.any():
        err += float(dist[idx0, bg].sum())
    if idx1.any():
        err += float(dist[idx1, mc1].sum())
    if idx2.any():
        err += float(dist[idx2, mc2].sum())

    if not idx3.any():
        return err, 0

    best = float("inf")
    best_c = 0
    for c in range(8):
        cost = float(dist[idx3, c].sum())
        if cost < best:
            best = cost
            best_c = c
    return err + best, best_c


def _pattern_error_hires(dist: np.ndarray, pattern: bytes, bg: int) -> Tuple[float, int]:
    # dist shape: (64, 16)
    bits = unpack_hires_bytes(pattern).reshape(-1)
    idx1 = bits == 1
    idx0 = ~idx1

    base = float(dist[idx0, bg].sum()) if idx0.any() else 0.0

    best = float("inf")
    best_fg = 0
    for fg in range(16):
        cost = base
        if idx1.any():
            cost += float(dist[idx1, fg].sum())
        if cost < best:
            best = cost
            best_fg = fg
    return best, best_fg


def dedupe_patterns(
    patterns: List[bytes],
    cell_colors: List[int],
    cell_modes: List[str],
    dist_mc: np.ndarray | None,
    dist_hi: np.ndarray | None,
    bg: int,
    mc1: int,
    mc2: int,
    max_chars: int = 256,
) -> Tuple[List[int], List[int], bytes, int]:
    # Preserve first-seen order for stable indices
    first_seen = []
    seen = set()
    for pat in patterns:
        if pat not in seen:
            seen.add(pat)
            first_seen.append(pat)

    counts = Counter(patterns)
    if len(counts) > max_chars:
        # Keep most frequent patterns, tie-break by first seen order
        ordered = sorted(counts.items(), key=lambda item: (-item[1], first_seen.index(item[0])))
        keep = [pat for pat, _ in ordered[:max_chars]]
        keep_set = set(keep)

        for idx, pat in enumerate(patterns):
            if pat in keep_set:
                continue
            mode = cell_modes[idx]
            best_pat = None
            best_err = float("inf")
            best_color = cell_colors[idx]
            for candidate in keep:
                if mode == "hires":
                    if dist_hi is None:
                        continue
                    err, fg = _pattern_error_hires(dist_hi[idx], candidate, bg)
                    if err < best_err:
                        best_err = err
                        best_pat = candidate
                        best_color = fg
                else:
                    if dist_mc is None:
                        continue
                    err, c = _pattern_error_multicolor(dist_mc[idx], candidate, bg, mc1, mc2)
                    if err < best_err:
                        best_err = err
                        best_pat = candidate
                        best_color = c
            if best_pat is not None:
                patterns[idx] = best_pat
                cell_colors[idx] = best_color

        counts = Counter(patterns)
        first_seen = []
        seen = set()
        for pat in patterns:
            if pat not in seen:
                seen.add(pat)
                first_seen.append(pat)

    # Assign indices based on first appearance
    pattern_to_index = {pat: idx for idx, pat in enumerate(first_seen)}
    charset_bytes = b"".join(first_seen)

    screen_ram = [pattern_to_index[pat] for pat in patterns]

    color_ram = []
    for idx, color in enumerate(cell_colors):
        if cell_modes[idx] == "multicolor":
            color_ram.append(int(color) | 0x08)
        else:
            color_ram.append(int(color) & 0x0F)

    return screen_ram, color_ram, charset_bytes, len(first_seen)
