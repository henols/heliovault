#ifndef TILE_FLAGS_H
#define TILE_FLAGS_H

#include <stdint.h>

/* Fixed tile flags (u16 mask) */
#define TF_SOLID        (1u << 0)
#define TF_DECOR        (1u << 1)
#define TF_STANDABLE    (1u << 2)
#define TF_LADDER       (1u << 3)
#define TF_DOOR         (1u << 4)
#define TF_INTERACTABLE (1u << 5)
#define TF_FLOOR        (1u << 6)
#define TF_HAZARD       (1u << 7)

#endif
