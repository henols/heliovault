# LVL File Format

This document describes the `.lvl` text format consumed by `tools/levelc.py`.

## Basics

- Comments start with `;` and run to end of line.
- Sections are block-based and terminated by `END` (or `ENDROOM` for rooms).
- Keywords are uppercase in examples, but parsing is case-sensitive for IDs.
- Map characters must be mapped to tile IDs via `TILES` or a `tset` CHARMAP.

## Top-Level Layout (Order Matters)

```
LEVEL name="BOOT AUDIT" w=20 h=12 start=R0:S0 tset=level_maint_bg.tset

TILES
  . FLOOR
  # WALL
END

FLAGS
  LOCKER_OPEN
  POWER_ON
END

VARS
  RELAY_BITS
END

ITEMS
  FUSE
  BADGE
END

MESSAGES
  PANEL_OK = "PANEL: OK"
  PANEL_NO = "NO POWER"
END

COND ALWAYS
  TRUE
END

ACT OPEN_DOOR
  SETFLAG POWER_ON
  MSG PANEL_OK
END

ROOM R0 name="Vestibule"
SPAWNS
  S0 2,7
END
EXITS
  R R1:S0
END
OBJECTS
  O1 at 3,2 type=SIGN verbs=LOOK look=OPEN_DOOR cond=ALWAYS
END
MAP
####################
#.................#
#.................#
#.................#
#.................#
#.................#
#.................#
#.................#
#.................#
#.................#
#.................#
####################
END
ENDROOM
```

### LEVEL header

Required keys:
- `name="..."` (string)
- `w=<int>` width in tiles
- `h=<int>` height in tiles
- `start=R?:S?` start room id and spawn id

Optional keys:
- `tset=<path>` path to a `.tset` file. If the tset defines `CHARMAP`, the `TILES` section can be omitted.

### TILES (optional with tset CHARMAP)

Maps single characters used in the MAP to tile IDs or tile names.

```
TILES
  . FLOOR
  # 3
END
```

If `tset=...` is provided, the right-hand side may be a tile name from the tset.
If no `TILES` section is provided and the tset has a `CHARMAP`, that mapping is used.
If both are provided, `TILES` entries override the `tset` CHARMAP for matching characters.

### FLAGS / VARS / ITEMS

Define named indices used in conditions and actions. Each line is a single name.

```
FLAGS
  POWER_ON
END
```

### MESSAGES

String table for dialogue and UI text.

```
MESSAGES
  PANEL_OK = "PANEL: OK"
END
```

### COND (conditions)

Conditions are AND-only bytecode. Each line is a command.

Supported condition ops:
- `TRUE`
- `FLAGSET <FLAG>`
- `FLAGCLR <FLAG>`
- `HAS <ITEM>`
- `VAREQ <VAR> <value>`

### ACT (actions)

Actions are linear bytecode. Each line is a command.

Supported action ops:
- `MSG <MESSAGE>`
- `SETFLAG <FLAG>`
- `CLRFLAG <FLAG>`
- `GIVE <ITEM>`
- `TAKE <ITEM>`
- `SETVAR <VAR> <value>`
- `SFX <int>`
- `TRANSITION <ROOM> <SPAWN>`

## Rooms

Each room is a block:

```
ROOM R0 name="Vestibule"
SPAWNS
  S0 2,7
END
EXITS
  R R1:S0
END
OBJECTS
  O1 at 3,2 type=SIGN verbs=LOOK look=SHOW_MANIFEST cond=ALWAYS
END
MAP
####################
#.................#
... (h rows total) ...
END
ENDROOM
```

### SPAWNS

```
SPAWNS
  S0 2,7
  S1 18,7
END
```

### EXITS

```
EXITS
  L R2:S0
  R R1:S0
  U R3:S0
  D R4:S1
END
```

Edges are `L`, `R`, `U`, `D`. Destination is `RoomId:SpawnId`.

### OBJECTS

```
OBJECTS
  O1 at 3,2 type=LOCKER_KEYPAD verbs=LOOK|OPERATE code=729 ok=LOCKER_OK bad=LOCKER_BAD cond=ALWAYS
  O2 at 10,6 type=BREAKER_PANEL verbs=OPERATE var=RELAY_BITS expect=0b101 ok=RELAYS_OK bad=RELAYS_BAD
  O3 at 16,2 type=HATCH_PANEL verbs=LOOK|USE fuse=INSERT_FUSE badge=SWIPE_BADGE reject=NO_FIT cond=POWER_ON
END
```

Common properties:
- `type=<OBJ_TYPE>` (see below)
- `verbs=LOOK|TAKE|USE|TALK|OPERATE` (pipe-separated)
- `cond=<COND>` optional (defaults to `ALWAYS`)
- `look=`, `take=`, `use=`, `talk=`, `operate=` script names

Type-specific routing:
- `LOCKER_KEYPAD`: `code=<int>`, `ok=<ACT>`, `bad=<ACT>`
- `BREAKER_PANEL`: `var=<VAR>`, `expect=<value>`, `ok=<ACT>`, `bad=<ACT>`
- `HATCH_PANEL`: `fuse=<ACT>`, `badge=<ACT>`, `reject=<ACT>` (stored as `use`)

### MAP

`MAP` is exactly `h` rows of `w` characters. Every character must exist in the `TILES` mapping.

If the active `.tset` defines `OBJECTS`, a character may also represent an object stamp.
In that case, the map must contain a solid rectangular block of that character matching the
object’s `size=WxH`. The compiler replaces the block with the object’s tile layout.
If the block is incomplete or overlaps another stamp, compilation fails with an error.

Example (2x1 object with char `O`):

```
MAP
####################
#......OO..........#
#......OO..........#
#..................#
####################
END
```

## Object Types

These names must match the engine enum:
- `SIGN`
- `PICKUP`
- `LOCKER_KEYPAD`
- `BREAKER_PANEL`
- `HATCH_PANEL`
- `EXIT_TRIGGER`
- `NPC_INTERCOM`

## Notes

- If `tset=...` is used and the tset defines `CHARMAP`, the `TILES` section can be omitted.
- If both `TILES` and tset `CHARMAP` exist, `TILES` takes precedence.
