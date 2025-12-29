#include "textbox.h"

#include <c64/charwin.h>

static const char* textbox_text = 0;
static CharWin textbox_win;

void textbox_init(void) {
    textbox_text = 0;
    cwin_init(&textbox_win, (char*)0x0400, 0, 24, 40, 1);
    cwin_clear(&textbox_win);
}

void textbox_update(void) {
}

void textbox_show(const char* text) {
    textbox_text = text;
    cwin_clear(&textbox_win);
    if (text) {
        cwin_putat_string_raw(&textbox_win, 0, 0, text, 1);
    }
}

const char* textbox_get_text(void) {
    return textbox_text;
}
