#include "puzzle.h"

#include "inventory.h"
#include "level_runtime.h"
#include "room.h"
#include "textbox.h"

#include "level_format.h"

enum {
    PUZZLE_MAX_FLAGS = 256,
    PUZZLE_MAX_VARS = 64,
    PUZZLE_FLAG_BYTES = PUZZLE_MAX_FLAGS / 8
};

static uint8_t puzzle_flags[PUZZLE_FLAG_BYTES];
static uint8_t puzzle_vars[PUZZLE_MAX_VARS];
static uint8_t puzzle_flag_count = 0;
static uint8_t puzzle_var_count = 0;

static void puzzle_clear_state(void) {
    uint16_t i;

    for (i = 0; i < PUZZLE_FLAG_BYTES; ++i) {
        puzzle_flags[i] = 0;
    }
    for (i = 0; i < PUZZLE_MAX_VARS; ++i) {
        puzzle_vars[i] = 0;
    }
}

void puzzle_init(void) {
    const uint8_t* blob = level_get_blob();

    puzzle_flag_count = lvl_rd8(blob, LVL_HDR_OFS_FLAGCOUNT);
    puzzle_var_count = lvl_rd8(blob, LVL_HDR_OFS_VARCOUNT);

    if (puzzle_flag_count > PUZZLE_MAX_FLAGS) {
        puzzle_flag_count = PUZZLE_MAX_FLAGS;
    }
    if (puzzle_var_count > PUZZLE_MAX_VARS) {
        puzzle_var_count = PUZZLE_MAX_VARS;
    }

    puzzle_clear_state();
}

void puzzle_update(void) {
}

unsigned char puzzle_flag_get(unsigned char flag_id) {
    if (flag_id >= puzzle_flag_count) {
        return 0;
    }
    return (puzzle_flags[flag_id >> 3] >> (flag_id & 7u)) & 1u;
}

void puzzle_flag_set(unsigned char flag_id) {
    if (flag_id >= puzzle_flag_count) {
        return;
    }
    puzzle_flags[flag_id >> 3] |= (uint8_t)(1u << (flag_id & 7u));
}

void puzzle_flag_clear(unsigned char flag_id) {
    if (flag_id >= puzzle_flag_count) {
        return;
    }
    puzzle_flags[flag_id >> 3] &= (uint8_t)~(1u << (flag_id & 7u));
}

unsigned char puzzle_var_get(unsigned char var_id) {
    if (var_id >= puzzle_var_count) {
        return 0;
    }
    return puzzle_vars[var_id];
}

void puzzle_var_set(unsigned char var_id, unsigned char value) {
    if (var_id >= puzzle_var_count) {
        return;
    }
    puzzle_vars[var_id] = value;
}

unsigned char puzzle_conditions_pass(unsigned short cond_ofs) {
    const uint8_t* blob = level_get_blob();
    uint16_t base;

    if (cond_ofs == 0) {
        return 1;
    }

    base = (uint16_t)(lvl_condstream_ofs(blob) + cond_ofs);

    for (;;) {
        uint8_t op = lvl_rd8(blob, base + 0);
        uint8_t a = lvl_rd8(blob, base + 1);
        uint8_t b = lvl_rd8(blob, base + 2);

        base = (uint16_t)(base + 3u);

        switch (op) {
            case C_END:
                return 1;
            case C_TRUE:
                break;
            case C_FLAG_SET:
                if (!puzzle_flag_get(a)) {
                    return 0;
                }
                break;
            case C_FLAG_CLR:
                if (puzzle_flag_get(a)) {
                    return 0;
                }
                break;
            case C_HAS_ITEM:
                if (!inventory_has(a)) {
                    return 0;
                }
                break;
            case C_VAR_EQ:
                if (puzzle_var_get(a) != b) {
                    return 0;
                }
                break;
            default:
                return 0;
        }
    }
}

void puzzle_run_actions(unsigned short act_ofs) {
    const uint8_t* blob = level_get_blob();
    uint16_t base;

    if (act_ofs == 0) {
        return;
    }

    base = (uint16_t)(lvl_actstream_ofs(blob) + act_ofs);

    for (;;) {
        uint8_t op = lvl_rd8(blob, base + 0);
        uint8_t a = lvl_rd8(blob, base + 1);
        uint8_t b = lvl_rd8(blob, base + 2);

        base = (uint16_t)(base + 3u);

        switch (op) {
            case A_END:
                return;
            case A_SHOW_MSG:
                textbox_show(level_get_message(a));
                break;
            case A_SET_FLAG:
                puzzle_flag_set(a);
                break;
            case A_CLR_FLAG:
                puzzle_flag_clear(a);
                break;
            case A_GIVE_ITEM:
                inventory_add(a);
                break;
            case A_TAKE_ITEM:
                inventory_remove(a);
                break;
            case A_SET_VAR:
                puzzle_var_set(a, b);
                break;
            case A_SFX:
                break;
            case A_TRANSITION:
                room_load_with_spawn(a, b);
                break;
            default:
                return;
        }
    }
}
