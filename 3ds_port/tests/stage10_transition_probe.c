/* Linked ARM diagnostic only, never part of a hardware candidate. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/screen/screen_draw.h"
#include "bodyprog/screen/background_draw.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"

void stage10_transition_init(void)
{
    Game3ds_BeginUpdate(GameState_InGame);
    Screen_Init(320, false);
    g_ActiveBufferIdx=GsGetActiveBuff();
    GsClearOt(0,0,&g_OrderingTable0[g_ActiveBufferIdx]);
    GsSortClear(50,80,100,&g_OrderingTable0[g_ActiveBufferIdx]);
    GsDrawOt(&g_OrderingTable0[g_ActiveBufferIdx]);
    game3ds_gpu_frame_complete();
}

void stage10_transition_frame(unsigned state, unsigned fade)
{
    Game3ds_BeginUpdate(state);
    GsOUT_PACKET_P=(PACKET*)TEMP_MEMORY_ADDR;
    GsClearOt(0,0,&g_OrderingTable0[g_ActiveBufferIdx]);
    GsClearOt(0,0,&g_OrderingTable2[g_ActiveBufferIdx]);
    Screen_BackgroundMotionBlur(2);
    if(fade) {
        if(fade==1)ScreenFade_Start(true,false,false);
        g_ScreenFadeTimestep=4096;
        g_DeltaTimeRaw=136;
        Screen_FadeUpdate();
    }
    GsSwapDispBuff();
    GsDrawOt(&g_OrderingTable0[g_ActiveBufferIdx]);
    GsDrawOt(&g_OrderingTable2[g_ActiveBufferIdx]);
    game3ds_gpu_frame_complete();
    g_ActiveBufferIdx=GsGetActiveBuff();
}

unsigned stage10_transition_sfx(unsigned pair)
{
    static s_EventData event;
    static s_MapPoint2d point;
    static s_MapOverlayHdr overlay;
    overlay.mapPoints=&point;
    g_pMapOverlayHeader=&overlay;
    event.sfxPairIdx_8_19=pair;
    event.eventParam=0;
    g_MapEventData=&event;
    g_SysWork.sysState=SysState_LoadRoom;
    SysState_LoadArea_Update();
    return 0;
}

void stage10_transition_invalidate(unsigned overlap)
{
    Game3ds_BeginUpdate(GameState_InGame);
    GsOUT_PACKET_P=(PACKET*)TEMP_MEMORY_ADDR;
    GsClearOt(0,0,&g_OrderingTable0[g_ActiveBufferIdx]);
    Screen_BackgroundMotionBlur(2);
    DRAWENV env;GetDrawEnv(&env);
    Game3ds_FeedbackInvalidate(overlap?0:800,env.clip.y,8,8);
    GsSwapDispBuff();GsDrawOt(&g_OrderingTable0[g_ActiveBufferIdx]);
}
