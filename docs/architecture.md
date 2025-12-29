# Architecture and Technical Spec (Oscar64)

This document is the technical source of truth for engine architecture, data formats, and runtime behavior. It is Oscar64-only.

---

## 1) Toolchain and targets

- Target: stock C64
- Toolchain: Oscar64 (C + asm)
- Output: `.prg` runnable on emulator or hardware
- PAL/NTSC: support both if possible, via build-time switch or detection

---

## 2) High-level engine pieces

### A) Main state machine

Keep it simple and explicit:

- TITLE
- LEVEL_INTRO (optional)
- ROOM_TRANSITION (fade/wipe + load)
- GAMEPLAY
- ACTION_MENU (world paused by default)
- MESSAGE_BOX (overlay)
- GAME_OVER / LEVEL_COMPLETE

### B) Timing model

- Raster IRQ: music + lightweight tick counter (and optional input sampling)
- Main loop: waits for tick, then updates game state and render

### C) Room/level manager

Responsibilities:

- Load room data (map, exits, spawns, interactables)
- Spawn entities for the room
- Handle edge transitions + door/ladder transitions
- Keep per-level flags and inventory across rooms

### D) Renderer (char mode + sprites)

- Background: metatile map (2x2 chars typical)
- Expand metatile IDs to Screen RAM + Color RAM
- Actors: player + key NPCs/enemies as sprites
- Full redraw only on room load; use dirty updates during gameplay

### E) Input

- Joystick read + edge detection
- Fire+Up (or context) opens action menu

### F) Player controller

- Ground / jump / fall / ladder / knockback states
- Forgiving ledges and landings

### G) Collision

- Primary: metatile flags (solid, ladder, hazard)
- Entity overlap for interactions and hazards

### H) Entity system

- Fixed pool, no malloc
- Type/state update via switch or function tables

### I) Interactables + action menu

- Interactables are room-placed objects with verbs + conditions + actions
- Menu is context-sensitive and pauses gameplay by default

### J) Puzzle/trigger system

- Flags + variables + conditions + actions
- Prefer table-driven triggers/bytecode over hardcoded puzzles

### K) Inventory system

- Small fixed list (6–10 items)
- Item IDs only; no complex crafting

### L) Text/message box

- Short prompts, single-message queue is fine

### M) Audio hooks

- Music in IRQ, SFX queued from main loop

### N) Persistence (optional)

- Checkpoint = room + flags + inventory

---

## 3) Module breakdown (recommended)

- `src/main.c`: state machine + main loop
- `asm/irq.asm`: raster IRQ
- `src/input.c/.h`: joystick + edge detection
- `src/room.c/.h`: room load + transitions
- `src/render.c/.h`: metatile expansion + HUD
- `src/metatile.c/.h`: metatile definitions + flags
- `src/player.c/.h`
- `src/entity.c/.h`
- `src/collision.c/.h`
- `src/menu.c/.h`: action menu UI
- `src/puzzle.c/.h`: flags + condition/action execution
- `src/inventory.c/.h`
- `src/textbox.c/.h`
- `src/audio.c/.h`

---

## 4) Data formats (compact + authorable)

### Metatiles (global)

- `mt_chars[MT_COUNT][4]`: TL, TR, BL, BR
- `mt_flags[MT_COUNT]`: SOLID, LADDER, HAZARD, INTERACT, DOORWAY, ONE_WAY
- Optional: per-char colors or per-metatile color

### Room content (per room)

- Header: width, height, room_id
- Map: `width * height` bytes of metatile IDs
- Exits: edges + door/ladder transitions
- Spawns: list of `(type, x, y, state)`
- Interactables: `(id, x, y, verb_mask, cond, action)`

### Puzzle triggers

Two options:

1) Condition/action tables (simple and fast)
2) Tiny bytecode interpreter (flexible, small)

Start with condition/action tables or bytecode based on authoring needs.

---

## 5) Rendering behavior

- Screen: 40x25 chars
- Metatile map: 20x12 (40x24 chars), last row reserved for HUD

Mapping:

- `cx = mx * 2`
- `cy = my * 2`

Rendering loop:

- Full redraw on room load
- Dirty update for puzzle-driven tile swaps

---

## 6) Per-frame update order

1) Read input (held + pressed)
2) Transition step if changing rooms
3) If menu open: update selection + apply action
4) Else gameplay:
   - Player update
   - Player vs world collision
   - Entities update + collision
   - Proximity triggers
5) Render sprites + dirty background + HUD

---

## 7) Memory map notes

- Screen RAM: `$0400`
- Color RAM: `$D800`
- Charset in RAM: `$2000` or `$3000`
- Sprite data: aligned to 64-byte blocks
- Room map buffer: ~240 bytes for 20x12
- Entity arrays + flags + inventory: fixed size
- Zero page: hot vars (player pos/vel, metatile pointers)

---

## 8) Vertical slice plan

Build one room that exercises the core loop:

- One locked exit door
- One puzzle panel that needs a fuse item
- One enemy patrol for light pressure
- Menu verbs: LOOK, TAKE, USE
- Message box responses: "IT'S LOCKED", "POWER ON", "DOOR UNLOCKED"

This validates: metatiles, collision, interactables, inventory, triggers, messages, transitions.
