# Koala Tilekit Compiler

Builds a tileset, charset, and analysis artifacts from a C64 Koala image plus a JSON tile spec.

## Usage

```
python tools/koala_tilekit_compiler.py images/boot_audit.json
```

Optional overrides:

```
python tools/koala_tilekit_compiler.py images/boot_audit.json \
  --kla images/boot_audit.kla \
  --out-dir gen/analysis/boot_audit \
  --charset assets/boot_audit_chargen.bin \
  --tset levels/boot_audit.tset \
  --tmap gen/analysis/boot_audit/boot_audit_tmap.bin \
  --tile-map gen/analysis/boot_audit/boot_audit_tile_locations.png \
  --info gen/analysis/boot_audit/boot_audit_info.txt
```

## Inputs

- Koala Painter `.kla` image (320x200 multicolor). Files with a 2-byte load header are accepted.
- Spec `.json` file describing tiles and objects.

### Spec format

The spec contains `cells` for individual 16x16 tiles and `objects` for grouped tiles
(stamps). Coordinates are in tile units (16x16). Each cell or object provides a
sample position from the Koala image; those samples become the source tile art.

```json
{
  "cells": [
    {
      "x": 0,
      "y": 0,
      "w": 1,
      "h": 1,
      "flags": ["SOLID"],
      "description": "Standard reinforced wall panel"
    }
  ],
  "objects": [
    {
      "id": "O1",
      "type": "DOOR_GLASS",
      "x": 0,
      "y": 3,
      "w": 2,
      "h": 1,
      "flags": ["SOLID", "DECOR"],
      "description": "Glass partition"
    }
  ]
}
```

Field notes:
- `x`, `y`, `w`, `h` are in 16x16 tile units.
- `description` becomes the tile label; it is sanitized for `.tset` output.
- `flags` are normalized to upper-case `|` delimited values.
- Objects expand into per-tile entries with a generated role and `variant_of` metadata.

## Outputs (default paths)

- `assets/<name>_chargen.bin`
- `levels/<name>.tset`
- `gen/analysis/<name>/<name>_tmap.bin`
- `gen/analysis/<name>/<name>_tile_locations.png`
- `gen/analysis/<name>/<name>_info.txt`
- `gen/analysis/<name>/tiles.md`
- `gen/analysis/<name>/tiles/*.png`

## Notes

- The tool chooses BG/MC1/MC2 from the most common colors, then finds the best
  per-character local color.
- `--fast` uses a heuristic for MC1/MC2 selection and is much quicker on large
  specs.
- The `.tset` output includes a CHARMAP, TILES section, and optional OBJECTS
  section when multi-tile objects are defined.
- The full-image `tmap` is built by matching each 16x16 cell against the
  generated tile list using a nearest-tile heuristic.

## Related docs

- `docs/tools.md`
- `docs/tset_format.md`
