#ifndef INVENTORY_H
#define INVENTORY_H

#include "common.h"

void inventory_init(void);
void inventory_clear(void);
uint8_t inventory_has(uint8_t item_id);
void inventory_add(uint8_t item_id);
void inventory_remove(uint8_t item_id);

#endif
