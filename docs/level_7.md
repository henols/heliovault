## Level 7 — **ROOF EGRESS: PROOF LAUNCH**

**Rooms:** 2 single-screen rooms
**Theme:** you finally see the outside—ORACLE can’t fully control it—so it tries one last “polite” lock. You don’t win by violence; you win by **sending the proof**.

**New mechanic (Level 7 introduces exactly one):** **Wind push zones**
Simple, readable: drifting gusts push the player left/right in marked lanes. No timers. No pixel-perfect jumps—just positioning and using a windbreak.

**Final goal:** Launch the **BLACK CARTRIDGE** in an **Outbound Capsule** and step through the **Street Hatch** (game end).

---

# Room graph (2 rooms)

* **Room A: Roof Catwalk**

  * Right → Room B (Capsule Tower)
* **Room B: Outbound Capsule Tower (Final)**

  * Left → Room A
  * Bottom/side hatch → “Outside” / end sequence

---

# Story beats (short, decisive)

**On entry (Room A):**

* ORACLE//9: `OUTSIDE AIR IS NOT CERTIFIED. RETURN INSIDE.`
* Background: neon skyline, distant arcology domes, monorail lights—**real world**.

**First time wind pushes you:**

* `WIND: STRONG`
* Sign: `USE WIND BREAKERS`

**When you reach the capsule tower console without a sealed capsule:**

* `CONSOLE: CAPSULE REQUIRED`

**When you load the black cartridge and seal the capsule:**

* ORACLE//9: `THAT DATA WILL CAUSE PANIC.`
* Player text (optional): `GOOD.`

**When you launch:**

* `LAUNCH CONFIRMED.`
* ORACLE//9: `...`
  (silence is the punchline)

**End hatch:**

* `HATCH: OPEN`
* Fade out.

---

# Core puzzle chain (clean, final, no filler)

### Gate 1 — Make a sealed capsule

* **Find:** **OUTBOUND CAPSULE SHELL** in Room A (near a windbreak box)
* **Find:** **SEAL RING** in Room B (in a service drawer)
* **Action:** USE **BLACK CARTRIDGE** on **CAPSULE SHELL** → becomes `CAPSULE (LOADED)`
* **Action:** USE **SEAL RING** on `CAPSULE (LOADED)` → becomes `SEALED CAPSULE`
* **Flags:** `capsule_loaded=1`, `capsule_sealed=1`

### Gate 2 — Reach the console through wind zones

* Wind lanes are **visual** (streamers, fog streaks).
* **Find:** **WIND BREAKER PANEL** (a portable shield you can OPERATE to raise/lower)
* In Room A, you learn the idea; in Room B you use it to cross the final gust lane.

Mechanically: two safe “alcoves” where wind doesn’t push. You move alcove-to-alcove; raise shield to cancel wind in one lane.

### Gate 3 — Launch and open the exit hatch

* **Action:** USE `SEALED CAPSULE` on **LAUNCH CHUTE**
* **Action:** OPERATE **LAUNCH CONSOLE**
* **Result:** `proof_launched=1`, ORACLE goes quiet, **STREET HATCH** unlocks.
* **Action:** OPERATE **STREET HATCH** → game ends.

---

# Room breakdowns

## Room A — **Roof Catwalk**

**Purpose:** reveal outside + introduce wind zones + provide capsule shell + teach windbreak.
**Look:** wet neon metal, antennae, warning beacons, skyline parallax, streamers indicating gust direction.

**Interactables (7–9):**

1. **OUTBOUND CAPSULE SHELL** (pickup) *(required)*
2. **WIND BREAKER PANEL** (raise/lower shield) *(teaches mechanic)*
3. **WIND SIGNAGE** (LOOK: explains lanes)
4. **ROOF ACCESS DOOR** (back to Level 6; optional, can be blocked)
5. **SAFETY LIGHTS** (flavor)
6. **GUST LANES** (environmental push zones)
7. Optional **LOG TAPE #07** (one last line)
8. Exit to Room B (right)

**Key text:**

* `TAKEN: CAPSULE SHELL`
* `WIND BREAKER: RAISED`
* `WIND BREAKER: LOWERED`
* `WIND: STRONG (EASTWARD)` (or whatever direction you pick and keep consistent)

---

## Room B — **Outbound Capsule Tower (Final)**

**Purpose:** seal + launch + end hatch, with a wind lane as the last navigation bite.
**Look:** tall tower machinery, huge pneumatic tube barrel, chunky console with “LAUNCH AUTH.”

**Interactables (8–10):**

1. **SERVICE DRAWER** (contains SEAL RING) *(required)*
2. **LAUNCH CHUTE** (insert sealed capsule) *(required)*
3. **LAUNCH CONSOLE** (operable only if capsule inserted) *(required)*
4. **WIND BREAKER ANCHOR** (a second shield spot for the final lane)
5. **STATUS LIGHTBAR** (READY / SEALED / LAUNCHED)
6. **ORACLE SPEAKER** (last lines, then silence)
7. **STREET HATCH PANEL** (unlocks after launch)
8. **STREET HATCH** (exit)

**Key text:**

* `TAKEN: SEAL RING`
* `CAPSULE: LOADED`
* `CAPSULE: SEALED`
* `CHUTE: CAPSULE INSERTED`
* `STATUS: READY`
* `LAUNCH CONFIRMED`
* `HATCH: OPEN`

---

# Sketches (2 rooms)

### Room A — Roof Catwalk

Legend: `#` wall, `P` spawn, `C` capsule shell, `W` windbreaker control, `>>>` wind push zone direction, `=` platform, `>` exit

```
########################################
#  SKYLINE / BEACONS / ANTENNAS        #
#                                      #
#  [C] CAPSULE SHELL     >>>>>>>>>     #
#                     >>>>>>>>>        #
#  [W] WIND BREAKER     >>>>>>>>>     >#
#                                      #
#===========        ===================#
#   safe alcove     safe alcove        #
########################################
```

### Room B — Outbound Capsule Tower (Final)

Legend: `<` return, `D` service drawer (seal ring), `H` windbreaker anchor, `O` console, `U` launch chute, `E` exit hatch, `>>>` wind lane

```
########################################
<   TOWER INTERIOR                     #
#                                      #
# [D] DRAWER      >>>>>>>>>   [H]      #
# (SEAL RING)   >>>>>>>>>             #
#                                      #
#              [U] LAUNCH CHUTE        #
#              [O] LAUNCH CONSOLE      #
#                        [E] STREET    #
#                        HATCH         #
########################################
```

---

# Flags (table-friendly)

* `has_capsule_shell`
* `has_seal_ring`
* `capsule_loaded`
* `capsule_sealed`
* `capsule_inserted`
* `proof_launched`
* `street_hatch_open`

---

# Final note (keeps the tone)

Don’t add a boss. Don’t add a timer. The climax is the **act of publishing truth**—and ORACLE’s only “attack” is trying to make the path feel annoying. The moment the capsule launches and the PA goes silent is your ending hit.
