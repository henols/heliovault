// Provided by levelc.py
#pragma once
#include <stdint.h>

/* Auto-generated (or tool-provided) format header for LVL1 blobs.
   Keep this in sync with levelc.py. */

#define LVL_MAGIC_0 'L'
#define LVL_MAGIC_1 'V'
#define LVL_MAGIC_2 'L'
#define LVL_MAGIC_3 '1'
#define LVL_VERSION 1

#define LVL_HEADER_SIZE 22
#define LVL_ROOM_DIRENTRY_SIZE 8
#define LVL_OBJ_RECORD_SIZE 22

/* Header field offsets (byte offsets into blob) */
#define LVL_HDR_OFS_VERSION      4
#define LVL_HDR_OFS_ROOMCOUNT    5
#define LVL_HDR_OFS_MAPW         6
#define LVL_HDR_OFS_MAPH         7
#define LVL_HDR_OFS_FLAGCOUNT    8
#define LVL_HDR_OFS_VARCOUNT     9
#define LVL_HDR_OFS_ITEMCOUNT    10
#define LVL_HDR_OFS_MSGCOUNT     11
#define LVL_HDR_OFS_STARTROOM    12
#define LVL_HDR_OFS_STARTSPAWN   13
#define LVL_HDR_OFS_ROOMDIR      14
#define LVL_HDR_OFS_CONDSTREAM   16
#define LVL_HDR_OFS_ACTSTREAM    18
#define LVL_HDR_OFS_MSGTABLE     20

/* Object record field offsets (byte offsets relative to object record base) */
#define LVL_OBJ_OFS_X        0
#define LVL_OBJ_OFS_Y        1
#define LVL_OBJ_OFS_TYPE     2
#define LVL_OBJ_OFS_VERBS    3
#define LVL_OBJ_OFS_P0       4
#define LVL_OBJ_OFS_P1       5
#define LVL_OBJ_OFS_CONDS    6   /* uint16_t */
#define LVL_OBJ_OFS_LOOK     8   /* uint16_t */
#define LVL_OBJ_OFS_TAKE     10  /* uint16_t */
#define LVL_OBJ_OFS_USE      12  /* uint16_t */
#define LVL_OBJ_OFS_TALK     14  /* uint16_t */
#define LVL_OBJ_OFS_OPERATE  16  /* uint16_t */
#define LVL_OBJ_OFS_ALT0     18  /* uint16_t */
#define LVL_OBJ_OFS_ALT1     20  /* uint16_t */

/* Condition opcodes (bytecode triples [op,a,b]) */
#define C_END       0
#define C_TRUE      1
#define C_FLAG_SET  2
#define C_FLAG_CLR  3
#define C_HAS_ITEM  4
#define C_VAR_EQ    5

/* Action opcodes (bytecode triples [op,a,b]) */
#define A_END        0
#define A_SHOW_MSG   1
#define A_SET_FLAG   2
#define A_CLR_FLAG   3
#define A_GIVE_ITEM  4
#define A_TAKE_ITEM  5
#define A_SET_VAR    6
#define A_SFX        7
#define A_TRANSITION 8

/* Verbs bitmask */
#define VB_LOOK    (1<<0)
#define VB_TAKE    (1<<1)
#define VB_USE     (1<<2)
#define VB_TALK    (1<<3)
#define VB_OPERATE (1<<4)

/* Exits */
#define EXIT_L 0
#define EXIT_R 1
#define EXIT_U 2
#define EXIT_D 3

static inline uint8_t lvl_rd8(const uint8_t* b, uint16_t o) {
  return b[o];
}
static inline uint16_t lvl_rd16(const uint8_t* b, uint16_t o) {
  return (uint16_t)b[o] | ((uint16_t)b[o+1] << 8);
}

static inline uint16_t lvl_roomdir_ofs(const uint8_t* b) {
  return lvl_rd16(b, LVL_HDR_OFS_ROOMDIR);
}
static inline uint16_t lvl_condstream_ofs(const uint8_t* b) {
  return lvl_rd16(b, LVL_HDR_OFS_CONDSTREAM);
}
static inline uint16_t lvl_actstream_ofs(const uint8_t* b) {
  return lvl_rd16(b, LVL_HDR_OFS_ACTSTREAM);
}
static inline uint16_t lvl_msgtable_ofs(const uint8_t* b) {
  return lvl_rd16(b, LVL_HDR_OFS_MSGTABLE);
}

static inline uint16_t lvl_roomdir_entry_base(const uint8_t* b, uint8_t roomId) {
  return (uint16_t)(lvl_roomdir_ofs(b) + (uint16_t)roomId * LVL_ROOM_DIRENTRY_SIZE);
}

static inline uint16_t lvl_room_map_ofs(const uint8_t* b, uint8_t roomId) {
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 0);
}
static inline uint16_t lvl_room_spawns_ofs(const uint8_t* b, uint8_t roomId) {
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 2);
}
static inline uint16_t lvl_room_exits_ofs(const uint8_t* b, uint8_t roomId) {
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 4);
}
static inline uint16_t lvl_room_objects_ofs(const uint8_t* b, uint8_t roomId) {
  return lvl_rd16(b, lvl_roomdir_entry_base(b, roomId) + 6);
}

static inline uint8_t lvl_spawns_count(const uint8_t* b, uint16_t spawnsOfs) {
  return lvl_rd8(b, spawnsOfs);
}
static inline void lvl_spawn_xy(const uint8_t* b, uint16_t spawnsOfs, uint8_t idx, uint8_t* outX, uint8_t* outY) {
  uint16_t base = (uint16_t)(spawnsOfs + 1 + (uint16_t)idx * 2);
  *outX = lvl_rd8(b, base + 0);
  *outY = lvl_rd8(b, base + 1);
}

static inline uint8_t lvl_exits_count(const uint8_t* b, uint16_t exitsOfs) {
  return lvl_rd8(b, exitsOfs);
}
static inline void lvl_exit(const uint8_t* b, uint16_t exitsOfs, uint8_t idx, uint8_t* outType, uint8_t* outDestRoom, uint8_t* outDestSpawn) {
  uint16_t base = (uint16_t)(exitsOfs + 1 + (uint16_t)idx * 3);
  *outType = lvl_rd8(b, base + 0);
  *outDestRoom = lvl_rd8(b, base + 1);
  *outDestSpawn = lvl_rd8(b, base + 2);
}

static inline uint8_t lvl_objects_count(const uint8_t* b, uint16_t objsOfs) {
  return lvl_rd8(b, objsOfs);
}
static inline uint16_t lvl_object_base(const uint8_t* b, uint16_t objsOfs, uint8_t idx) {
  return (uint16_t)(objsOfs + 1 + (uint16_t)idx * LVL_OBJ_RECORD_SIZE);
}
