#include "metatile.h"

enum {
    MT_EMPTY = 0,
    MT_WALL = 1,
    MT_COUNT
};

#define MT_FLAG_SOLID 0x01u

static uint8_t mt_flags_table[MT_COUNT] = {
    0,
    MT_FLAG_SOLID
};

static uint8_t mt_chars_table[MT_COUNT][4] = {
    {32, 32, 32, 32}, /* space */
    {35, 35, 35, 35}  /* '#' */
};

void metatile_init(void) {
}

uint8_t metatile_get_flags(uint8_t mt_id) {
    return mt_flags_table[mt_id];
}

const uint8_t* metatile_get_chars(uint8_t mt_id) {
    return mt_chars_table[mt_id];
}
