#ifndef LEVEL_RUNTIME_H
#define LEVEL_RUNTIME_H

#include "common.h"

void level_set_blob(const uint8_t* blob);
const uint8_t* level_get_blob(void);

uint8_t level_get_room_count(void);
uint8_t level_get_map_width(void);
uint8_t level_get_map_height(void);
uint8_t level_get_start_room(void);
uint8_t level_get_start_spawn(void);

const char* level_get_message(uint8_t msg_id);

#endif
