## Level 4 — **MUSEUM OF TOMORROW: CURATED TRUTH**

**Rooms:** 3 single-screen rooms (gallery hub + tube routing closet + archive service bay)
**Theme:** propaganda exhibits + your first hard proof item.
**New mechanic (Level 4 introduces exactly one):** **Pneumatic tube capsule routing** (put item in capsule → route → send → receive).

**Level goal:** Obtain the **BLACK CARTRIDGE** and unlock the **SPINE ELEVATOR** to Level 5.

---

# Room graph (3 rooms)

* **Room A (Hub): Gallery Atrium**

  * Left → Room B (Tube Routing Closet)
  * Right → Room C (Archive Service Bay)
  * Top hatch (exit) → locked (Spine Elevator)
* **Room B: Tube Routing Closet**

  * Right → Room A
* **Room C: Archive Service Bay**

  * Left → Room A

---

# Story beats (short, punchy)

**On load (Room A):**

* ORACLE//9: `WELCOME TO THE MUSEUM OF TOMORROW. HISTORY IS SAFETY.`
* Exhibit banner: `OUTSIDE IS CHAOS. INSIDE IS PROGRESS.`

**When you try the Spine Elevator early:**

* `ELEVATOR: PROOF MEDIA REQUIRED.`

**When you first enter Room C:**

* Sign: `ARCHIVE DRAWER OPENS ONLY ON TICKET DELIVERY (PNEU-TUBE).`
* ORACLE//9: `UNAUTHORIZED CURIOSITY DETECTED.`

**When you retrieve the black cartridge:**

* `TAKEN: BLACK CARTRIDGE`
* ORACLE//9: `THAT ITEM IS NOT FOR COURIERS.`

---

# Core puzzle chain (clue → action → state change)

### Gate 1 — Get a token to access the kiosk

* **Find:** **MUSEUM TOKEN** in Room B (obvious pickup on a shelf).
* **Use:** TOKEN on **EXHIBIT KIOSK** in Room A.
* **Result:** Kiosk powers up and prints **REQUEST TICKET**.
* **Flags:** `has_token=1`, `has_ticket=1`

### Gate 2 — You cannot carry paper into the archive

* Between Room A and C is a **MEDIA SCANNER ARCH**.
* If you attempt to enter C with the ticket:

  * `SCANNER: LOOSE MEDIA NOT PERMITTED.`
  * (Door stays locked until the ticket is not in your inventory.)
* This forces the new mechanic.

### Gate 3 — Tube-route the ticket to the archive

* **Action A (Room A):** Put **REQUEST TICKET** into **TUBE CAPSULE** at **TUBE STATION A**.
* **Action B (Room B):** Set **DIVERTER VALVES** to route **A → C** (simple two-switch pattern).
* **Action C (Room A):** OPERATE **SEND LEVER**.
* **Result (Room C):** Capsule arrives at **RECEIVER C**, ticket is consumed by receiver, and:

  * `ARCHIVE DRAWER: UNLOCKED.`
* **Flags:** `ticket_delivered=1`, `drawer_unlocked=1`

### Gate 4 — Retrieve proof and open the exit

* **Action (Room C):** OPERATE **ARCHIVE DRAWER** → TAKE **BLACK CARTRIDGE**.
* **Action (Room A):** USE **BLACK CARTRIDGE** on **SPINE ELEVATOR CONSOLE**.
* **Result:** Exit hatch unlocks.
* **Flags:** `has_black_cartridge=1`, `spine_unlocked=1`

---

# Room breakdowns

## Room A — **Gallery Atrium (Hub)**

**Purpose:** propaganda vibe + kiosk + tube station + level exit.
**Look:** glossy plastic tile, chrome trims, neon slogans, CRT exhibit loops, monorail poster art, “HAPPY TOMORROW” typography.

**Interactables (7–9):**

1. **EXHIBIT KIOSK** (prints REQUEST TICKET when token inserted)
2. **TUBE STATION A** (capsule insert/remove)
3. **SEND LEVER** (dispatch capsule)
4. **MEDIA SCANNER ARCH** (blocks carrying ticket into Room C)
5. **SPINE ELEVATOR CONSOLE** (requires black cartridge)
6. **SPINE ELEVATOR HATCH** (exit)
7. **PROPAGANDA EXHIBIT PANEL** (LOOK for flavor clue)
8. Optional **LOG TAPE #04** (lore)
9. Mild hazard: none (keep hub safe)

**Key text:**

* `KIOSK: INSERT TOKEN.`
* `PRINTED: REQUEST TICKET`
* `SCANNER: LOOSE MEDIA NOT PERMITTED.`
* `ELEVATOR: PROOF MEDIA REQUIRED.`

---

## Room B — **Tube Routing Closet**

**Purpose:** teach routing cleanly; contains token; contains valve clue.

**Interactables (6–8):**

1. **DIVERTER PANEL** (two toggles, labeled VALVE-1 / VALVE-2)
2. **TUBE MAP SIGN** (clue)
3. **MUSEUM TOKEN** (pickup)
4. Optional **SPARE CAPSULE FOAM** (pure decor)
5. Optional **CREDITS** pickup
6. Mild hazard: slow **piston vent** (knockback only) *optional*

**Routing logic (simple and readable):**

* Tube map shows:

  * `A→C = 1:UP  2:DOWN`
  * `A→B = 1:DOWN 2:UP`
  * (B→C not needed in this level)
* Player flips valves until panel display reads `ROUTE: A→C`.

**Key text:**

* `MAP: A→C = VALVE1 UP, VALVE2 DOWN`
* `ROUTE SET: A→C`

---

## Room C — **Archive Service Bay**

**Purpose:** pay-off room; drawer unlocks only after tube delivery.

**Interactables (6–8):**

1. **RECEIVER C** (accepts delivered ticket; triggers drawer unlock)
2. **ARCHIVE DRAWER** (contains BLACK CARTRIDGE)
3. **STATUS LIGHT** (LOCKED/UNLOCKED)
4. **SECURITY GLASS** (shows cartridge silhouette early to motivate)
5. Optional **“HISTORY EDIT” TERMINAL** (LOOK: creepy propaganda line)
6. Mild hazard: **moving laser line** near floor (knockback only) *optional*

**Key text:**

* Before delivery: `DRAWER: LOCKED. TICKET REQUIRED.`
* After delivery: `DRAWER: UNLOCKED.`
* `TAKEN: BLACK CARTRIDGE`

---

# Sketches (3 rooms)

### Room A — Gallery Atrium (Hub)

Legend: `#` wall, `P` spawn, `K` kiosk, `T` tube station, `S` send lever, `^` elevator exit, `E` elevator console, `| |` scanner arch, `<`/`>` exits

```
########################################
#      PROPAGANDA WALL     [^] EXIT    #
#                         [E] CONSOLE  #
#                                      #
#   [K] KIOSK           | | SCANNER | |#
#                       | |         | |#
#   P                                  #
#===========        ===================#
#   [T] TUBE   [S] SEND                #
#                                      #
<                                      >
########################################
```

### Room B — Tube Routing Closet

Legend: `V` diverter panel, `M` map sign, `O` token pickup

```
########################################
#   [M] TUBE MAP                        #
#                                      #
#                [V] DIVERTER PANEL    #
#                VALVE1 / VALVE2       #
#                                      #
#   [O] MUSEUM TOKEN                    #
#===========        ===================#
#                                      #
#                                      #
>                                      #
########################################
```

### Room C — Archive Service Bay

Legend: `R` receiver, `D` drawer, `G` glass, `L` laser hazard

```
########################################
<   [G] GLASS: "THE FUTURE IS SAFE"    #
#                                      #
#   [R] RECEIVER C       [D] DRAWER    #
#                     STATUS: LOCK/UNL #
#                                      #
#===========        ===================#
#      L  L  L (moving laser)          #
#                                      #
#======================================#
########################################
```

---

# Flags (table-friendly)

* `has_token`
* `has_ticket`
* `ticket_delivered`
* `drawer_unlocked`
* `has_black_cartridge`
* `spine_unlocked`

---

# Why this level works

* Forces one new mechanic (tube routing) without turning into a systems maze.
* Propaganda setting pays off narratively with a **physical proof object**.
* No softlocks: valves can be flipped forever; ticket can be reprinted if lost (kiosk can reprint once token is used and the flag is set).

Optional: Level 5 can be the **Spine** as a vertical 4–5 room climb where ORACLE starts actively reshaping routes—but still puzzle-first, not combat.
