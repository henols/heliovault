## Level 5 — **THE SPINE: MANUAL OVERRIDE**

**Rooms:** 4 single-screen rooms (vertical climb vibe, one mid “workshop” room)
**Theme:** ORACLE’s “perfect” automation collapses the moment you force it through **physical wiring**.

**New mechanic (Level 5 introduces exactly one):** **Patch-bay routing**
You physically connect labeled ports with **PATCH CABLES** to route power/auth/safety signals. No timing, no precision platforming—just state + logic.

**Level goal:** Bring the **BLACK CARTRIDGE** to the **TRUTH TERMINAL**, extract an **OVERRIDE SEAL**, then power and unlock the **SPINE LIFT** to reach Level 6.

---

# Room graph (4 rooms)

* **Room A (Entry): Spine Base Lobby**

  * Up → Room B
  * Right → Room C
* **Room B: Cable Trunk**

  * Down → Room A
  * Up → Room D
* **Room C: Manual Override Bay (Patch Room)**

  * Left → Room A
* **Room D: Oracle Node Gate (Exit Room)**

  * Down → Room B
  * Exit hatch to Level 6

This layout forces one backtrack through the hub, but stays readable.

---

# Story beats (short, sharp)

**On load (Room A):**

* ORACLE//9: `WELCOME TO THE SPINE. THIS AREA IS NOT FOR COURIERS.`
* Wall sign (big): `AUTOMATION FAILSAFE: MANUAL PATCH REQUIRED`

**First time you touch the patch bay (Room C) without cables:**

* `PATCH BAY: NO CABLES INSTALLED.`

**When you correctly patch the system:**

* `BUS ROUTED. LIFT POWER: ONLINE.`
* ORACLE//9: `UNAPPROVED CONFIGURATION DETECTED.`

**When you insert BLACK CARTRIDGE in Room D:**

* `TRUTH TERMINAL: MEDIA AUTHENTIC.`
* ORACLE//9: `STOP. THAT IS NOT A STORY YOU ARE CLEARED TO READ.`

**Level completion:**

* `SPINE LIFT: OPEN.`
* ORACLE//9: `PLEASE REMAIN INSIDE.` (still polite, still wrong)

---

# Core puzzle chain (clue → action → state change)

### Gate 1 — Learn the correct routing (Room A)

* **Clue:** LOOK the **WIRING PLACARD** (sticky label on a cracked CRT)

  * `ROUTE SPEC (SPINE LIFT):`
  * `BUS A → LIFT MOTOR`
  * `BUS B → MAGLOCK`
  * `BUS C → SAFETY LOOP`

This makes the patch puzzle deterministic (no guesswork).

### Gate 2 — Collect patch hardware (Room B + Room A)

* **Find (Room B):** TAKE **PATCH CABLE x2** (obvious hanging coils)
* **Find (Room A):** TAKE **JUMPER PLUG** (in a small “EMERGENCY KIT” drawer)
* **Flags:** `has_cable_1`, `has_cable_2`, `has_jumper`

### Gate 3 — Patch the bay (Room C)

* **Action:** OPERATE **PATCH BAY** and connect:

  * Cable 1: `BUS A → LIFT MOTOR`
  * Cable 2: `BUS B → MAGLOCK`
  * Jumper: `BUS C → SAFETY LOOP`
* **Result:** `lift_power=1` and `maglock_armed=1` (status lamp turns GREEN)
* **Text:** `PATCH OK. STATUS: GREEN`

### Gate 4 — Extract the Override Seal (Room D)

* **Action:** USE **BLACK CARTRIDGE** on **TRUTH TERMINAL**
* **Result:** prints/sets `override_seal=1` (no fragile paper item needed; just a flag)
* **Text:** `OVERRIDE SEAL ISSUED.`

### Exit — Open the Spine Lift (Room D)

* **Action:** OPERATE **SPINE LIFT PANEL**
* **Condition:** requires `lift_power=1` + `maglock_armed=1` + `override_seal=1`
* **Result:** hatch opens → Level 6

---

# Room breakdowns

## Room A — **Spine Base Lobby**

**Purpose:** introduce the “manual patch” concept, give the routing clue, hold the jumper plug.
**Look:** tall shaft walls, ribbed panels, warning stripes, big cable bundles vanishing upward, “AUTHORIZED PERSONNEL” plaques.

**Interactables (6–8):**

1. **WIRING PLACARD** (clue)
2. **EMERGENCY KIT DRAWER** (contains JUMPER PLUG)
3. **STATUS LAMP** (RED until patched)
4. **ORACLE SPEAKER** (flavor barks)
5. **MAINTENANCE MAP** (shows “PATCH BAY → EAST”)
6. Ladder / lift frame up to Room B
7. Door to Room C

**Key text:**

* `STATUS: RED`
* `PLACARD: BUS A→MOTOR, BUS B→MAG, BUS C→LOOP`
* `TAKEN: JUMPER PLUG`

---

## Room B — **Cable Trunk**

**Purpose:** get the cables; show the Spine as a dangerous machine, but keep hazards non-lethal.
**Look:** thick conduits, moving pistons behind grates, sparking junctions (knockback only).

**Interactables (6–9):**

1. **PATCH CABLE COILS** (TAKE x2)
2. **JUNCTION BOX** (LOOK: flavor + confirms “Buses A/B/C”)
3. **PISTON VENT** hazard strip (knockback)
4. **SERVICE SIGN** (points to “NODE GATE UP”)
5. Optional **LOG TAPE #05** (lore)
6. Ladders/platforms up/down

**Key text:**

* `TAKEN: PATCH CABLE`
* `ZAP! (LOW VOLTAGE)`
* `SIGN: NODE GATE — UP`

---

## Room C — **Manual Override Bay (Patch Room)**

**Purpose:** the actual new mechanic puzzle.
**Look:** big patch bay with chunky jacks, colored labels, a CRT that only shows “ROUTE SPEC.”

**Interactables (6–8):**

1. **PATCH BAY** (connect ports)
2. **PORT LABELS** (LOOK: lists BUS A/B/C and targets)
3. **STATUS LAMP** (RED/GREEN)
4. Optional **SPARE CABLE** (decor only; don’t add confusion)
5. Optional **INSULATED GLOVES** (flavor item, no effect)
6. Door back to A

**Key text:**

* `PATCH BAY: CONNECT BUS TO TARGET`
* `STATUS: GREEN` (when correct)
* `LIFT POWER: ONLINE`

Patch UI suggestion (simple):

* When OPERATE: show cursor over ports and let player choose Source then Target.

---

## Room D — **Oracle Node Gate (Exit Room)**

**Purpose:** reward with truth + final gate to Level 6.
**Look:** sterile, propaganda-clean, with a single terminal and the lift panel. One “security eye” in the background for vibe.

**Interactables (6–9):**

1. **TRUTH TERMINAL** (cartridge reader)
2. **SPINE LIFT PANEL** (final lock)
3. **SPINE LIFT HATCH** (exit)
4. **SECURITY CAMERA** (background; optional “LOOK” flavor)
5. **STATUS LIGHTBAR** (shows POWER / MAGLOCK / SEAL)
6. Optional **ALARM LASER LINE** (knockback only)

**Key text:**

* `TRUTH TERMINAL: INSERT MEDIA`
* `OVERRIDE SEAL ISSUED`
* `LIFT: SEALED` (before override)
* `LIFT: OPEN`

---

# Sketches (4 rooms)

### Room A — Spine Base Lobby

Legend: `#` wall, `P` spawn, `W` wiring placard, `J` jumper kit, `S` status lamp, `^` up to B, `>` to C

```
########################################
#   [W] ROUTE PLACARD      [S] STATUS  #
#                                      #
#   [J] EMERGENCY KIT                  #
#                                      #
#   P                                  #
#===========                 ==========#
#                 ^ (LADDER)          #
#                 ^                  > #
#===========                 ==========#
########################################
```

### Room B — Cable Trunk

Legend: `C` cables, `~` hazard strip, `T` tape, `v` down, `^` up

```
########################################
#        SIGN: NODE GATE UP            #
#                                      #
#   [C] PATCH CABLES       [T] LOG     #
#                                      #
#===========        ===================#
#    ~~~~~~ (piston/spark hazard)      #
#===========        ===================#
#   v (DOWN)                 ^ (UP)    #
########################################
```

### Room C — Manual Override Bay

Legend: `BAY` patch bay, `L` lamp, `<` back to A

```
########################################
#   MANUAL OVERRIDE BAY                #
#                                      #
#   [BAY] PATCH PANEL                  #
#   BUS A/B/C -> MOTOR/MAG/LOOP        #
#                                      #
#   [L] STATUS LAMP                    #
#===========        ===================#
#                                      #
<                                      #
########################################
```

### Room D — Oracle Node Gate (Exit)

Legend: `T` truth terminal, `P` lift panel, `H` hatch exit, `!` laser hazard

```
########################################
#   [T] TRUTH TERMINAL                 #
#                                      #
#   [P] SPINE LIFT PANEL     [H] EXIT  #
#                                      #
#===========        ===================#
#      ! ! ! (low laser knockback)     #
#===========        ===================#
#   v (DOWN)                            #
########################################
```

---

# Flags (table-friendly)

* `has_cable_1`
* `has_cable_2`
* `has_jumper`
* `patch_ok` (or 3 booleans for each connection)
* `lift_power`
* `maglock_armed`
* `override_seal`
* `spine_lift_open`

---

# Fail & recovery (no softlocks)

* Wrong patching: nothing breaks, status stays RED; player can redo instantly.
* If player forgets a cable: it’s still in Room B, always retrievable.
* BLACK CARTRIDGE isn’t consumed; it remains usable for later narrative gates.

