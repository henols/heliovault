#ifndef METATILE_H
#define METATILE_H

#include "common.h"

void metatile_init(void);

uint16_t metatile_get_flags(uint8_t mt_id);
const uint8_t* metatile_get_chars(uint8_t mt_id);
uint8_t metatile_get_color_mode(uint8_t mt_id);
const uint8_t* metatile_get_colors(uint8_t mt_id);
uint8_t metatile_get_bg_color(void);
uint8_t metatile_get_mc1_color(void);
uint8_t metatile_get_mc2_color(void);
const uint8_t* metatile_get_charset_blob(void);
uint32_t metatile_get_charset_size(void);

#endif
