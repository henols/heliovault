**GOAL**
Create ONE densely packed **PIXEL ART TEXTURE ATLAS (GRID SHEET)** in a strict 2D side-view.
The image must be a collection of isolated assets that condenses ALL required objects and tiles into this single image (20x12 grid).

**WORKFLOW (must follow this order)**
1. Read the provided level documentation to identify ALL unique object types, hazards, wall tiles, and decor.
2. Create and render the "Texture Atlas," placing every unique element into the grid cells **separately**.
3. After the image is complete, generate JSON for the grid mapping.

**ATLAS LAYOUT RULES**
* **Separation:** Do NOT build a connected scene or room. Treat every grid cell (or block of cells) as a separate file.
* **Zero Spacing:** Pack objects tightly, edge-to-edge. Do **NOT** leave empty buffer space between different objects.
* **Grid Usage:** Maximize the use of the 20x12 grid. Fill every available slot with assets.
* **Mandatory Inclusions:** Include at least one instance of **EVERY** object type, interactable, and surface variation listed in the text.
* **Prioritization:** If space is limited, prioritize unique interactable objects and hazards over generic background tiles.

**PIXEL ART STYLE REQUIREMENTS (hard)**
* **Perspective:** Strictly **orthographic 2D side-view**.
    * The image must look like a flat platformer tile set.
    * Do NOT render side walls, floor depth, ceiling depth, or 3D perspective.
    * The back wall is perfectly parallel to the screen.
* **Color Quantization:** Hard-edge color assignment only.
    * No anti-aliasing, no alpha transparency, and no soft color blending.
* **Shading:** Use **dithered gradients** (Bayer or checkerboard patterns) for lighting transitions.
    * Do NOT create new intermediate colors to bridge shades.
* **Surface Detail:** Every asset must use multi-tone shading and texture; no large flat fills. Use clustered pixel shading, bevels, grime, scratches, and decals.
* **Palette Enforcement:** Use ONLY this palette (no other colors allowed). If a shadow or highlight is needed, snap it to the nearest allowed color:
    #000000, #626262, #898989, #adadad, #ffffff, #9f4e44, #cb7e75, #6d5412, #a1683c, #c9d487, #9ae29b, #5cab5e, #6abfc6, #887ecb, #50459b, #a057a3

**IMAGE RATIO + BLACK PADDING (critical)**
* Final image aspect ratio: exactly 20 : 12.5 (1.6).
* Bottom 4% is solid #000000 padding; nothing touches it.

**GRID LOGIC (Strict Sizing)**
* The top 96% of the image is the asset area: 20 columns × 12 rows.
* **DEFAULT SIZE (1x1):** You must attempt to fit every object into a **single 1x1 grid square**.
* **EXPANSION RULES:** Only expand an object's footprint if it is physically impossible to represent it in 1x1 (e.g., a tall boss, a long bridge).
* **Allowed Footprints:**
    * **Standard:** 1x1 (Most preferred)
    * **Tall:** 1x2, 1x3
    * **Wide:** 2x1, 3x1
    * **Block:** 2x2
* **Strict Packing:** Object A at (0,0) and Object B at (1,0) should be visually distinct assets, even though they touch.
* Assets must be centered in their assigned footprint.

**FLAGS (ONLY these are allowed in JSON)**
SOLID, DECOR, STANDABLE, LADDER, DOOR, INTERACTABLE, FLOOR, HAZARD

**OUTPUTS (must output BOTH, in order)**
1. Output the PNG image directly (visible in the response).
2. Output ONE JSON code block (strict JSON, no comments, no trailing commas).

**JSON REQUIREMENTS**
* The grid is 20×12.
* **Object Isolation:** Even if pixels touch in the image, the JSON must define them as separate entries in `objects[]` or `cells[]`.
* **Objects:** Interactive elements, props, and enemies go in `objects[]`.
* **Cells:** Static terrain tiles (walls, floors) go in `cells[]`.
* Each entry must have:
    * x, y (grid coordinate)
    * w, h (dimensions matching the allowed footprints: 1, 2, or 3)
    * flags (subset of allowed flags)
    * description (short and specific)

**JSON FORMAT**
```json
{
  "cells": [
    { "x": 0, "y": 0, "w": 1, "h": 1, "flags": ["SOLID", "FLOOR"], "description": "Standard concrete floor tile" }
  ],
  "objects": [
    { "id": "O1", "type": "<object type>", "x": 1, "y": 0, "w": 1, "h": 1, "flags": ["INTERACTABLE"], "description": "Small medical kit" },
    { "id": "O2", "type": "<object type>", "x": 2, "y": 0, "w": 1, "h": 3, "flags": ["HAZARD"], "description": "Tall electric pylon (expanded height)" }
  ]
}