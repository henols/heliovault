#pragma once
#include <stdint.h>

/* Auto-generated (or tool-provided) format header for TSET blobs.
   Keep this in sync with tilesetc.py. */

#define TSET_MAGIC_0 'T'
#define TSET_MAGIC_1 'S'
#define TSET_MAGIC_2 'E'
#define TSET_MAGIC_3 'T'
#define TSET_VERSION 1

#define TSET_HEADER_SIZE 17
#define TSET_RECORD_SIZE 12

/* Header field offsets (byte offsets into blob) */
#define TSET_HDR_OFS_VERSION     4
#define TSET_HDR_OFS_TILE_W      5
#define TSET_HDR_OFS_TILE_H      6
#define TSET_HDR_OFS_TILE_COUNT  7
#define TSET_HDR_OFS_REC_SIZE    8
#define TSET_HDR_OFS_RECORDS     9   /* uint16_t */
#define TSET_HDR_OFS_NAMES       11  /* uint16_t */
#define TSET_HDR_OFS_BG          13  /* uint8_t */
#define TSET_HDR_OFS_MC1         14  /* uint8_t */
#define TSET_HDR_OFS_MC2         15  /* uint8_t */

/* Record field offsets (byte offsets relative to record base) */
#define TSET_REC_OFS_ID          0
#define TSET_REC_OFS_CHARS       1
#define TSET_REC_OFS_COLOR_MODE  5
#define TSET_REC_OFS_COLORS      6
#define TSET_REC_OFS_FLAGS       10  /* uint16_t */

static inline uint8_t tset_rd8(const uint8_t* b, uint16_t o) {
    return b[o];
}
static inline uint16_t tset_rd16(const uint8_t* b, uint16_t o) {
    return (uint16_t)b[o] | ((uint16_t)b[o + 1] << 8);
}
