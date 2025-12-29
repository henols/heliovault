#ifndef INPUT_H
#define INPUT_H

#include "common.h"

extern uint8_t input_down;
extern uint8_t input_pressed;

enum {
    INPUT_LEFT = 1u << 0,
    INPUT_RIGHT = 1u << 1,
    INPUT_UP = 1u << 2,
    INPUT_DOWN = 1u << 3,
    INPUT_FIRE = 1u << 4
};

void input_init(void);
void input_poll(void);

#endif
