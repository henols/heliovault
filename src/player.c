#include "player.h"

#include "input.h"
#include "room.h"
#include "metatile.h"
#include "vic_mem.h"
#include "tile_flags.h"
#include "level_format.h"
#include "npc_sprites_mc.h"

#include <c64/sprites.h>
#include <c64/vic.h>

static const uint8_t* const player_sprite_src = npc_tech;
static const uint16_t player_sprite_addr = SPRITE_ADDR;
static const uint8_t player_sprite_index = SPRITE_PTR_VALUE;
static uint8_t* const sprite_ptrs = (uint8_t*)SPRITE_PTR_ADDR;

static const uint8_t sprite_offset_x = 24;
static const uint8_t sprite_offset_y = 50;

static uint8_t player_x = 0;
static uint8_t player_y = 0;
static uint8_t player_inited = 0;

static void player_sprite_init(void) {
    uint8_t i;
    uint8_t* dst = (uint8_t*)player_sprite_addr;

    for (i = 0; i < 64; ++i) {
        dst[i] = player_sprite_src[i];
    }

    spr_init((char*)SCREEN_ADDR);
    sprite_ptrs[0] = player_sprite_index;
    vic.spr_mcolor0 = NPC_MC0_COLOR;
    vic.spr_mcolor1 = NPC_MC1_COLOR;
    spr_set(0, 1, 0, 0, player_sprite_index, NPC_TECH_COLOR, 1, 0, 0);
}

static void player_sprite_move(uint8_t mx, uint8_t my) {
    uint16_t px = (uint16_t)mx * 16u + sprite_offset_x;
    uint16_t py = (uint16_t)my * 16u + sprite_offset_y;

    spr_move(0, (int)px, (int)py);
}

static void player_place_at_spawn(void) {
    uint8_t sx = 0;
    uint8_t sy = 0;
    uint8_t spawn_id = room_get_spawn_id();
    room_get_spawn_xy(spawn_id, &sx, &sy);
    player_x = sx;
    player_y = sy;
}

static uint8_t map_is_solid(uint8_t mx, uint8_t my) {
    const uint8_t* map = room_get_map();
    uint8_t w = room_get_width();
    uint8_t h = room_get_height();
    uint8_t mt_id;
    uint16_t flags;

    if (!map || mx >= w || my >= h) {
        return 1;
    }
    mt_id = map[(uint16_t)my * w + mx];
    flags = metatile_get_flags(mt_id);
    return (flags & TF_SOLID) ? 1 : 0;
}

static uint8_t try_exit(uint8_t edge) {
    uint8_t i;
    uint8_t count = room_get_exit_count();
    for (i = 0; i < count; ++i) {
        uint8_t type;
        uint8_t dest_room;
        uint8_t dest_spawn;
        room_get_exit(i, &type, &dest_room, &dest_spawn);
        if (type == edge) {
            room_load_with_spawn(dest_room, dest_spawn);
            room_render();
            player_place_at_spawn();
            player_sprite_move(player_x, player_y);
            return 1;
        }
    }
    return 0;
}

void player_init(void) {
    player_sprite_init();
    player_place_at_spawn();
    player_sprite_move(player_x, player_y);
    player_inited = 1;
}

void player_update(void) {
    int8_t dx = 0;
    int8_t dy = 0;
    uint8_t next_x;
    uint8_t next_y;
    uint8_t w;
    uint8_t h;

    if (!player_inited) {
        player_init();
        return;
    }

    if (input_pressed & INPUT_LEFT) {
        dx = -1;
    } else if (input_pressed & INPUT_RIGHT) {
        dx = 1;
    } else if (input_pressed & INPUT_UP) {
        dy = -1;
    } else if (input_pressed & INPUT_DOWN) {
        dy = 1;
    } else {
        return;
    }

    w = room_get_width();
    h = room_get_height();

    next_x = (uint8_t)(player_x + dx);
    next_y = (uint8_t)(player_y + dy);

    if (dx < 0 && player_x == 0) {
        if (try_exit(EXIT_L)) {
            return;
        }
        return;
    }
    if (dx > 0 && player_x + 1 >= w) {
        if (try_exit(EXIT_R)) {
            return;
        }
        return;
    }
    if (dy < 0 && player_y == 0) {
        if (try_exit(EXIT_U)) {
            return;
        }
        return;
    }
    if (dy > 0 && player_y + 1 >= h) {
        if (try_exit(EXIT_D)) {
            return;
        }
        return;
    }

    if (map_is_solid(next_x, next_y)) {
        return;
    }

    player_x = next_x;
    player_y = next_y;
    player_sprite_move(player_x, player_y);
}
