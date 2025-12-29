#ifndef PUZZLE_H
#define PUZZLE_H

void puzzle_init(void);
void puzzle_update(void);
unsigned char puzzle_flag_get(unsigned char flag_id);
void puzzle_flag_set(unsigned char flag_id);
void puzzle_flag_clear(unsigned char flag_id);
unsigned char puzzle_var_get(unsigned char var_id);
void puzzle_var_set(unsigned char var_id, unsigned char value);
unsigned char puzzle_conditions_pass(unsigned short cond_ofs);
void puzzle_run_actions(unsigned short act_ofs);

#endif
