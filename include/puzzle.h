#ifndef PUZZLE_H
#define PUZZLE_H

#include "common.h"

void puzzle_init(void);
void puzzle_update(void);
unsigned char puzzle_flag_get(FlagId flag_id);
void puzzle_flag_set(FlagId flag_id);
void puzzle_flag_clear(FlagId flag_id);
unsigned char puzzle_var_get(VarId var_id);
void puzzle_var_set(VarId var_id, unsigned char value);
unsigned char puzzle_conditions_pass(unsigned short cond_ofs);
void puzzle_run_actions(unsigned short act_ofs);

#endif
