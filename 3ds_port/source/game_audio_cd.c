/* Original audio task loader, with an independent read-only disc cursor. */
#include "game.h"
#include "game3ds.h"
#include "game_audio.h"
#include "game_audio_cd.h"
#include "bodyprog/sound/sound_system.h"
#include "psx_memory.h"
#include "sh_disc.h"
#include "bodyprog/libsd.h"
#include "game_xa.h"
#include "xa_locations.h"
#include <string.h>

static PsxDisc disc;
static uint32_t cursor, opened, reads, loaded_bytes, tick_last, tick_fraction;
static uint8_t cd_mode,filter_file,filter_channel;
extern s_AudioItemData *g_Sd_VabTargetLoad, *g_Sd_KdtTargetLoad;
static void ensure_open(void)
{
    if(opened)return;
    int status=PsxDisc_Open(&disc,"sdmc:/3ds/silenthill/sh1.bin","sdmc:/3ds/silenthill/sh1.cue");
    if(status)game3ds_halt(481,"audio disc open",(uint32_t)status);
    opened=1;
}
int AudioCdControl(u_char cmd,u_char *param,u_char *result)
{
    if(result)*result=(uint8_t)game_xa_status();
    if((cmd==CdlSetloc || cmd==CdlSeekL || cmd==CdlSeekP) && param) {
        PsxMsf msf={param[0],param[1],param[2]};int32_t lba;
        if(PsxDisc_MsfToLba(&msf,&lba) || lba<0)game3ds_halt(482,"audio seek",0);
        cursor=(uint32_t)lba;
    }
    if(cmd==CdlSetmode && param)cd_mode=*param;
    if(cmd==CdlSetfilter && param){filter_file=param[0];filter_channel=param[1];}
    if(cmd==CdlSetmode || cmd==CdlSetfilter || cmd==CdlPause || cmd==CdlStop || cmd==CdlSeekL || cmd==CdlSeekP || cmd==CdlReadN || cmd==CdlReadS)
        game_xa_note(XA_NOTE_CD,cmd,cd_mode|((uint32_t)filter_file<<8)|((uint32_t)filter_channel<<16),cursor);
    if(cmd==CdlPause || cmd==CdlStop || cmd==CdlSeekL || cmd==CdlSeekP)
        game_xa_cancel(cmd==CdlPause || cmd==CdlStop?XA_CANCEL_CD_PAUSE:XA_CANCEL_CD_SEEK,cmd,cursor);
    if(cmd==CdlReadN || cmd==CdlReadS) {
        if(!(cd_mode&CdlModeRT))return 0;
        uint32_t ticks=game_audio_xa_ticks();
        if(!ticks)return 0;
        game_xa_start(cursor,filter_file,filter_channel,ticks);
    }
    if(cmd==CdlGetparam && result){result[1]=cd_mode;result[2]=0;result[3]=filter_file;result[4]=filter_channel;}
    return 1;
}
int AudioCdControlB(u_char c,u_char *p,u_char *r) { return AudioCdControl(c,p,r); }
int AudioCdSync(int mode,u_char *r) { (void)mode;if(r)*r=(uint8_t)game_xa_status();return CdlComplete; }
int AudioCdReadSync(int mode,u_char *r) { (void)mode;if(r)*r=0;return 0; }
int AudioCdMix(CdlATV *v) { if(v)game_xa_mix(v->val0,v->val1,v->val2,v->val3);return 1; }
int AudioCdReset(int mode) { (void)mode;game3ds_halt(483,"audio loader retry limit",cursor); }
int AudioCdRead(int sectors,u_long *buffer,int mode)
{
    ensure_open();
    uintptr_t dest=(uintptr_t)buffer,base=(uintptr_t)g_PsxRam;
    uint32_t bytes=sectors>0 && sectors<=25?(uint32_t)sectors*2048:0;
    int allowed=0;
    for(unsigned i=0;i<127;i++) {
        const s_AudioItemData *a=&g_AudioData[i];
        if(a!=g_Sd_VabTargetLoad && a!=g_Sd_KdtTargetLoad)continue;
        uint32_t end=a->fileOffset_8+((uint32_t)a->fileSize_4+2047)/2048;
        if(cursor>=a->fileOffset_8 && cursor<end && (uint32_t)sectors<=end-cursor)allowed=1;
    }
    if(!allowed || mode!=128 || !bytes || dest<base || dest-base>PSX_RAM_SIZE || bytes>PSX_RAM_SIZE-(dest-base))
        game3ds_halt(484,"audio read bounds",cursor);
    int status=ShDisc_ReadBytes(&disc,cursor,0,buffer,bytes);
    if(status)game3ds_halt(485,"audio sector I/O",(uint32_t)status);
    cursor+=(uint32_t)sectors;reads++;loaded_bytes+=bytes;
    return 1;
}
void game_audio_cd_close(void) { if(opened)PsxDisc_Close(&disc);opened=0; }
void game_audio_tick(void)
{
    /* PSX RCnt2: 33,868,800 / 8 / 7328 Hz. Independent of 30/60 render cap.
     * Only the game thread touches libsd. NDSP's worker touches the SPU core. */
    uint32_t now=game3ds_q12_clock();
    if(!tick_last){tick_last=now;return;}
    uint32_t dt=now-tick_last;tick_last=now;
    if(dt>4096/4)dt=4096/4;
    tick_fraction+=dt*33075u; /* exact reduction: timerHz / Q12Hz = 33075/234496 */
    while(tick_fraction>=234496u) { smf_timer();tick_fraction-=234496u; }
}
void game_audio_loader_report(FILE *out)
{ fprintf(out,"audio_disc_reads=%lu\naudio_disc_bytes=%lu\n",(unsigned long)reads,(unsigned long)loaded_bytes); }
