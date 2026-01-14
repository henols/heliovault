## Level 1 — **BOOT AUDIT**

**Rooms:** 2 single-screen rooms connected left/right.
**Goal:** Reach the **Access Lift Hatch** (exit) by restoring local power and rearming its maglock with a fuse. This level is pure onboarding: movement + menu interaction + simple “clue → action → state change” escape-room logic. 

**New mechanic introduced (only one):** **Breaker panel** (set a 3-switch pattern). 

**Required tasks (gates exit):**

1. Get **MAINT-3 BADGE** + **FUSE** (Room 1)
2. Set **RELAYS** correctly (Room 2)
3. **Insert FUSE** + **SWIPE BADGE** at hatch panel (Room 2)

**Optional:** Collect **LOG TAPE #01** (tiny story hint), + bonus “CREDITS” pickup.

---

# Story beats (Level 1)

Minimal, punchy, all delivered via short lines/signage.

**On load (Room 1):**

* Text box: `WAKE EVENT. CONTAINMENT ACTIVE.`
* ORACLE//9 (PA): `WELCOME, CITIZEN. PLEASE COMPLETE BOOT AUDIT.`
* Hint line (only once): `FIRE+UP: MENU`

**If player tries the Room 2 hatch early:**

* `HATCH: NO POWER.`

**When player finds LOG TAPE #01 (optional):**

* `LOG TAPE FOUND.`
* On LOOK: `"...ORACLE RUNS THE DRILL AGAIN. IT LIKES THIS VERSION."`

**When relays are set correctly (Room 2):**

* ORACLE//9: `AUDIT STEP 1: PASS. POWER ROUTED.`
* `STATUS: GREEN`

**On completion (Room 2):**

* ORACLE//9: `AUDIT COMPLETE. PLEASE REMAIN INSIDE.`
* (Door opens anyway. That’s the joke.)

---

# Room 1 — **Courier Vestibule**

**Purpose:** Teach interacting, give the two critical items, drop the clue for the breaker pattern. 

### Interactables (6 total)

1. **LOCKER L3** (keypad)
2. **MANIFEST CLIPBOARD** (clue source)
3. **INTERCOM “MIRA”** (optional hint)
4. **LOG TAPE #01** (optional collectible)
5. **VENDING SLOT** (optional credits pickup)
6. **EXIT to Room 2** (right edge)

### Items available

* **SCREWDRIVER** (in locker) *(optional but nice for teaching “USE tool on panel” later; not required in this Level 1 chain if you prefer)*
* **MAINT-3 BADGE** (in locker) *(required)*
* **FUSE (BLUE)** (in locker) *(required)*

### Puzzle (Room 1): Locker code

* **Clue:** LOOK at the clipboard on a desk:

  * `MANIFEST: BAY A / LOCKER L3`
  * `PIN: 7-2-9`
* **Action:** OPERATE LOCKER → enter **729**
* **Result/state:** Locker opens; items can be TAKEn.

**Why this works early:** No guessing, no pixel hunting, and it forces the player to use the menu once. 

### Optional hint NPC (Intercom)

* TALK → MIRA:

  * `MIRA: "Power’s dead in the relay gallery. Flip 1&3 ON. 2 OFF."`
    This repeats the breaker pattern so the player can’t get stuck.

### Player-facing text (Room 1)

* `LOCKER: KEYPAD LOCKED.`
* `CLIPBOARD: LOOK?`
* `PIN: 7-2-9`
* `TAKEN: MAINT-3 BADGE`
* `TAKEN: FUSE (BLUE)`
* `TAKEN: SCREWDRIVER` *(optional)*
* `MIRA: "RELAYS ARE LABELLED. DON'T OVERTHINK IT."`

---

## Room 1 sketch (single screen)

Legend: `#` wall, `=` platform, `H` ladder, `P` spawn, `L` locker, `M` manifest, `I` intercom, `T` tape, `V` vending, `>` exit to Room 2

```
########################################
#   I        GLASS     WARNING STRIPES  #
#                                        #
#   [M] desk     [L3] LOCKER             #
#                                        #
#                 [V]                    #
#                                        #
#   P                                    #
#======================     ============#
#                H          #           #
#                H          #    [T]    #
#                H          #           #
#===========================#===========#
#                                        >
########################################
```

Traversal is forgiving: 1–2 easy jumps, one obvious ladder. 

---

# Room 2 — **Power Relay Gallery**

**Purpose:** Teach the “set state → system changes → exit unlock” loop. Mild hazard only. 

### Interactables (7 total)

1. **BREAKER PANEL** (three switches: 1/2/3) *(required)*
2. **STATUS LIGHT** (shows RED/GREEN)
3. **HATCH PANEL** (fuse slot + badge swipe) *(required)*
4. **ACCESS LIFT HATCH** (exit) *(required)*
5. **SPARK CABLE** (hazard zone, knockback only)
6. **SIGN: RELAY MAP** (backup clue)
7. **Left edge return** to Room 1

### Puzzle chain (Room 2)

**Gate A: Restore power**

* **Clue sources (redundant on purpose):**

  * From MIRA in Room 1: `1&3 ON. 2 OFF.`
  * Or LOOK the sign in Room 2:

    * `RELAY MAP (BAY A): 1=ON 2=OFF 3=ON`
* **Action:** OPERATE BREAKER PANEL → set switches to **ON/OFF/ON**
* **Result/state:** `flag_relays_ok = 1`, STATUS goes GREEN, hatch panel becomes powered:

  * `HATCH PANEL: POWER OK. INSERT FUSE.`

**Gate B: Arm hatch panel**

* **Clue:** Powered hatch panel now shows: `FUSE MISSING.`
* **Action:** USE FUSE (BLUE) → on HATCH PANEL
* **Result/state:** `flag_fuse_installed = 1`, text: `FUSE SEATED.`

**Gate C: Authorization**

* **Action:** USE MAINT-3 BADGE → on HATCH PANEL
* **Result/state:** `flag_badge_swiped = 1`, hatch unlocks:

  * `MAGLOCK: RELEASED.`
  * Access Lift Hatch becomes OPERATABLE.

**Exit**

* **Action:** OPERATE ACCESS LIFT HATCH
* **Result:** level complete → transition to Level 2.

### Mild hazard (optional pressure, not a skill gate)

* **Spark cable** arcs every ~2 seconds. If touched: knockback + drop to lower floor, no death.
* Text: `ZAP! (LOW VOLTAGE)`

This matches the “falling costs time/position, not instant death” philosophy. 

---

## Room 2 sketch (single screen)

Legend adds: `B` breaker, `S` status light, `F` hatch panel (fuse+badge), `E` exit hatch, `~` spark hazard, `<` return to Room 1

```
########################################
<                                       #
#   SIGN: RELAY MAP         [E] HATCH   #
#                         ========      #
#            [S]            [F] PANEL   #
#            GREEN/RED                  #
#                                        #
#   [B] BREAKERS                         #
#   (1)(2)(3)                            #
#                                        #
#==============          ===============#
#             H          #   ~~~~~~~    #
#             H          #   ~~~~~~~    #
#=============H==========#==============#
#                                        #
########################################
```

---

# State flags (clean + table-driven friendly)

* `got_badge`
* `got_fuse`
* `got_screwdriver` *(optional)*
* `locker_open`
* `relays_ok`
* `panel_powered` *(can be implied by relays_ok)*
* `fuse_installed`
* `badge_swiped`
* `hatch_open`

---

# Fail & recovery (no softlocks)

* Wrong breaker config: nothing breaks; status stays RED; player can flip again.
* If player leaves fuse/badge behind: both remain in Room 1 locker forever.
* Hazard only repositions; never blocks progress.

This aligns with “no softlocks” + “early levels teach safely.” 

---

# Minimal menu options you need for Level 1

* **LOOK, TAKE, USE, TALK, OPERATE** (that’s it)

Context-sensitive examples:

* Near clipboard: `LOOK`
* Near locker: `OPERATE`, `LOOK`
* In front of hatch panel with fuse in inventory: `USE`

---

If you want the next step: I’ll turn this into **authorable room data** (metatile interactables list + conditions/actions) so it drops straight into your engine’s flag/trigger tables. 
