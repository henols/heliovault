#ifndef TEXTBOX_H
#define TEXTBOX_H

void textbox_init(void);
void textbox_update(void);
void textbox_show(const char* text);
const char* textbox_get_text(void);

#endif
