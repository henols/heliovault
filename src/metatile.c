#include "metatile.h"

#include "tileset_format.h"
#include "tilesets/BOOT_AUDIT1_tset-blob.h"
#include "tilesets/BOOT_AUDIT1_charset-blob.h"

#include <stddef.h>

static const uint8_t mt_default_chars[4] = {32, 32, 32, 32};
static const uint8_t mt_default_colors[4] = {1, 1, 1, 1};
static const uint8_t* mt_blob = BOOT_AUDIT1_tset_blob;
static const uint8_t* mt_charset_blob = BOOT_AUDIT1_charset_blob;
static uint32_t mt_charset_size = 0u;

static uint8_t metatile_blob_ok(const uint8_t* blob) {
    if (!blob) {
        return 0;
    }
    return blob[0] == TSET_MAGIC_0 &&
           blob[1] == TSET_MAGIC_1 &&
           blob[2] == TSET_MAGIC_2 &&
           blob[3] == TSET_MAGIC_3 &&
           tset_rd8(blob, TSET_HDR_OFS_VERSION) == TSET_VERSION;
} 

static const uint8_t* metatile_record(uint8_t mt_id) {
    uint16_t ofs_records;
    uint8_t rec_size;
    uint8_t count;
    const uint8_t* blob = mt_blob;

    if (!blob) {
        return 0;
    }

    count = tset_rd8(blob, TSET_HDR_OFS_TILE_COUNT);
    if (mt_id >= count) {
        return 0;
    }

    rec_size = tset_rd8(blob, TSET_HDR_OFS_REC_SIZE);
    if (rec_size < TSET_RECORD_SIZE) {
        return 0;
    }

    ofs_records = tset_rd16(blob, TSET_HDR_OFS_RECORDS);
    return blob + ofs_records + (uint16_t)mt_id * rec_size;
}

void metatile_init(void) {
    if (!metatile_blob_ok(mt_blob)) {
        mt_blob = NULL;
    }
    mt_charset_size = BOOT_AUDIT1_charset_blob_size;
    if (!mt_charset_blob || mt_charset_size == 0u) {
        mt_charset_blob = NULL;
        mt_charset_size = 0u;
    }
}

uint16_t metatile_get_flags(uint8_t mt_id) {
    const uint8_t* rec = metatile_record(mt_id);
    if (!rec) {
        return 0;
    }
    return tset_rd16(rec, TSET_REC_OFS_FLAGS);
}

const uint8_t* metatile_get_chars(uint8_t mt_id) {
    const uint8_t* rec = metatile_record(mt_id);
    if (!rec) {
        return mt_default_chars;
    }
    return rec + TSET_REC_OFS_CHARS;
}

uint8_t metatile_get_color_mode(uint8_t mt_id) {
    const uint8_t* rec = metatile_record(mt_id);
    if (!rec) {
        return 0;
    }
    return tset_rd8(rec, TSET_REC_OFS_COLOR_MODE);
}

const uint8_t* metatile_get_colors(uint8_t mt_id) {
    const uint8_t* rec = metatile_record(mt_id);
    if (!rec) {
        return mt_default_colors;
    }
    return rec + TSET_REC_OFS_COLORS;
}

uint8_t metatile_get_bg_color(void) {
    if (!mt_blob) {
        return 0;
    }
    return tset_rd8(mt_blob, TSET_HDR_OFS_BG);
}

uint8_t metatile_get_mc1_color(void) {
    if (!mt_blob) {
        return 0;
    }
    return tset_rd8(mt_blob, TSET_HDR_OFS_MC1);
}

uint8_t metatile_get_mc2_color(void) {
    if (!mt_blob) {
        return 0;
    }
    return tset_rd8(mt_blob, TSET_HDR_OFS_MC2);
}

const uint8_t* metatile_get_charset_blob(void) {
    return mt_charset_blob;
}

uint32_t metatile_get_charset_size(void) {
    return mt_charset_size;
}
