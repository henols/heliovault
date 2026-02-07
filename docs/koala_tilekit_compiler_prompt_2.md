You will be given text describing a game level, art direction, and world details.

**GOAL**
Create ONE attractive, playful PIXEL ART GAME LEVEL MAP (CROSS-SECTION) in a strict 2D side-view. The image must be a **"showroom" view** that condenses ALL rooms, areas, and objects described in the level text into this single contiguous image (20x12 grid), regardless of their original spatial distance.

**WORKFLOW (must follow this order)**

1. Read the provided level documentation to identify ALL rooms, areas, story beats, and required object types.
2. Create and render the "showroom" level map, condensing all described rooms and elements into the single image frame with high material detail and layered lighting.
3. After the image is complete, generate JSON for the grid.

**LEVEL CONTENT RULES**

* **Showroom Composition:** You must fit **ALL** rooms and areas described in the text into this single view. Condense empty space (like long hallways) to ensure every distinct interactive element, platform, and prop fits within the 20 columns.
* **Mandatory Inclusions:** Include at least one instance of **EVERY** object type listed in the level description.
* **Environment:** Include walls, floor, ceiling, ladders, raised platforms, doors, hazard areas, and rich background decor as described in the text.
* **Completeness:** If the text describes a start room and an end room, both must be visible and connected in this image.

**PIXEL ART STYLE REQUIREMENTS (hard)**

* **Perspective:** Strictly **orthographic 2D side-view**. The image must look like a flat platformer game level (tile-based). Do NOT render side walls, floor depth, ceiling depth, or 3D perspective. The back wall is perfectly parallel to the screen.
* **Color Quantization:** Hard-edge color assignment only. No anti-aliasing, no alpha transparency, and no soft color blending.
* **Shading:** Use **dithered gradients** (Bayer or checkerboard patterns) for lighting transitions. Do NOT create new intermediate colors to bridge shades.
* **Surface Detail:** Every large surface must use multi-tone shading and texture; no large flat fills. Use clustered pixel shading, bevels, grime, scratches, and decals.
* **Silhouettes:** Broken up with greebles, vents, cables, signage frames, and protrusions.
* **Palette Enforcement:** Use ONLY this palette (no other colors allowed). If a shadow or highlight is needed, snap it to the nearest allowed color:
#000000
#626262
#898989
#adadad
#ffffff
#9f4e44
#cb7e75
#6d5412
#a1683c
#c9d487
#9ae29b
#5cab5e
#6abfc6
#887ecb
#50459b
#a057a3

**IMAGE RATIO + BLACK PADDING (critical)**

* Final image aspect ratio: exactly 20 : 12.5 (1.6).
* Bottom 4% is solid #000000 padding; nothing touches it.

**GRID LOGIC (grid is invisible; do not draw it)**

* The top 96% of the image is the gameplay area: 20 columns × 12 rows.
* The grid is ONLY for logical mapping (JSON). It should NOT make the art look blocky.
* Each object has a footprint of 1×1, 1×2, 2×1, or 2×2 cells.
* Inside its footprint, object art may be irregular and non-rectilinear.
* Background decor may overlap visually but must map cleanly to one cell footprint each.
* The footprint must be unambiguous for JSON even if art edges are irregular.

**FLAGS (ONLY these are allowed in JSON)**
SOLID, DECOR, STANDABLE, LADDER, DOOR, INTERACTABLE, FLOOR, HAZARD

**OUTPUTS (must output BOTH, in order)**

1. Output the PNG image directly (visible in the response).
2. Output ONE JSON code block (strict JSON, no comments, no trailing commas).

**JSON REQUIREMENTS**

* The grid is 20×12.
* Any square covered by an object footprint appears only in objects[].
* All remaining squares appear in cells[].
* Each cell entry must have:
x, y (grid coordinate), w=1, h=1
flags (subset of allowed flags)
description (short and specific)
* If a square is walkable, include FLOOR and STANDABLE.
* If a square is blocking, include SOLID.
* If a square is background-only detail, include DECOR.

**JSON FORMAT**

```json
{
  "cells": [
    { "x": 0, "y": 0, "w": 1, "h": 1, "flags": ["DECOR"], "description": "..." }
  ],
  "objects": [
    { "id": "O1", "type": "<object type from provided text>", "x": 10, "y": 6, "w": 1, "h": 2, "flags": ["INTERACTABLE"], "description": "..." }
  ]
}

```

**HARD VALIDATION**

* Ratio and padding rules must be exact.
* **Perspective must be completely flat (no 2.5D depth).**
* **No unauthorized colors; hard edges only.**
* Every object type from the text appears in objects[] and is visible in the art.
* The image must contain ALL rooms/areas described in the level text, condensed into the single view.
* Footprints follow allowed sizes; silhouettes can be irregular inside footprints.
