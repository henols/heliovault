#!/usr/bin/env python3
"""
build_assets.py - Build tileset + all levels in one pass.

Usage:
  python tools/build_assets.py
  python tools/build_assets.py --tset levels/tileset.tset
  python tools/build_assets.py --levels levels
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from gen_paths import GEN_ROOT


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        sys.exit(proc.returncode)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tset", default="levels/tileset.tset", help="Path to tileset .tset")
    ap.add_argument("--levels", default="levels", help="Directory containing .lvl files")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    gen_root = root / GEN_ROOT
    tset_path = (root / args.tset).resolve()
    levels_dir = (root / args.levels).resolve()

    if not tset_path.is_file():
        candidates = sorted((root / "levels").glob("*.tset"))
        if len(candidates) == 1:
            tset_path = candidates[0].resolve()
        else:
            print(f"Tileset not found: {tset_path}", file=sys.stderr)
            if candidates:
                names = ", ".join(p.name for p in candidates)
                print(f"Available .tset files: {names}", file=sys.stderr)
            print("Pass --tset with the desired tileset path.", file=sys.stderr)
            sys.exit(1)
    if not levels_dir.is_dir():
        print(f"Levels dir not found: {levels_dir}", file=sys.stderr)
        sys.exit(1)

    tilesetc = root / "tools" / "tilesetc.py"
    levelc = root / "tools" / "levelc.py"
    gen_build = root / "tools" / "gen_build.py"

    # Build tileset blob + ids header
    run([sys.executable, str(tilesetc), str(tset_path)])

    # Build all levels
    lvl_files = sorted(levels_dir.glob("*.lvl"))
    if not lvl_files:
        print(f"No .lvl files found in {levels_dir}", file=sys.stderr)
        sys.exit(1)
    for lvl in lvl_files:
        run([sys.executable, str(levelc), str(lvl)])

    # Refresh project-config.json and build/build.ninja now that gen/ outputs exist.
    run([sys.executable, str(gen_build)])


if __name__ == "__main__":
    main()
