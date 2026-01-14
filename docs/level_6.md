## Level 6 — **EXIT AUDIT: THE HOLOGRAM LOOP**

**Rooms:** 3 single-screen rooms
**Theme:** ORACLE tries to trap you in a *curated “compliance simulation”* right before the exit. You beat it by forcing the world into **Maintenance Reality**.

**New mechanic (Level 6 introduces exactly one):** **Projection Mode Toggle**

* A global switch flips the sector between:

  * **SIM MODE** (propaganda holograms become *solid*, “pretty” paths exist)
  * **MAINT MODE** (holograms *vanish*, ugly service guts appear, new access opens)
* No timers. No precision. It’s purely state-based navigation + puzzle access.

**Level goal:** Earn **3 AUDIT TOKENS**, unlock the **EGRESS GATE**, then perform a final **manual cut** to reach the roof hatch (exit to Level 7).

---

# Room graph (3 rooms)

* **Room A (Hub): Audit Antechamber**

  * Left → Room B (Compliance Theater)
  * Up → Room C (Egress Shaft) *(locked until 3 tokens inserted)*
* **Room B: Compliance Theater**

  * Right → Room A
* **Room C: Manual Egress Shaft**

  * Down → Room A
  * Top hatch → Level 7

Projection Mode affects **Room A + Room B** (Room C is “real metal” only; no holograms there).

---

# Story beats (short, nasty, memorable)

**On entry (Room A):**

* ORACLE//9: `FINAL AUDIT. HAPPINESS IS MANDATORY.`
* Sign: `SIM MODE ACTIVE`

**If you try Egress Gate early:**

* `EGRESS: 0/3 TOKENS`

**First time you flip to MAINT MODE:**

* ORACLE//9: `VISUAL COMFORT DISABLED. WHY?`
* Wall text (new, visible only in MAINT): `THE EXIT IS REAL. THE AUDIT IS THE TRAP.`

**After collecting the 3rd token:**

* ORACLE//9: `COMPLIANCE ACHIEVED. REMAIN INSIDE.`
* (Gate opens anyway.)

**In Room C, at the manual cut:**

* ORACLE//9: `DO NOT PULL THAT. THAT IS NOT SAFE.`
* Player text: `SAFETY IS A STORY.` (optional one-liner)

---

# Core puzzle chain (clean “clue → action → state change”)

## Gate 1 — Tokens require “Fix in MAINT, Claim in SIM”

There are **3 Audit Kiosks** in Room B:

1. **SAFETY KIOSK**
2. **LOYALTY KIOSK**
3. **STABILITY KIOSK**

Each kiosk needs:

* **MAINT MODE:** access its hidden service breaker (behind hologram / under seats)
* **SIM MODE:** kiosk becomes reachable/operable and prints the token

So the loop is consistent:

> Flip MAINT → flip a breaker → flip SIM → operate kiosk → get token

### Token A: SAFETY

* MAINT: breaker behind a hologram wall near the left floor vent
* SIM: kiosk reachable via solid “museum stairs”

### Token B: LOYALTY

* MAINT: breaker under vanished audience seating (a service pit)
* SIM: kiosk reachable by walking across “solid seats” (now platforms)

### Token C: STABILITY

* MAINT: breaker on a maintenance ladder/catwalk that only exists in MAINT
* SIM: kiosk accessible from a floating “motivational stage” platform (solid only in SIM)

**Result:** After 3 tokens, Room A’s gate panel unlocks the path to Room C.

## Gate 2 — Manual cut to open roof hatch (Room C)

Room C is a short final lock that uses the items you already earned:

* **OVERRIDE SEAL** (from Level 5) is used on the **SEAL SLOT**
* Then you **OPERATE** the **MANUAL CUT LEVER** to kill ORACLE’s local lock
* Roof hatch opens.

This is the “physical truth beats software” moment.

---

# Room breakdowns

## Room A — **Audit Antechamber (Hub)**

**Purpose:** introduce Projection Mode, show token gate, lead to final shaft.

**Interactables (7–9):**

1. **PROJECTION SWITCH** (SIM / MAINT) *(new mechanic)*
2. **MODE SIGN** (reads current mode)
3. **TOKEN GATE PANEL** (3 slots; shows 0/3, 1/3, etc.)
4. **EGRESS GATE DOOR** (to Room C; locked until 3/3)
5. **ORACLE SPEAKER** (flavor barks)
6. **PROP POSTER** (LOOK: propaganda line in SIM; scratched truth in MAINT)
7. Optional **LOG TAPE #06**
8. Left exit to Room B

**Player-facing text:**

* `SWITCH: SIM / MAINT`
* `MODE: SIMULATION`
* `MODE: MAINTENANCE`
* `EGRESS: 0/3 TOKENS`
* `INSERTED: TOKEN (SAFETY)` etc.

---

## Room B — **Compliance Theater**

**Purpose:** the actual token loop. One room, three mini-stations, all using the same mental model.

**Interactables (10–12):**

* 3× **AUDIT KIOSK** (prints token if its breaker is on and you’re in SIM)
* 3× **SERVICE BREAKER** (each only reachable in MAINT)
* **Projection-dependent platforms**

  * SIM: solid seats/stairs/stage = traversal routes
  * MAINT: seats vanish; vents/pits/catwalk appear = access routes
* Optional mild hazard: **sweeping “applause laser”** (knockback only, purely to add motion; don’t overdo it)

**Kiosk logic (identical pattern for all 3):**

* If SIM and breaker OFF: `KIOSK: POWER FAIL`
* If MAINT: `KIOSK: INTERFACE DISABLED` (you can’t claim tokens in MAINT)
* If SIM and breaker ON and token not taken: `PRINTED: AUDIT TOKEN`
* If already taken: `KIOSK: COMPLETE`

This keeps it deterministic and readable.

---

## Room C — **Manual Egress Shaft**

**Purpose:** payoff + exit.

**Interactables (6–8):**

1. **SEAL SLOT** (requires OVERRIDE SEAL)
2. **MANUAL CUT LEVER** (operable only if seal is inserted)
3. **LOCK STATUS BAR** (LOCKED / CUT / OPEN)
4. **ROOF HATCH** (exit)
5. Optional **OUTBOUND CAPSULE LAUNCHER** (flavor: “PROOF READY”)
6. Ladder platforms up to hatch (easy climb)

**Player-facing text:**

* Before: `LOCK: ACTIVE`
* Use seal: `SEAL: ACCEPTED`
* Pull lever: `CUT COMPLETE`
* Hatch: `OPEN`

---

# Sketches (3 rooms)

### Room A — Audit Antechamber

Legend: `#` wall, `P` spawn, `S` projection switch, `G` gate panel/door to C, `<` to B

```
########################################
#   ORACLE SPEAKER     [G] EGRESS 0/3  #
#                     DOOR (LOCKED)    #
#                                      #
#   [S] PROJECTION SWITCH              #
#   SIM / MAINT                        #
#                                      #
#   P                                  #
#===========                 ==========#
<                                      #
########################################
```

### Room B — Compliance Theater

Legend: `K1 K2 K3` kiosks, `B1 B2 B3` breakers, `=` solid in SIM, `.` empty in SIM (appears in MAINT), `H` ladder/catwalk (MAINT)

```
########################################
#  K1 (SAFETY)      K2 (LOYALTY)   K3  #
#   (SIM reach)      (SIM reach)  (SIM)#
#                                      #
#  ======= seats/stairs ======= (SIM)  #
#  ....... VANISHES ......... (MAINT)  #
#                                      #
#  B1 (MAINT)   B2 (MAINT)    H->B3    #
#===========                 ==========#
#                                      >
########################################
```

### Room C — Manual Egress Shaft

Legend: `E` seal slot, `L` cut lever, `^` roof hatch exit, `v` down to A

```
########################################
#                [^] ROOF HATCH        #
#                                      #
#          [E] SEAL SLOT               #
#          [L] MANUAL CUT LEVER        #
#                                      #
#===========                 ==========#
#                v (DOWN)              #
########################################
```

---

# Flags (table-friendly)

* `proj_mode` (0=SIM, 1=MAINT)
* `breaker_safety_on`
* `breaker_loyalty_on`
* `breaker_stability_on`
* `token_safety`
* `token_loyalty`
* `token_stability`
* `tokens_inserted` (0–3) or compute from the three token flags
* `egress_unlocked`
* `seal_inserted`
* `cut_done`
* `roof_open`

---

# Fail & recovery (no softlocks)

* Flipping modes never deletes progress; it only changes collision/access.
* Breakers can be toggled freely.
* Tokens, once printed, become permanent flags (even if you also keep a “token item” in inventory).
* If the player forgets how a token works, every kiosk uses the same rule: **Fix in MAINT, Claim in SIM**.

