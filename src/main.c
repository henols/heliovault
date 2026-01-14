#include "common.h"
#include "irq.h"
#include "input.h"
#include "player.h"
#include "entity.h"
#include "collision.h"
#include "room.h"
#include "puzzle.h"
#include "inventory.h"
#include "menu.h"
#include "textbox.h"
#include "audio.h"
#include "level_runtime.h"
#include "metatile.h"
#include "render.h"

static void game_init(void) {
    kernal_irq_disable();
    // Temporarily disabled to isolate startup crash.
    // irq_init();
    input_init();
    inventory_init();
    puzzle_init();
    menu_init();
    textbox_init();
    audio_init();
    metatile_init();
    render_init();
    room_load_with_spawn(level_get_start_room(), level_get_start_spawn());
    room_render();
    player_init();
    entity_init();
}

static void game_tick(void) {
    input_poll();
    player_update();
    entity_update();
    collision_update();
    puzzle_update();
    menu_update();
    textbox_update();
    audio_update();
}

int main(void) {
    game_init();
    while (1) {
        game_tick();
    }
    return 0;
}
