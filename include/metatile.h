#ifndef METATILE_H
#define METATILE_H

#include "common.h"

void metatile_init(void);

uint8_t metatile_get_flags(uint8_t mt_id);
const uint8_t* metatile_get_chars(uint8_t mt_id);

#endif
