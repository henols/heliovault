# Tools Guide

This document lists the project tools, what they do, and how to run them.

---

## build_assets.py

Builds a tileset and all levels in one pass.

Usage:
```
python tools/build_assets.py
python tools/build_assets.py --tset levels/BOOT_AUDIT1.tset
python tools/build_assets.py --levels levels
```

Inputs:
- One `.tset` file (default `levels/tileset.tset`).
- All `.lvl` files in the levels directory (default `levels/`).

Notes:
- If the default tileset path is missing and exactly one `.tset` exists in `levels/`, that file is used automatically.

Outputs:
- Tileset blob + headers via `tools/tilesetc.py`.
- Level blobs + headers via `tools/levelc.py`.

Notes:
- This does not compile the game binary. It only generates assets.
- It also refreshes `project-config.json` after generation so the build picks up new `gen/src` files.

---

## gen_build.py

Expands `project-config.json` sources so VS64 can build directory/glob entries.

Usage:
```
python tools/gen_build.py
```

Inputs:
- `project-config.json`

Outputs:
- `project-config.json` with expanded `sources` (generated from `project-config.template.json`).

Notes:
- Use this before VS64 build/rebuild so `src/tilesets/` is expanded into the actual generated `.c` files.

---

## tilesetc.py

Compiles a `.tset` tileset into a binary blob and C headers.

Usage:
```
python tools/tilesetc.py levels/BOOT_AUDIT1.tset -o assets/BOOT_AUDIT1.bin
```

Outputs:
- `gen/assets/<name>.bin`
- `gen/include/<name>_tset_ids.h`
- `gen/include/tilesets/<name>_tset-blob.h`
- `gen/src/tilesets/<name>_tset.c`
- `gen/include/tilesets/<name>_charset-blob.h` (when `charset=` is set)
- `gen/src/tilesets/<name>_charset.c` (when `charset=` is set)
- `gen/analysis/tilesets/<name>.sym`
- `gen/analysis/tilesets/<name>.json`

See `docs/tset_format.md` for format details.

---

## levelc.py

Compiles a `.lvl` level into a binary blob and C headers.

Usage:
```
python tools/levelc.py levels/boot_audit.lvl
```

Outputs:
- `gen/assets/levels/<level>.bin`
- `gen/src/levels/<level>.c`
- `gen/include/levels/<level>.h`
- `gen/include/levels/<level>-blob.h`
- `gen/include/level_format.h`
- `gen/analysis/levels/<level>.sym`
- `gen/analysis/levels/<level>.json`

See `docs/levelc.md` and `docs/lvl_format.md` for format details.

---

## levelc_all.py

Compiles all `.lvl` files and emits a depfile + stamp for build systems.

Usage:
```
python tools/levelc_all.py --levels levels \
  --stamp debug/levels/levels.stamp \
  --depfile debug/levels/levels.d
```

Outputs:
- All level outputs from `levelc.py`
- A stamp file (`--stamp`)
- A depfile listing all `.lvl` inputs (`--depfile`)

---

## koala_tilekit_compiler.py

Builds a tileset + charset from a Koala image and a spec file.

Usage:
```
python tools/koala_tilekit_compiler.py images/BOOT_AUDIT1.md
```

Inputs:
- A `.kla` Koala image (same basename as the spec, unless `--kla` is set).
- A spec `.md` or `.json` file.

Outputs (defaults, per spec name):
- `assets/<name>_chargen.bin`
- `levels/<name>.tset`
- `gen/analysis/<name>/<name>_tmap.bin`
- `gen/analysis/<name>/<name>_tile_locations.png`
- `gen/analysis/<name>/<name>_info.txt`
- `gen/analysis/<name>/tiles.md`

Notes:
- The spec drives tile names, flags, and object stamps.
- Use `--fast` to speed up MC color selection.

---

## md_sketch_to_png.py

Renders fenced code blocks from a markdown file into a single PNG.

Usage:
```
python tools/md_sketch_to_png.py docs/level_art_prompt.txt debug/level_art_prompt.png --scale 2
```

Inputs:
- Markdown file with fenced code blocks.

Outputs:
- One PNG rendering of the combined blocks.

---

## watch_assets.py

Watches `.tset` and `.lvl` files and rebuilds outputs when they change.

Usage:
```
python tools/watch_assets.py --levels levels --tset levels/tileset.tset
python tools/watch_assets.py --once
python tools/watch_assets.py /path/to/project
```

Behavior:
- Rebuilds tilesets with `tools/tilesetc.py` when `.tset` changes.
- Rebuilds levels with `tools/levelc.py` when `.lvl` changes.
- Tracks output mtimes to avoid unnecessary work.

Outputs:
- Same outputs as `tilesetc.py` and `levelc.py`.
- Cache file at `build/.asset_cache.json`.

---

## tset_parser.py (internal)

Shared parser for `.tset` used by `tilesetc.py` and `levelc.py`.
Not meant to be invoked directly.

---

## Common workflows

### Update tileset or charmap

1) Regenerate tileset assets (and optional charset):
```
python tools/tilesetc.py levels/BOOT_AUDIT1.tset -o gen/assets/BOOT_AUDIT1.bin
```

2) Rebuild levels that reference the tileset:
```
python tools/levelc.py levels/boot_audit.lvl
```

3) Expand sources for VS64 (so new tileset C files are linked):
```
python tools/gen_build.py --in-place
```

4) Build the PRG (VS64 rebuild or your CLI build command).

---

### Update level content

1) Compile the level:
```
python tools/levelc.py levels/boot_audit.lvl
```

2) Build the PRG.

---

### Rebuild everything (assets + levels)

```
python tools/build_assets.py --tset levels/BOOT_AUDIT1.tset --levels levels
python tools/gen_build.py --in-place
```

Then build the PRG.
