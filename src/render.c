#include "render.h"
#include "room.h"
#include "metatile.h"

#include <c64/charwin.h>

static CharWin screen_win;

static void render_write_char(uint8_t cx, uint8_t cy, uint8_t ch) {
    cwin_putat_char_raw(&screen_win, (char)cx, (char)cy, (char)ch, 1);
}

void render_init(void) {
    cwin_init(&screen_win, (char*)0x0400, 0, 0, 40, 25);
}

void render_room(void) {
    const uint8_t* map = room_get_map();
    uint8_t w = room_get_width();
    uint8_t h = room_get_height();
    uint8_t mx;
    uint8_t my;

    for (my = 0; my < h; ++my) {
        for (mx = 0; mx < w; ++mx) {
            uint8_t mt_id = map[(uint16_t)my * w + mx];
            render_metatile(mx, my, mt_id);
        }
    }
}

void render_metatile(uint8_t mx, uint8_t my, uint8_t mt_id) {
    const uint8_t* chars = metatile_get_chars(mt_id);
    uint8_t cx = mx * 2u;
    uint8_t cy = my * 2u;

    render_write_char(cx, cy, chars[0]);
    render_write_char((uint8_t)(cx + 1u), cy, chars[1]);
    render_write_char(cx, (uint8_t)(cy + 1u), chars[2]);
    render_write_char((uint8_t)(cx + 1u), (uint8_t)(cy + 1u), chars[3]);
}
