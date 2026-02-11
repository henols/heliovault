from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ImageImportOptions:
    lock_bg: bool = False
    lock_mc1: bool = False
    lock_mc2: bool = False
    mixed_mode: bool = False
    dither: bool = False
    chroma_weight: float = 0.25
    dither_strength: float = 0.035

    def locks_dict(self, current: Dict[str, int]) -> Dict[str, Optional[int]]:
        return {
            "bg": current.get("bg") if self.lock_bg else None,
            "mc1": current.get("mc1") if self.lock_mc1 else None,
            "mc2": current.get("mc2") if self.lock_mc2 else None,
        }
