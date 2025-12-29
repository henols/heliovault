#include "input.h"

#include <stdbool.h>
#include <c64/joystick.h>

uint8_t input_down = 0;
uint8_t input_pressed = 0;

static uint8_t input_prev = 0;

void input_init(void) {
    input_down = 0;
    input_pressed = 0;
    input_prev = 0;
}

void input_poll(void) {
    uint8_t down = 0;

    joy_poll(0);

    if (joyx[0] < 0) {
        down |= INPUT_LEFT;
    } else if (joyx[0] > 0) {
        down |= INPUT_RIGHT;
    }

    if (joyy[0] < 0) {
        down |= INPUT_UP;
    } else if (joyy[0] > 0) {
        down |= INPUT_DOWN;
    }

    if (joyb[0]) {
        down |= INPUT_FIRE;
    }

    input_down = down;
    input_pressed = (uint8_t)(down & (uint8_t)~input_prev);
    input_prev = down;
}
