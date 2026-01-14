#ifndef VIC_MEM_H
#define VIC_MEM_H

#include <stdint.h>

// VIC bank 1 ($4000-$7FFF) layout for screen/charset/sprites.
#define VIC_BANK_BASE 0x4000u
#define SCREEN_ADDR   0x4400u
#define CHARSET_ADDR  0x6000u
#define SPRITE_ADDR   0x7000u
#define SPRITE_PTR_ADDR (SCREEN_ADDR + 0x03F8u)
#define SPRITE_PTR_VALUE ((uint8_t)((SPRITE_ADDR - VIC_BANK_BASE) / 64u))

#endif
