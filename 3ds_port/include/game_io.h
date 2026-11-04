#ifndef SH_GAME_IO_H
#define SH_GAME_IO_H
#include <stdint.h>
#include <stdio.h>
void game_io_context(unsigned state,unsigned player,unsigned map,int32_t x,int32_t z,int32_t yaw);
void game_io_begin(unsigned file,uint32_t lba,uint32_t bytes);
void game_io_raw(uint32_t lba,uint32_t requested,uint32_t actual,unsigned seek,uint64_t ticks);
void game_io_data(uint32_t bytes);
void game_io_end(int status);
void game_io_report(FILE *out);
#endif
