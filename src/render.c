#include "render.h"
#include "room.h"
#include "metatile.h"
#include "vic_mem.h"

#include <c64/vic.h>
#include <c64/charwin.h>
#include <string.h>

static CharWin screen_win;
static uint8_t render_ready = 0;

#define VIC_CTRL2_ADDR 0xd016u
#define CIA2_PRA_ADDR  0xdd00u

static void render_load_charset(void) {
    const uint8_t* blob = metatile_get_charset_blob();
    uint32_t size = metatile_get_charset_size();
    uint8_t screen_index;
    uint8_t charset_index;
    uint8_t d018;
    volatile uint8_t* cia2_pra = (volatile uint8_t*)CIA2_PRA_ADDR;

    if (!blob || size < 2048u) {
        return;
    }

    *cia2_pra = (uint8_t)((*cia2_pra & 0xFCu) | 0x02u); // VIC bank 1 ($4000-$7FFF)

    memcpy((void*)CHARSET_ADDR, blob, 2048u);

    screen_index = (uint8_t)((SCREEN_ADDR - VIC_BANK_BASE) >> 10);  // / 0x400
    charset_index = (uint8_t)((CHARSET_ADDR - VIC_BANK_BASE) >> 11); // / 0x800
    d018 = (uint8_t)((screen_index << 4) | (charset_index << 1));
    *((volatile uint8_t*)0xd018u) = d018;
}

static void render_write_char(uint8_t cx, uint8_t cy, uint8_t ch, uint8_t color) {
    // Force multicolor per character cell (color RAM bit 3).
    cwin_putat_char_raw(&screen_win, (char)cx, (char)cy, (char)ch, (char)(color | 0x08u));
}

void render_init(void) {
    cwin_init(&screen_win, (char*)SCREEN_ADDR, 0, 0, 40, 25);
    render_load_charset();
    *(volatile uint8_t*)VIC_CTRL2_ADDR |= 0x10u; // Enable multicolor text mode.
    vic.color_back = metatile_get_bg_color();
    vic.color_back1 = metatile_get_mc1_color();
    vic.color_back2 = metatile_get_mc2_color();
    render_ready = 1;
}

void render_room(void) {
    const uint8_t* map = room_get_map();
    uint8_t w = room_get_width();
    uint8_t h = room_get_height();
    uint8_t mx;
    uint8_t my;

    if (!render_ready || !map || w == 0 || h == 0) {
        return;
    }
    if (w > (uint8_t)(screen_win.wx >> 1)) {
        w = (uint8_t)(screen_win.wx >> 1);
    }
    if (h > (uint8_t)(screen_win.wy >> 1)) {
        h = (uint8_t)(screen_win.wy >> 1);
    }

    for (my = 0; my < h; ++my) {
        for (mx = 0; mx < w; ++mx) {
            uint8_t mt_id = map[(uint16_t)my * w + mx];
            render_metatile(mx, my, mt_id);
        }
    }
    return;
}

void render_metatile(uint8_t mx, uint8_t my, uint8_t mt_id) {
    const uint8_t* chars = metatile_get_chars(mt_id);
    const uint8_t* colors = metatile_get_colors(mt_id);
    uint8_t color_mode = metatile_get_color_mode(mt_id);
    uint8_t cx = mx * 2u;
    uint8_t cy = my * 2u;
    uint8_t c0 = colors[0];
    uint8_t c1 = colors[1];
    uint8_t c2 = colors[2];
    uint8_t c3 = colors[3];

    if (!render_ready) {
        return;
    }
    if ((uint8_t)(cx + 1u) >= (uint8_t)screen_win.wx ||
        (uint8_t)(cy + 1u) >= (uint8_t)screen_win.wy) {
        return;
    }

    if (color_mode == 0) {
        c1 = c0;
        c2 = c0;
        c3 = c0;
    }

    render_write_char(cx, cy, chars[0], c0);
    render_write_char((uint8_t)(cx + 1u), cy, chars[1], c1);
    render_write_char(cx, (uint8_t)(cy + 1u), chars[2], c2);
    render_write_char((uint8_t)(cx + 1u), (uint8_t)(cy + 1u), chars[3], c3);
}
