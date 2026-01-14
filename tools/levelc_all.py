#!/usr/bin/env python3
"""
levelc_all.py - Compile all .lvl files and emit a depfile + stamp.

Usage:
  python tools/levelc_all.py --levels levels --stamp debug/levels/levels.stamp --depfile debug/levels/levels.d
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default="levels", help="Directory containing .lvl files")
    ap.add_argument("--stamp", required=True, help="Stamp file path")
    ap.add_argument("--depfile", required=True, help="Depfile path")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    levels_dir = (root / args.levels).resolve()
    if not levels_dir.is_dir():
        print(f"Levels dir not found: {levels_dir}", file=sys.stderr)
        sys.exit(1)

    levelc = root / "tools" / "levelc.py"
    lvl_files = sorted(levels_dir.glob("*.lvl"))
    if not lvl_files:
        print(f"No .lvl files found in {levels_dir}", file=sys.stderr)
        sys.exit(1)

    for lvl in lvl_files:
        run([sys.executable, str(levelc), str(lvl)])

    stamp_path = Path(args.stamp)
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text("ok\n", encoding="utf-8")

    dep_path = Path(args.depfile)
    dep_path.parent.mkdir(parents=True, exist_ok=True)
    deps = " ".join(str(p) for p in lvl_files)
    dep_path.write_text(f"{stamp_path}: {deps}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
