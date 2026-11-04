/* Explicit temporary Stage 4 presentation and absent-memory-card boundaries. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/memcard.h"
#include "bodyprog/sound/sound_system.h"
#include "bodyprog/math/math.h"
#include "game_card.h"
#include <string.h>

int Game3ds_CardChange(unsigned card)
{
    /* Save/Load can disable card events while the background presence probe
     * is in flight. It can no longer complete without those events. Discard
     * only this read-only probe, never a foreground save/load operation. */
    if(!g_MemCard_AvailibityStatus &&
       g_MemCard_Work.state==MemCardWorkState_Init &&
       g_MemCard_Work.MemCardIoMode==MemCardIoMode_Init &&
       g_MemCard_SaveWork.saveWork[0].processId==MemCardProcess_None)
        MemCard_StateInit();
    /* The game can leave a synchronous card probe in progress between
     * frames. Finish it while paused; never replace an active operation. */
    for(unsigned i=0;i<64 && g_MemCard_Work.state!=MemCardWorkState_Idle;i++)
        MemCard_StateUpdate();
    if(g_MemCard_Work.state==MemCardWorkState_Init)
        return -(4000+(g_MemCard_AvailibityStatus?1000:0)+
                 (int)g_MemCard_Work.MemCardIoMode*100+(int)g_MemCard_Work.stateStep);
    if(g_MemCard_Work.state!=MemCardWorkState_Idle)return -(400+(int)g_MemCard_Work.state);
    if(!game_card_select(card))return -(game_card_select_error()?game_card_select_error():301);
    MemCard_SysDisable();
    MemCard_SysInit();
    MemCard_SysInit2();
    MemCard_InitStatus();
    return 1;
}

s_WorldGfxWork g_WorldGfxWork;
s_WorldEnvWork g_WorldEnvWork;
_GsFCALL GsFCALL4;
void func_80089090(s32 enabled) { (void)enabled; }
void func_800890B8(void) {}
s32 func_80089128(void) { return 0; }
void func_800892A4(s32 effect) { (void)effect; } /* vibration effect enqueue */
void func_800893D0(q19_12 force) { (void)force; }
void func_8008944C(void) {}
void func_80089470(void) {}
void func_80089494(void) {}
void func_800894B8(s32 arg0) {(void)arg0;} /* vibration pattern 9 amplitude */
void func_80089500(void) {} /* vibration pattern 9: New 3DS has no motor */
void func_80089314(s32 mode) { (void)mode; } /* vibration pattern timing */
