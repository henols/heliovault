## Level 3 — **HYDRO / BIOLAB: CLEAN WATER LIE**

**Rooms:** 3 single-screen rooms (Hub + Control + Lab)
**Theme:** the facility pretends contamination control is “for your safety,” but it’s really just another leash.

**New mechanic (Level 3 introduces exactly one):** **Water level control**
A single **PUMP DIAL** changes the water level across connected rooms: **HIGH / LOW** (keep it binary for clarity).

**Level goal:** Open the **DECON LIFT HATCH** (exit) by:

1. Getting a **FILTER CARTRIDGE**
2. Installing it to restore **AIRFLOW OK**
3. Entering the lab airlock
4. Printing a **DECON PASS**
5. Using the pass on the lift hatch

**Menu verbs needed:** LOOK, TAKE, USE, TALK, OPERATE

---

# Story beats (tight, readable)

**Level start (Room A):**

* ORACLE//9: `WELCOME TO HYDRO. CLEANLINESS IS COMPLIANCE.`
* Sign: `BIOWING ACCESS REQUIRES: AIRFLOW OK + DECON PASS`

**First time you reach the lab door (Room C) without airflow:**

* `AIRLOCK: AIR QUALITY CRITICAL. FILTER REQUIRED.`

**When you install the filter:**

* ORACLE//9: `AIRFLOW RESTORED. CONTAMINATION RISK: ACCEPTABLE.`
* (That “acceptable” line feels wrong on purpose.)

**Optional lore (LOG TAPE #03):**

* On LOOK: `"THE GARDEN IS JUST A SIMULATION WITH PLANTS."`

---

# Room graph

* **Room A (Hub): Hydro Atrium**
  Exits: left → Room B, right → Room C, top hatch (exit) locked
* **Room B: Pump Control Bay**
  Exits: right → Room A
* **Room C: Bio-Quarantine Lab + Airlock**
  Exits: left → Room A

Water level changes affect **Room A + Room C**.

---

# Required puzzle chain (clue → action → result/flags)

### Gate 1 — Reach the Filter Cartridge (water LOW)

* **Clue (Room A):** A grating under the water has a label you can only read when LOW:

  * When HIGH: `WATER: TOO DEEP`
  * When LOW: `INTAKE GRATE: SERVICE CACHE`
* **Action:** In Room B, OPERATE **PUMP DIAL** → set **LOW**
* **Result:** In Room A, the water drains, exposing the **INTAKE GRATE**.
* **Action:** OPERATE **INTAKE GRATE** → TAKE **FILTER CARTRIDGE**
* **Flags:** `water_low=1`, `got_filter=1`

### Gate 2 — Restore airflow (install filter)

* **Clue (Room A):** Vent stack panel reads: `FILTER SLOT: EMPTY`
* **Action:** USE **FILTER CARTRIDGE** on **VENT STACK**
* **Result:** `AIRFLOW OK` indicator turns green; lab airlock can open.
* **Flags:** `airflow_ok=1` (and optionally consume the item into “installed,” but do not softlock—make it non-removable)

### Gate 3 — Print Decon Pass (water HIGH inside lab)

* **Clue (Room C):** Pass printer sits on a floating service float that only rises when the water is HIGH:

  * When LOW: `PRINTER: OUT OF REACH`
  * When HIGH: `PRINTER: READY`
* **Action:** Enter Room C (airlock now opens), then go back to Room B and set **HIGH**
* **Result:** The float in Room C rises; you can reach the printer.
* **Action:** OPERATE **PASS PRINTER** → receive **DECON PASS**
* **Flags:** `water_high=1`, `has_pass=1`

### Gate 4 — Exit hatch

* **Clue (Room A):** `DECON LIFT: PASS REQUIRED`
* **Action:** USE **DECON PASS** on **LIFT PANEL**
* **Result:** hatch unlocks.
* **Action:** OPERATE **DECON LIFT HATCH**
* **Flags:** `lift_open=1` → Level complete

---

# Room breakdowns

## Room A — Hydro Atrium (Hub)

**Purpose:** Show the water mechanic visually, contain the filter pickup, host the exit hatch.
**Look:** plastic-chrome planters, neon hazard stripes, bubbling water, big “HYDRO SAFETY” signage.

**Exits:**

* Left edge → Room B
* Right edge → Room C (airlock)
* Top hatch → Level exit (locked until pass)

**Interactables (6–8):**

1. **VENT STACK** (filter slot, required)
2. **INTAKE GRATE** (filter pickup, only reachable on LOW)
3. **DEPTH GAUGE SIGN** (shows HIGH/LOW state)
4. **DECON LIFT PANEL** (pass gate)
5. **DECON LIFT HATCH** (exit)
6. **LOG TAPE #03** (optional)
7. **Small hazard strip**: slick algae edge (knockback, not death)

**Player-facing prompts:**

* `WATER LEVEL: HIGH`
* `INTAKE GRATE: SUBMERGED`
* `VENT STACK: FILTER MISSING`
* `TAKEN: FILTER CARTRIDGE`
* `AIRFLOW: OK`
* `LIFT: PASS REQUIRED`

---

## Room B — Pump Control Bay

**Purpose:** One obvious control point that affects other rooms. No gotchas.
**Look:** CRT diagrams, chunky dial, “DO NOT SET TO LOW DURING BIOWING TEST” warning.

**Exits:** right → Room A

**Interactables (5–7):**

1. **PUMP DIAL** (HIGH/LOW, required)
2. **STATUS CRT** (shows what changes: “Atrium depth / Biolab float”)
3. **EMERGENCY SHUTOFF** (flavor; does nothing, or just reaffirms current state)
4. **Sign: WATER ROUTING** (backup clue)
5. Optional **CREDITS** pickup (cosmetic/score)

**Player-facing prompts:**

* `PUMP DIAL: HIGH / LOW`
* `SET: LOW`
* `SET: HIGH`
* `CRT: LOW EXPOSES INTAKE. HIGH LIFTS BIO FLOAT.`

---

## Room C — Bio-Quarantine Lab + Airlock

**Purpose:** The “aha” use of HIGH water to reach the printer + teach the airlock gate.
**Look:** white plastic walls with bright warning decals, glowing sample lockers, chunky airlock door.

**Exits:** left → Room A

**Interactables (6–8):**

1. **AIRLOCK DOOR** (requires airflow_ok)
2. **PASS PRINTER** (reachable only at HIGH)
3. **FLOAT PLATFORM** (moves with water level; not “timing,” just state)
4. **BIO SIGNAGE** (backup instructions)
5. **Sample case** (optional flavor item)
6. **Hazard**: electrified puddle strip (knockback only, clearly animated)

**Player-facing prompts:**

* Before filter: `AIRLOCK: FILTER REQUIRED`
* After filter: `AIRLOCK: OPEN`
* Low water: `PRINTER: OUT OF REACH`
* High water: `PRINTER: READY`
* `PRINTED: DECON PASS`

---

# Sketches (3 rooms)

### Room A — Hydro Atrium (Hub)

Legend: `#` wall, `=` platform, `~` water, `P` spawn, `V` vent stack, `G` intake grate, `H` exit hatch, `L` lift panel, `T` tape, `<`/`>` exits

```
########################################
#                [H] DECON LIFT HATCH  #
#                [L] PANEL             #
#                                      #
#   [V] VENT STACK        [T] LOG      #
#                                      #
#   P                                  #
#===========            ===============#
#   ~~~~~~~~~~~~~~~~                 > #
#   ~~~~~~ [G] INTAKE ~~~~~~~~         #
#   ~~~~~~~~~~~~~~~~                 < #
########################################
```

### Room B — Pump Control Bay

Legend: `D` pump dial, `C` CRT, `k` credits

```
########################################
#   [C] STATUS CRT                     #
#                                      #
#           [D] PUMP DIAL              #
#           HIGH / LOW                 #
#                                      #
#                      [k]             #
#==================      ==============#
#                                      #
#                                      #
#======================================#
>                                      #
########################################
```

### Room C — Bio Lab + Airlock

Legend: `A` airlock door, `F` float platform, `R` pass printer, `~` water, `!` hazard strip

```
########################################
<   [A] AIRLOCK                        #
#                                      #
#              [R] PASS PRINTER        #
#                 (needs HIGH)         #
#                                      #
#===========      ==============       #
#   ~~~~~~~~      |    ! ! !   |       #
#   ~~~ [F] ~~~    (puddle hazard)     #
#   ~~~~~~~~      |            |       #
#======================================#
########################################
```

---

# Required vs optional

**Required:** filter cartridge → install → print pass → open lift
**Optional:** LOG TAPE #03, credits, sample case (flavor only)

---

# Failure & recovery (no softlocks)

* You can flip water HIGH/LOW forever. No “wrong” permanent state.
* Filter installation is a one-way upgrade (flag), not a consumable you can lose.
* If the player prints the pass, make it a permanent flag too (even if you also give an inventory item).

---

# Suggested flags (compact)

* `water_low` (or `water_state=0/1`)
* `got_filter`
* `airflow_ok`
* `has_pass`
* `lift_open`

Optional: for a harder emotional hit without added complexity, after you print the DECON PASS, have the printer also spit a second slip: `OUTSIDE STATUS: UNKNOWN (DATA WITHHELD)`—tiny, nasty, memorable.
