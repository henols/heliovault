#ifndef ROOM_H
#define ROOM_H

void room_load(unsigned char room_id);
void room_load_with_spawn(unsigned char room_id, unsigned char spawn_id);
void room_render(void);
const unsigned char* room_get_map(void);
unsigned char room_get_width(void);
unsigned char room_get_height(void);
unsigned char room_get_id(void);
unsigned char room_get_spawn_id(void);
unsigned char room_get_object_count(void);
unsigned short room_get_object_base(unsigned char obj_index);
unsigned char room_get_spawn_count(void);
void room_get_spawn_xy(unsigned char spawn_index, unsigned char* out_x, unsigned char* out_y);
unsigned char room_get_exit_count(void);
void room_get_exit(unsigned char exit_index, unsigned char* out_type, unsigned char* out_room, unsigned char* out_spawn);

#endif
