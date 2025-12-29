# Level Compiler (levelc.py)

This document explains the `tools/levelc.py` workflow, the input format, and how the output is used by the engine.

---

## 1) What levelc.py does

`levelc.py` compiles a text-based level file (`.lvl`) into:

- a binary blob (`.bin`) containing maps, objects, scripts, and messages
- a C file (`.c`) embedding the blob as a `uint8_t[]`
- a blob header (`.h`) exposing the blob symbol
- an ID header (`*_ids.h`) with enums for flags/vars/items/messages
- a format header (`level_format.h`) with offsets + accessors
- a symbol map (`.sym`) for debugging
- optional debug JSON (`.json`)

---

## 2) Input format summary

The file is block-based and easy to author.

```
LEVEL name="BOOT AUDIT" w=20 h=12 start=R0:S0

TILES
. 0
# 1
= 2
H 3
! 4
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
PANEL_NO_POWER = "HATCH: NO POWER"
PANEL_OK       = "PANEL: OK"
END

COND ALWAYS
  TRUE
END

ACT INSERT_FUSE
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
  O1 at 5,5 type=HATCH_PANEL verbs=LOOK|USE cond=ALWAYS look=SHOW_PANEL fuse=INSERT_FUSE
END
MAP
####################
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
#..................#
####################
END
ENDROOM
```

---

## 3) Objects and routing (Approach A)

Routing logic is engine-coded by object type; outcomes are data-driven scripts.

- `LOCKER_KEYPAD`:
  - `code=729`
  - `ok=<ACT>` stored in `alt0`
  - `bad=<ACT>` stored in `alt1`

- `BREAKER_PANEL`:
  - `var=<VAR>` stored in `p0`
  - `expect=<value>` stored in `p1`
  - `ok=<ACT>` stored in `alt0`
  - `bad=<ACT>` stored in `alt1`

- `HATCH_PANEL`:
  - `fuse=<ACT>` stored in `alt0`
  - `badge=<ACT>` stored in `alt1`
  - `reject=<ACT>` stored in `use` (optional)

Other types can use `look=`, `take=`, `talk=`, `operate=` as normal.

---

## 4) Commands and outputs

Example build for one level (auto output):

```
python tools/levelc.py levels/level1.lvl
```

This writes outputs into:

- `.bin` → `assets/levels/`
- `.c` → `src/levels/`
- `-blob.h`, ids `.h` → `include/levels/`
- `level_format.h` → `include/`
- `.sym`, `.json` → `build/levels/`

All files use the LEVEL name as the base filename (sanitized).

The generated `.c` uses Oscar64's `#embed` directive to include the `.bin` at
compile time. This keeps the binary as a separate file while still producing
a `const uint8_t[]` symbol for the engine to use. The `.c` includes the blob
header as `levels/<level>-blob.h` and the shared format header as
`level_format.h`.

---

## 5) How the engine uses the output

At runtime:

- `level1_blob` provides the raw bytes
- `level_format.h` provides offsets + helpers
- `level1.h` provides enums

Typical usage:

- `level_get_start_room()` → start room id
- `room_load_with_spawn(room, spawn)` → load a room
- `puzzle_run_actions(ofs)` → execute scripts

---

## 6) Example: Locker keypad + breaker

```
OBJECTS
  O1 at 4,3 type=LOCKER_KEYPAD verbs=LOOK|OPERATE code=729 ok=LOCKER_OK bad=LOCKER_BAD
  O2 at 10,6 type=BREAKER_PANEL verbs=OPERATE var=RELAY_BITS expect=0b101 ok=RELAYS_OK bad=RELAYS_BAD
END
```

---

## 7) Example: Hatch panel with item routing

```
OBJECTS
  O3 at 16,2 type=HATCH_PANEL verbs=LOOK|USE cond=POWER_ON
     look=SHOW_PANEL_OK
     fuse=INSERT_FUSE
     badge=SWIPE_BADGE
     reject=NO_FIT
END
```

The engine routes USE by item id and executes the correct action script.

---

## 8) File placement convention

Recommended layout:

- `levels/` for `.lvl` source files
- `tools/` for generated `.c/.h/.sym/.bin` outputs

---

## 9) Debugging tips

- Use `--sym` to inspect offsets for objects and scripts.
- Use `--json` to sanity-check IDs and counts.
- If objects are not interactable, check `cond=` names and script offsets.
