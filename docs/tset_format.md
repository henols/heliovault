# TSET File Format

This document describes the `.tset` text format consumed by `tools/tilesetc.py`.

## Basics

- Comments start with `;` and run to end of line.
- Sections are block-based and terminated by `END`.
- `FLAGBITS` is **not allowed**. Tile flags are fixed in code.
- Tile names must be uppercase with `_` only (no spaces/specials) when generated.
 - Prefer color names in uppercase (e.g., `BLACK`, `LIGHT_GREY`). Numeric values are also accepted.

## Top-Level Layout

```
TSET name="level_maint_bg" tileSize=2x2 bgColor=0 mc1Color=11 mc2Color=12 charset=assets/level_maint_bg_chargen.bin

CHARMAP
P PIPE_CEILING_CORE ; repeat horizontally ... [PIPE_CEILING_CLAMP]
END

TILES
PIPE_CEILING_CORE chars=0x00,0x01,0x02,0x03 colors=0,0,0,0 flags=DECOR
END

END
```

## TSET Header

Required keys:
- `name="..."` tileset name (used for outputs)
- `tileSize=2x2` currently only 2x2 is supported
- `bgColor=<0..15>` background color ($D021)
- `mc1Color=<0..15>` multicolor 1 ($D022)
- `mc2Color=<0..15>` multicolor 2 ($D023)

Optional keys:
- `charset=<path>` path to a compiled charset `.bin` used by this tileset
- `count=<int>` optional sanity check (must be >= number of tiles)

## CHARMAP

Maps a single character to a tile name for use in `.lvl` MAP sections.

```
CHARMAP
# WALL_FILL
. FLOOR
END
```

Notes:
- Keys are single characters.
- Tile names must exist in `TILES`.
 - If a CHARMAP entry points to an `OBJECTS` name, that character becomes an object stamp in `.lvl` MAPs.

Color values:
- Colors may be specified as numeric values (`0..15`, `$0F`, `0x0F`) or as color names.
- Color names are case-insensitive (e.g., `BLACK`, `black`, `Black` are all valid).

## OBJECTS (stamp macros)

Defines multi-tile objects that can be placed in `.lvl` MAP sections as a block of a single character.
The compiler replaces a rectangular block of that character with the object’s tile layout.

```
OBJECTS
  DOOR_GLASS size=2x1 tiles=DOOR_GLASS_L,DOOR_GLASS_R
  CRATE_STACK size=2x2 tiles=CRATE_TL,CRATE_TR,CRATE_BL,CRATE_BR
END
```

Rules:
- `size=` is `WxH` in tiles (supported sizes: 1x1, 1x2, 2x1, 2x2).
- `tiles=` is a row-major list of tile names matching the size.
- All tile names must exist in `TILES`.

Charmap binding:
- Use `CHARMAP` to bind a single character to an OBJECTS name for placement in `.lvl` maps.
 - Prefer `OBJECTS` only for multi-tile stamps. For 1x1, define a normal tile and map it in CHARMAP.

## TILES

Each line defines one metatile (2x2 chars).

```
TILES
WALL_FILL chars=0x10,0x11,0x12,0x13 colors=15,15,0,0 flags=SOLID
FLOOR     chars=F,F,F,F              color=lightblue flags=FLOOR|STANDABLE
END
```

Fields:
- `chars=` exactly 4 values (TL,TR,BL,BR). Each value can be hex (`0x..` or `$..`), decimal, or a single letter (`A`..`Z` -> 1..26).
- `colors=` 4 values (per quadrant) or `color=` for a single color.
- `flags=` pipe-separated list.

### Fixed Flag Bits

Flags are fixed and must be one of:

- `SOLID`
- `DECOR`
- `STANDABLE`
- `LADDER`
- `DOOR`
- `INTERACTABLE`
- `FLOOR`
- `HAZARD`

## Errors

`tilesetc.py` validates:
- missing `TSET` header or required keys
- missing/invalid `bgColor/mc1Color/mc2Color`
- invalid `CHARMAP` entries
- duplicate tile names/ids
- missing or invalid `chars/colors`
- unknown flags

## Outputs

Running:

```
python tools/tilesetc.py levels/level_maint_bg.tset -o gen/assets/level_maint_bg.bin
```

Generates:
- `gen/assets/<name>.bin`
- `gen/include/<name>_tset_ids.h`
- `gen/include/tilesets/<name>_tset-blob.h`
- `gen/src/tilesets/<name>_tset.c`
- `gen/include/tilesets/<name>_charset-blob.h` (if `charset=` set)
- `gen/src/tilesets/<name>_charset.c` (if `charset=` set)
- `gen/analysis/tilesets/<name>.sym`
- `gen/analysis/tilesets/<name>.json`
