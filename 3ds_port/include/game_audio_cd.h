#ifndef SH_GAME_AUDIO_CD_H
#define SH_GAME_AUDIO_CD_H
#include <psyq/libcd.h>
int AudioCdControl(u_char command,u_char *param,u_char *result);
int AudioCdControlB(u_char command,u_char *param,u_char *result);
int AudioCdSync(int mode,u_char *result);
int AudioCdRead(int sectors,u_long *buffer,int mode);
int AudioCdReadSync(int mode,u_char *result);
int AudioCdMix(CdlATV *volume);
int AudioCdReset(int mode);
#define CdControl AudioCdControl
#define CdControlB AudioCdControlB
#define CdSync AudioCdSync
#define CdRead AudioCdRead
#define CdReadSync AudioCdReadSync
#define CdMix AudioCdMix
#define CdReset AudioCdReset
#endif
