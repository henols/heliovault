#include "room.h"
#include "render.h"
#include "level_runtime.h"

#include "level_format.h"

static uint8_t current_room_id = 0;
static uint8_t current_spawn_id = 0;
static const uint8_t* room_map = 0;
static uint16_t room_map_ofs = 0;
static uint16_t room_spawns_ofs = 0;
static uint16_t room_exits_ofs = 0;
static uint16_t room_objects_ofs = 0;

void room_load(unsigned char room_id) {
    room_load_with_spawn(room_id, 0);
}

void room_load_with_spawn(unsigned char room_id, unsigned char spawn_id) {
    const uint8_t* blob = level_get_blob();

    current_room_id = room_id;
    current_spawn_id = spawn_id;
    room_map_ofs = lvl_room_map_ofs(blob, room_id);
    room_spawns_ofs = lvl_room_spawns_ofs(blob, room_id);
    room_exits_ofs = lvl_room_exits_ofs(blob, room_id);
    room_objects_ofs = lvl_room_objects_ofs(blob, room_id);
    room_map = blob + room_map_ofs;
}

void room_render(void) {
    render_room();
}

const unsigned char* room_get_map(void) {
    return room_map;
}

unsigned char room_get_width(void) {
    return level_get_map_width();
}

unsigned char room_get_height(void) {
    return level_get_map_height();
}

unsigned char room_get_id(void) {
    return current_room_id;
}

unsigned char room_get_spawn_id(void) {
    return current_spawn_id;
}

unsigned char room_get_object_count(void) {
    const uint8_t* blob = level_get_blob();

    return lvl_objects_count(blob, room_objects_ofs);
}

unsigned short room_get_object_base(unsigned char obj_index) {
    const uint8_t* blob = level_get_blob();

    return lvl_object_base(blob, room_objects_ofs, obj_index);
}

unsigned char room_get_spawn_count(void) {
    const uint8_t* blob = level_get_blob();

    return lvl_spawns_count(blob, room_spawns_ofs);
}

void room_get_spawn_xy(unsigned char spawn_index, unsigned char* out_x, unsigned char* out_y) {
    const uint8_t* blob = level_get_blob();

    lvl_spawn_xy(blob, room_spawns_ofs, spawn_index, out_x, out_y);
}

unsigned char room_get_exit_count(void) {
    const uint8_t* blob = level_get_blob();

    return lvl_exits_count(blob, room_exits_ofs);
}

void room_get_exit(unsigned char exit_index, unsigned char* out_type, unsigned char* out_room, unsigned char* out_spawn) {
    const uint8_t* blob = level_get_blob();

    lvl_exit(blob, room_exits_ofs, exit_index, out_type, out_room, out_spawn);
}
