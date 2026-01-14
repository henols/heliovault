#!/usr/bin/env python3
"""
watch_assets.py - Rebuild tileset and levels when inputs or outputs change.

Usage:
  python tools/watch_assets.py --levels levels --tset levels/tileset.tset
  python tools/watch_assets.py --once
  python tools/watch_assets.py /path/to/project
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from gen_paths import GEN_ROOT, ANALYSIS_ROOT

Observer = None
FileSystemEventHandler = None


def _extend_sys_path_for_watchdog(root: Path) -> None:
    candidates = []
    venv_lib = root / ".venv" / "lib"
    if venv_lib.exists():
        candidates.extend(venv_lib.glob("python*/site-packages"))
    pipx_lib = Path.home() / ".local" / "pipx" / "venvs" / "watchdog" / "lib"
    if pipx_lib.exists():
        candidates.extend(pipx_lib.glob("python*/site-packages"))
    for site in candidates:
        sys.path.append(str(site))


def _try_load_watchdog(root: Path) -> bool:
    global Observer, FileSystemEventHandler
    try:
        from watchdog.observers import Observer as _Observer
        from watchdog.events import FileSystemEventHandler as _Handler
        Observer = _Observer
        FileSystemEventHandler = _Handler
        return True
    except Exception:
        _extend_sys_path_for_watchdog(root)
        try:
            from watchdog.observers import Observer as _Observer
            from watchdog.events import FileSystemEventHandler as _Handler
            Observer = _Observer
            FileSystemEventHandler = _Handler
            return True
        except Exception:
            return False


def sanitize_level_name(name: str) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    base = base.strip("_").lower()
    return base if base else "level"


def parse_level_name(path: Path) -> str:
    try:
        for ln in path.read_text(encoding="utf-8").splitlines():
            s = ln.split(";", 1)[0].strip()
            if not s.startswith("LEVEL"):
                continue
            for part in s.split():
                if part.startswith("name="):
                    name = part.split("=", 1)[1].strip().strip('"')
                    return name
    except Exception:
        pass
    return path.stem


def file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def run(cmd: list[str]) -> bool:
    proc = subprocess.run(cmd)
    return proc.returncode == 0


def load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def should_run(input_path: Path, outputs: list[Path], cache: dict) -> bool:
    in_key = str(input_path)
    input_m = file_mtime(input_path)
    if input_m == 0.0:
        return False
    cached = cache.get(in_key, {})
    if cached.get("input_mtime") != input_m:
        return True
    for out in outputs:
        if file_mtime(out) == 0.0:
            return True
    cached_out = cached.get("outputs", {})
    for out in outputs:
        if cached_out.get(str(out)) != file_mtime(out):
            return True
    return False


def update_cache_entry(input_path: Path, outputs: list[Path], cache: dict) -> None:
    entry = {
        "input_mtime": file_mtime(input_path),
        "outputs": {str(out): file_mtime(out) for out in outputs},
    }
    cache[str(input_path)] = entry


def _tset_has_charset(path: Path) -> bool:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.split(";", 1)[0].strip()
            if not s.startswith("TSET"):
                continue
            return "charset=" in s
    except Exception:
        return False
    return False


def _tset_outputs_for(path: Path, root: Path) -> list[Path]:
    name = path.stem
    outputs = [
        root / GEN_ROOT / "assets" / f"{name}.bin",
        root / GEN_ROOT / "include" / f"{name}_tset_ids.h",
        root / GEN_ROOT / "include" / "tilesets" / f"{name}_tset-blob.h",
        root / GEN_ROOT / "src" / "tilesets" / f"{name}_tset.c",
        root / ANALYSIS_ROOT / "tilesets" / f"{name}.sym",
        root / ANALYSIS_ROOT / "tilesets" / f"{name}.json",
    ]
    if _tset_has_charset(path):
        outputs.extend(
            [
                root / GEN_ROOT / "include" / "tilesets" / f"{name}_charset-blob.h",
                root / GEN_ROOT / "src" / "tilesets" / f"{name}_charset.c",
            ]
        )
    return outputs


def run_once(
    root: Path,
    levels_dir: Path,
    tset_path: Path,
    tilesetc: Path,
    levelc: Path,
    cache_path: Path,
    changed_path: str | None = None,
) -> bool:
    ok = True
    cache = load_cache(cache_path)
    if not (changed_path and changed_path.endswith(".lvl")):
        for tset in sorted(tset_path.parent.glob("*.tset")):
            tset_outputs = _tset_outputs_for(tset, root)
            if should_run(tset, tset_outputs, cache):
                if run([sys.executable, str(tilesetc), str(tset), "-o", str(tset_outputs[0])]):
                    update_cache_entry(tset, tset_outputs, cache)
                else:
                    ok = False

    if changed_path and changed_path.endswith(".tset"):
        save_cache(cache_path, cache)
        return ok

    for lvl in sorted(levels_dir.glob("*.lvl")):
        if changed_path and changed_path.endswith(".lvl") and str(lvl) != changed_path:
            continue
        level_name = parse_level_name(lvl)
        base = sanitize_level_name(level_name)
        outputs = [
            root / GEN_ROOT / "assets" / "levels" / f"{base}.bin",
            root / GEN_ROOT / "include" / "levels" / f"{base}.h",
            root / GEN_ROOT / "include" / "levels" / f"{base}-blob.h",
            root / GEN_ROOT / "src" / "levels" / f"{base}.c",
            root / ANALYSIS_ROOT / "levels" / f"{base}.json",
            root / ANALYSIS_ROOT / "levels" / f"{base}.sym",
            root / GEN_ROOT / "include" / "level_format.h",
        ]
        if should_run(lvl, outputs, cache):
            if run([sys.executable, str(levelc), str(lvl)]):
                update_cache_entry(lvl, outputs, cache)
            else:
                ok = False

    save_cache(cache_path, cache)
    return ok


def run_tset_only(
    root: Path,
    tset_path: Path,
    tilesetc: Path,
    cache_path: Path,
    changed_path: str | None = None,
) -> bool:
    ok = True
    cache = load_cache(cache_path)
    if changed_path:
        tsets = [Path(changed_path)]
    else:
        tsets = sorted(tset_path.parent.glob("*.tset"))
    for tset in tsets:
        tset_outputs = _tset_outputs_for(tset, root)
        if should_run(tset, tset_outputs, cache):
            if run([sys.executable, str(tilesetc), str(tset), "-o", str(tset_outputs[0])]):
                update_cache_entry(tset, tset_outputs, cache)
            else:
                ok = False
    save_cache(cache_path, cache)
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".", help="Project root (default: .)")
    ap.add_argument("--levels", default="levels", help="Directory containing .lvl files")
    ap.add_argument("--tset", default="levels/tileset.tset", help="Tileset .tset")
    ap.add_argument("--interval", type=float, default=0.5, help="Polling interval in seconds")
    ap.add_argument("--once", action="store_true", help="Run a single pass and exit")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    levels_dir = (root / args.levels).resolve()
    tset_path = (root / args.tset).resolve()
    cache_path = root / "build" / ".asset_cache.json"

    if not levels_dir.is_dir():
        print(f"{levels_dir}:1:1: error: Levels dir not found", file=sys.stderr)
        sys.exit(1)
    if not tset_path.is_file():
        print(f"{tset_path}:1:1: error: Tileset not found", file=sys.stderr)
        sys.exit(1)

    tilesetc = root / "tools" / "tilesetc.py"
    levelc = root / "tools" / "levelc.py"

    if args.once:
        success = run_once(root, levels_dir, tset_path, tilesetc, levelc, cache_path)
        if not success:
            sys.exit(1)
        return

    if not _try_load_watchdog(root):
        print("watchdog not found. Install into the active interpreter, or use pipx path.", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print(f"  {sys.executable} -m pip install --user watchdog", file=sys.stderr)
        print("  or ensure pipx venv exists at ~/.local/pipx/venvs/watchdog", file=sys.stderr)
        sys.exit(1)

    def run_cycle():
        print("ASSETGEN START")
        run_once(root, levels_dir, tset_path, tilesetc, levelc, cache_path, changed_path=None)
        print("ASSETGEN END")

    class AssetsHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.is_directory:
                return
            if event.src_path.endswith(".lvl") or event.src_path.endswith(".tset"):
                print("ASSETGEN START")
                if event.src_path.endswith(".tset"):
                    run_tset_only(root, tset_path, tilesetc, cache_path, changed_path=event.src_path)
                else:
                    run_once(
                        root,
                        levels_dir,
                        tset_path,
                        tilesetc,
                        levelc,
                        cache_path,
                        changed_path=event.src_path,
                    )
                print("ASSETGEN END")

        def on_created(self, event):
            if event.is_directory:
                return
            if event.src_path.endswith(".lvl") or event.src_path.endswith(".tset"):
                print("ASSETGEN START")
                if event.src_path.endswith(".tset"):
                    run_tset_only(root, tset_path, tilesetc, cache_path, changed_path=event.src_path)
                else:
                    run_once(
                        root,
                        levels_dir,
                        tset_path,
                        tilesetc,
                        levelc,
                        cache_path,
                        changed_path=event.src_path,
                    )
                print("ASSETGEN END")

    observer = Observer()
    observer.schedule(AssetsHandler(), str(levels_dir), recursive=False)
    observer.schedule(AssetsHandler(), str(tset_path.parent), recursive=False)
    observer.start()

    run_cycle()

    try:
        while True:
            time.sleep(args.interval)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
