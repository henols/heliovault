# Binary Formats

This document describes the binary layouts produced by the toolchain.
For the authoritative offsets, see:

- `include/tileset_format.h` (TSET)
- `include/level_format.h` (LVL)

---

## TSET blob (`gen/assets/<name>.bin`)

Produced by `tools/tilesetc.py`.

### Header (17 bytes)

```
0x00  4  magic "TSET"
0x04  1  version (1)
0x05  1  tile_w
0x06  1  tile_h
0x07  1  tile_count
0x08  1  record_size (12)
0x09  2  ofs_records (u16)
0x0B  2  ofs_names (u16, unused)
0x0D  1  bg_color
0x0E  1  mc1_color
0x0F  1  mc2_color
0x10  1  reserved
```

### Record (12 bytes, repeated `tile_count`)

```
0x00  1  id
0x01  4  chars (TL, TR, BL, BR)
0x05  1  color_mode (0=single, 1=per-quadrant)
0x06  4  colors (if single, only colors[0] is used)
0x0A  2  flags (bitmask)
```

### Reading in code

Use helpers in `include/tileset_format.h`:

- `tset_rd8` / `tset_rd16`
- `TSET_HDR_OFS_*` and `TSET_REC_OFS_*`

---

## LVL blob (`gen/assets/levels/<level>.bin`)

Produced by `tools/levelc.py`.

### Header (22 bytes)

```
0x00  4  magic "LVL1"
0x04  1  version (1)
0x05  1  room_count
0x06  1  map_w
0x07  1  map_h
0x08  1  flag_count
0x09  1  var_count
0x0A  1  item_count
0x0B  1  msg_count
0x0C  1  start_room
0x0D  1  start_spawn
0x0E  2  ofs_room_dir (u16)
0x10  2  ofs_cond_stream (u16)
0x12  2  ofs_act_stream (u16)
0x14  2  ofs_msg_table (u16)
```

### Room directory (8 bytes per room)

Each entry contains 4 little-endian offsets:

```
ofs_map (u16)
ofs_spawns (u16)
ofs_exits (u16)
ofs_objects (u16)
```

### Map block

```
map_w * map_h bytes
row-major metatile IDs
```

### Spawns block

```
u8 count
repeated: u8 x, u8 y
```

### Exits block

```
u8 count
repeated: u8 edge, u8 dest_room, u8 dest_spawn
```

### Objects block (22 bytes per object)

```
u8 count
repeated record:
  u8 x
  u8 y
  u8 type
  u8 verbs
  u8 p0
  u8 p1
  u16 cond_ofs
  u16 look_ofs
  u16 take_ofs
  u16 use_ofs
  u16 talk_ofs
  u16 operate_ofs
  u16 alt0_ofs
  u16 alt1_ofs
```

### Condition stream

Bytecode stream of 3-byte instructions: `[op, a, b]`.
Terminated by `C_END`.

### Action stream

Bytecode stream of 3-byte instructions: `[op, a, b]`.
Terminated by `A_END`.

### Message table

```
u8 msg_count
u16[msg_count] offsets to null-terminated ASCII strings
```

### Reading in code

Use helpers in `include/level_format.h`:

- `lvl_rd8` / `lvl_rd16`
- `lvl_roomdir_ofs`, `lvl_room_map_ofs`, `lvl_room_objects_ofs`, etc.

---

## Generated C blobs

The toolchain emits C files that embed blobs at compile time:

- `gen/src/levels/<level>.c` for LVL
- `gen/src/tilesets/<name>_tset.c` and `gen/src/charset/<name>_charset.c` for TSET/charset

These expose:

- `<level>_blob` and `<level>_blob_size`
- `<name>_tset_blob` and `<name>_tset_blob_size`
- `<name>_charset_blob` and `<name>_charset_blob_size`
