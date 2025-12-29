# Game Design Spec (Escape-Room Platformer)

This document is the design source of truth: level structure, room rules, interactions, puzzles, and output format for new content.

---

## 1) Core concept

- Side-view C64 platformer, Bruce Lee–style
- Single-screen rooms (no scrolling)
- Escape-room puzzle loop with light combat/hazards

**Critical framing:** This is not top-down. Every room assumes gravity, jumping, and side-on reachability.

---

## 2) Structure

- Levels: 1–4 rooms each
- Connections: left/right edges, doors, ladders
- Goal: complete required tasks to unlock the level exit

---

## 3) Movement rules

- Gravity-based movement
- Run, jump, fall, ladder climb
- Forgiving ledge detection; avoid precision jumps
- Falls cost time/position, not instant death

Controls (default):

- Left/Right: run
- Up/Down: ladder entry/climb
- Fire: jump
- Fire + Up (or context): open action menu

---

## 4) Room design rules

- Rooms must read as platform layouts at a glance
- 3–8 interactables per room
- Each room has a clear purpose: puzzle, clue, item, NPC, traversal, or hazard
- Avoid maze-like layouts; use a hub if 3–4 rooms

---

## 5) Interaction model

- Menu-based, no typing
- Verbs: LOOK, TAKE, USE, TALK, GIVE, PUSH, PULL, OPERATE (keep small)
- Interaction requires overlap + facing (or within 1 tile)

World pause:

- Menu pauses the world by default
- Rare pressure rooms may keep time running

---

## 6) Metatile rules

- Recommended: 20x12 metatiles (2x2 chars) for 40x24 playfield
- Minimum metatile types: SOLID, EMPTY, PLATFORM, LADDER, HAZARD, DOOR, OBJECT
- Door/exit tiles are distinct and visually locked when locked

---

## 7) Inventory rules

- 6–10 items max
- Simple items (keys, tools, parts)
- Avoid crafting; no softlocks

---

## 8) NPC rules

Friendly NPCs:

- Hint, trade, unlock, trigger events
- Optional companion behaviors (FOLLOW/STAY, hold switch, distract)

Hostiles:

- Patrollers, blockers, turrets
- Combat is light and readable
- Prefer puzzle alternatives (disable, distract, lock out)

---

## 9) Puzzle design rules

Each puzzle defines:

- Clue source(s)
- Player action(s)
- State change(s)

Avoid:

- Pixel hunting
- Verb guessing
- External trivia
- Long backtracking

---

## 10) Difficulty and progression

- Early levels teach safely
- Later levels combine mechanics + light pressure
- One new mechanic per level max
- Failures reset locally and provide clear feedback

---

## 11) Output format for new level proposals

Use this format for design content:

- Level overview (room count, goal, required tasks, new mechanic)
- Room breakdown (layout notes, exits, interactables, NPCs, hazards)
- Puzzle list (clue → action → result/state flag)
- Required vs optional tasks
- Failure & recovery
- Player-facing text (short prompts + verbs)

---

## 12) Level template

**Level Overview**

- Name:
- Rooms (2–4): IDs + purpose
- New mechanic (if any):
- Required tasks:
- Optional rewards:

**State Flags**

- Lx_FLAG_NAME: description

**Items**

- ITEM_NAME: location, use

**NPCs**

- NPC_NAME: location, role

**Room Breakdown (repeat per room)**

- Room ID + name:
- Purpose:
- Exits:
- Interactables (3–8):
- Hazards:
- NPCs:

**Metatile Layout (20x12)**

Legend: `#` SOLID, `.` EMPTY, `=` PLATFORM, `H` LADDER, `!` HAZARD, `D` DOOR, `O` OBJECT

```
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
```

**Puzzle List**

- Clue → action → result/state flag

**Failure & Recovery**

- What happens on mistake

**Player-Facing Text**

- Short messages (max ~20 chars)

---

## 13) Starter progression (skeleton)

**Level 1: The Intake**

- New mechanic: ladders + basic door key
- Required: find key, unlock exit
- Optional: tutorial hint NPC

**Level 2: The Switchroom**

- New mechanic: lever toggles platform/hazard
- Required: route power, open exit
- Optional: hidden cache

**Level 3: The Trade**

- New mechanic: NPC trade
- Required: fetch item, get access key
- Optional: disable patrol for safer route

**Level 4: The Lockdown**

- New mechanic: timed door or pressure room
- Required: sequence actions under pressure
- Optional: alternate safe route
