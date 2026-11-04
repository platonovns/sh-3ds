#ifndef SH_GAME_CARD_H
#define SH_GAME_CARD_H
#include "psyq_file.h"
#include <psyq/kernel.h>
int PsxCard_OpenEvent(unsigned desc,int spec,int mode,void (*callback)(void));
struct DIRENTRY *PsxCard_FirstFile(char *path,struct DIRENTRY *out);
struct DIRENTRY *PsxCard_NextFile(struct DIRENTRY *out);
int PsxCard_Format(char *path);
int PsxCard_Erase(char *path);
int PsxCard_Rename(char *from,char *to);
int game_card_select(unsigned card);
int game_card_select_error(void);
void game_card_set_initial(unsigned card);
int Game3ds_CardChange(unsigned card);
#endif
