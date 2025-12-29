#include "level_runtime.h"

#include "levels/boot_audit-blob.h"
#include "level_format.h"

static const uint8_t* level_blob = boot_audit_blob;

void level_set_blob(const uint8_t* blob) {
    if (blob) {
        level_blob = blob;
    }
}

const uint8_t* level_get_blob(void) {
    return level_blob;
}

uint8_t level_get_room_count(void) {
    return lvl_rd8(level_blob, LVL_HDR_OFS_ROOMCOUNT);
}

uint8_t level_get_map_width(void) {
    return lvl_rd8(level_blob, LVL_HDR_OFS_MAPW);
}

uint8_t level_get_map_height(void) {
    return lvl_rd8(level_blob, LVL_HDR_OFS_MAPH);
}

uint8_t level_get_start_room(void) {
    return lvl_rd8(level_blob, LVL_HDR_OFS_STARTROOM);
}

uint8_t level_get_start_spawn(void) {
    return lvl_rd8(level_blob, LVL_HDR_OFS_STARTSPAWN);
}

const char* level_get_message(uint8_t msg_id) {
    uint16_t msg_table = lvl_msgtable_ofs(level_blob);
    uint8_t msg_count = lvl_rd8(level_blob, msg_table);
    uint16_t msg_ofs;

    if (msg_id >= msg_count) {
        return 0;
    }

    msg_ofs = lvl_rd16(level_blob, (uint16_t)(msg_table + 1u + (uint16_t)msg_id * 2u));
    return (const char*)(level_blob + msg_ofs);
}
