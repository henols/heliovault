#!/usr/bin/env python3
"""
gen_build.py
Expand project-config.json sources so VS64 can build directory/glob entries.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def is_glob(s: str) -> bool:
    return any(ch in s for ch in ["*", "?", "["])


def expand_source(root: Path, entry: str) -> list[str]:
    path = Path(entry)
    if not path.is_absolute():
        path = root / path

    if is_glob(entry):
        return sorted(str(p.relative_to(root)) for p in path.parent.glob(path.name) if p.is_file())

    if entry.endswith("/") or path.is_dir():
        return sorted(
            str(p.relative_to(root))
            for p in path.glob("*.c")
            if p.is_file()
        )

    if path.exists():
        return [str(path.relative_to(root))]

    return [entry]


def expand_sources(root: Path, sources: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for entry in sources:
        for item in expand_source(root, entry):
            if item not in seen:
                out.append(item)
                seen.add(item)
    return out


def patch_build_ninja(root: Path, sources: list[str]) -> None:
    ninja_path = root / "build" / "build.ninja"
    if not ninja_path.is_file():
        return
    abs_sources = [str((root / s).resolve()) for s in sources]
    new_line = "build $target | $dbg_out : cc " + " ".join(abs_sources) + "\n"
    lines = ninja_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("build $target | $dbg_out : cc "):
            lines[i] = new_line
            updated = True
            break
    if updated:
        ninja_path.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="project-config.template.json", help="Path to project config template")
    ap.add_argument("--out", default="project-config.json", help="Output config path")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    config_path = (root / args.config).resolve()
    out_path = (root / args.out).resolve()

    if not config_path.is_file():
        print(f"Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = config.get("sources", [])
    if not isinstance(sources, list):
        print("Config 'sources' must be a list.", file=sys.stderr)
        sys.exit(1)

    config["sources"] = expand_sources(root, sources)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(config, indent=4) + "\n", encoding="utf-8")
    patch_build_ninja(root, config["sources"])


if __name__ == "__main__":
    main()
