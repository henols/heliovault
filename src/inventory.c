#include "inventory.h"

enum {
    INVENTORY_MAX = 8
};

static uint8_t inventory_items[INVENTORY_MAX];
static uint8_t inventory_count = 0;

void inventory_init(void) {
    inventory_clear();
}

void inventory_clear(void) {
    inventory_count = 0;
}

uint8_t inventory_has(uint8_t item_id) {
    uint8_t i;

    for (i = 0; i < inventory_count; ++i) {
        if (inventory_items[i] == item_id) {
            return 1;
        }
    }
    return 0;
}

void inventory_add(ItemId item_id) {
    if (inventory_has(item_id)) {
        return;
    }
    if (inventory_count >= INVENTORY_MAX) {
        return;
    }
    inventory_items[inventory_count++] = item_id;
}

void inventory_remove(ItemId item_id) {
    uint8_t i;

    for (i = 0; i < inventory_count; ++i) {
        if (inventory_items[i] == item_id) {
            inventory_items[i] = inventory_items[inventory_count - 1];
            inventory_count--;
            return;
        }
    }
}
