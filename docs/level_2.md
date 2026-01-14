## Level 2 — **TRANSIT SECTOR: REROUTE**

**Rooms:** 4 single-screen rooms (one is a hub).
**Theme:** you realize the lockdown is *staged*—transit routes are “broken on purpose,” and you reroute them. 

**New mechanic (Level 2 introduces exactly one):** **Companion positioning** (PATCH-3 can **FOLLOW / STAY** to hold a plate / pedal). This is straight out of the intended friendly-NPC puzzle role style. 

**Level goal:** Get through the **Outbound Turnstile** (exit to Level 3) by:

1. Restoring track power + route to DOCK
2. Printing a **TRANSIT PASS**
3. Rebooting **PATCH-3** and using it to satisfy a two-person safety interlock
4. Docking the shuttle and opening the turnstile

Interaction stays menu-based (LOOK/TAKE/USE/TALK/OPERATE) and puzzle-first, low-precision traversal. 

---

# Story beats (short, C64-friendly)

**On entry (Room A):**

* ORACLE//9: `WELCOME, CITIZEN. TRANSIT IS A PRIVILEGE.`
* Status sign is visibly “wrong”: `ROUTE: LOOP TEST (DEFAULT)` (a hint that it’s intentionally set to waste your time). 

**First time you reach the monorail area (Room D):**

* ORACLE//9: `SAFETY INTERLOCK ENABLED. TWO-ACTOR COMPLIANCE REQUIRED.`

**When PATCH-3 boots:**

* PATCH-3: `BEEP. UNIT PATCH-3 ONLINE. AWAITING DIRECTIVE.`
* Menu adds: TALK → `FOLLOW / STAY`

**When you dock successfully:**

* ORACLE//9: `AUDIT: ACCEPTABLE. PLEASE REMAIN WITHIN DESIGNATED ROUTES.`

---

# Map / room graph (4 rooms, 1 hub)

* **Room A (Hub): Transit Lobby**
  Connects **left → Room B**, **down → Room C**, **right → Room D**
* **Room B: Tube Junction J-9** (power + items)
* **Room C: Service Catwalk / Storage** (PATCH-3)
* **Room D: Monorail Dock** (two-person interlock + level exit)

This follows the “one hub-ish room” rule for 3–4 room levels. 

---

# Required task chain (clean “clue → action → state change”)

### Gate 1 — Track Power + Route

* **Clue (Room A):** `TRACK BUS: RED. SERVICE AT J-9.`
* **Action (Room B):** OPERATE **ROUTE LEVER** at J-9 → set to **DOCK**
* **Result/flags:** `track_power=1`, `route_dock=1`
  Room A kiosk powers on and Room D shutter unlocks.

### Gate 2 — Print the Transit Pass

* **Clue (Room A):** Kiosk reads `INSERT 1 CREDIT`
* **Action:** TAKE **CREDIT** (Room B) → USE at **KIOSK**
* **Result/flags:** `has_pass=1` (prints **TRANSIT PASS**)

### Gate 3 — Reboot PATCH-3 (companion unlock)

* **Clue (Room A):** Sign: `PATCH-3 STORAGE — POWER CELL REQUIRED`
* **Action:** TAKE **POWER CELL** (Room B) → USE on **PATCH-3** (Room C)
* **Result/flags:** `patch3_online=1` and companion commands become available. 

### Gate 4 — Two-person safety interlock (final)

* **Clue (Room D):** Console says `INTERLOCK: PEDAL HELD`
* **Action:** TALK PATCH-3 → **STAY** on **DEADMAN PEDAL**
  Then OPERATE **DOCK CONSOLE**
* **Result/flags:** `interlock_ok=1`, `shuttle_docked=1`

### Exit — Outbound Turnstile

* **Action:** USE **TRANSIT PASS** on **OUTBOUND TURNSTILE**
* **Result:** turnstile opens → transition to Level 3

This keeps “action supports puzzles,” not combat/platform precision. 

---

# Room breakdowns

## Room A — Transit Lobby (Hub)

**Purpose:** central navigation + pass printing + down-hatch to PATCH-3.
**Exits:** left to B, down to C (locked until key), right to D (locked until power).

**Interactables (6):**

1. **TRACK STATUS PANEL** (LOOK)
2. **TRANSIT KIOSK** (USE credit)
3. **SERVICE HATCH** (OPERATE; needs MAINT KEY)
4. **MAP BOARD** (LOOK)
5. **SECURITY SHUTTER** to Room D (locked until power)
6. **ORACLE SPEAKER** (flavor barks)

**Player-facing text:**

* `STATUS: TRACK BUS RED.`
* `KIOSK: INSERT 1 CREDIT.`
* `HATCH: KEY REQUIRED.`
* `SHUTTER: NO POWER.`

---

## Room B — Tube Junction J-9

**Purpose:** restore track route + collect items.
**Exits:** right back to A.

**Interactables (7):**

1. **J-9 ROUTE LEVER** (3 positions: LOOP / DOCK / QUARANTINE)
2. **J-9 INDICATOR LIGHT** (RED/GREEN)
3. **LOCKER “MAINT”** (contains MAINT KEY)
4. **CHARGE CRADLE** (holds POWER CELL)
5. **CREDIT** pickup
6. **SPARK CABLE** hazard strip (knockback only)
7. **SIGN: ROUTE LEGEND** (backup clue)

**Puzzle detail:**

* Sign says: `FOR OUTBOUND: ROUTE = DOCK`
* Lever set to DOCK flips indicator GREEN and powers lobby.

**Enemy pressure (optional):**

* One slow **patrol drone** that just bumps/knocks back (no death). Optional: skip it for a cleaner puzzle room—this level already has enough moving parts.

**Player-facing text:**

* `LEVER: LOOP / DOCK / QUARANTINE`
* `J-9: ROUTE SET TO DOCK.`
* `TAKEN: CREDIT`
* `TAKEN: POWER CELL`
* `TAKEN: MAINT KEY`
* `ZAP! (LOW VOLTAGE)`

---

## Room C — Service Catwalk / Storage

**Purpose:** introduce companion, no combat, low-stress.
**Exits:** up back to A (via hatch ladder).

**Interactables (5):**

1. **PATCH-3** (USE power cell, then TALK)
2. **DIAGNOSTIC CRT** (LOOK: explains FOLLOW/STAY)
3. **TOOL RACK** (optional: “CABLE TIE” flavor item or nothing)
4. **VENT FAN** (background hazard-looking, non-lethal)
5. **LADDER** back up

**Player-facing text:**

* Before power: `PATCH-3: NO POWER.`
* After power: `PATCH-3 ONLINE.`
* CRT: `TALK: FOLLOW / STAY`

---

## Room D — Monorail Dock (Exit room)

**Purpose:** two-person interlock + dock shuttle + open turnstile.
**Exits:** left back to A; right turnstile to Level 3.

**Interactables (7):**

1. **DEADMAN PEDAL** (plate)
2. **DOCK CONSOLE** (OPERATE only if pedal held)
3. **SHUTTLE DOOR** (opens after docking; mostly visual reward)
4. **OUTBOUND TURNSTILE** (requires pass)
5. **STATUS LIGHTBAR** (shows “INTERLOCK” and “DOCKED”)
6. **SAFETY SIGN** (backup clue)
7. **MOVING PLATFORM EDGE** (simple, slow, not timing-critical)

**Player-facing text:**

* `CONSOLE: INTERLOCK REQUIRED.`
* `PATCH-3: HOLDING PEDAL.`
* `CONSOLE: DOCKING...`
* `STATUS: DOCKED.`
* `TURNSTILE: PASS REQUIRED.`
* `ACCESS GRANTED.` 

---

# Sketches (ASCII “room intent” layouts)

### Room A — Transit Lobby (Hub)

Legend: `#` wall, `=` platform, `H` ladder, `P` spawn, `K` kiosk, `S` status, `M` map, `D` shutter to Dock, `h` hatch down, `>` exit, `<` exit

```
########################################
# [M] MAP      [S] TRACK STATUS   [D]  >
#                                      #
#          [K] KIOSK                    #
#                                      #
#                                      #
#   P                                  #
#===========           ================#
#     h  (HATCH DOWN)                  #
#     h                                #
#     h                                #
#===========           ================#
<                                      #
########################################
```

### Room B — Tube Junction J-9

Legend: `J` lever, `L` light, `k` locker (MAINT KEY), `C` credit, `B` power cell, `~` sparks

```
########################################
#  SIGN: ROUTE LEGEND                  #
#                                      #
#  [J] ROUTE LEVER     [L] INDICATOR   #
#                                      #
#  [k] MAINT LOCKER        [B] CELL    #
#                                      #
#==================      ==============#
#        ~~~~~~          #    [C]      #
#        ~~~~~~          #             #
#========================#=============#
#                                      >
########################################
```

### Room C — Service Catwalk / Storage

Legend: `X` PATCH-3, `CRT` terminal

```
########################################
#   CATWALK / STORAGE                  #
#                                      #
#   [CRT] DIAGNOSTICS                  #
#                                      #
#           [X] PATCH-3 (OFFLINE)      #
#                                      #
#==================      ==============#
#        H                             #
#        H                             #
#========H=============================#
<                                      #
########################################
```

### Room D — Monorail Dock (Exit)

Legend: `P` pedal, `O` dock console, `T` turnstile (exit), `=` slow platform

```
########################################
<    STATUS LIGHTBAR        [T] EXIT    #
#                                      #
#   [P] DEADMAN PEDAL     [O] CONSOLE  #
#                                      #
#                SHUTTLE BAY           #
#===========                 ==========#
#          = (SLOW PLATFORM)          #
#===========                 ==========#
#                                      #
########################################
```

---

# Required vs optional

**Required:**

* route lever to DOCK
* credit → kiosk → transit pass
* power cell → PATCH-3 reboot
* PATCH-3 holds pedal while you operate console
* pass → turnstile

**Optional (rewards only):**

* **LOG TAPE #02** in Room D (or B) with one line of lore
* a cosmetic “badge sticker” item
* disable/avoid patrol drone (if included)

---

# Failure & recovery (no softlocks)

* Wrong route lever: can be changed anytime; indicator tells you instantly.
* If PATCH-3 gets separated: TALK again to FOLLOW, or it respawns at Room C when you re-enter that room (simple “rubber-band” rule).
* Spark hazard = knockback only (time loss), not death, consistent with “falling costs time/position.” 
* Credit/pass can’t be lost (if “used,” it converts into a permanent `has_pass` flag).

---

# Flags (table-friendly)

* `route_dock`
* `track_power`
* `has_credit` (or `credit_used`)
* `has_pass`
* `has_maint_key`
* `patch3_online`
* `patch3_mode` (FOLLOW/STAY)
* `interlock_ok`
* `shuttle_docked`
* `turnstile_open`

---

Optional: to make Level 2 feel a bit nastier (without becoming “action game”), make Room D the only **pressure room** where the menu doesn’t pause for ~10 seconds after docking starts. Use sparingly, clearly labeled, per the rules.
