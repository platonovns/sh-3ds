#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/events/npc_main.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/screen/screen_draw.h"
#include "bodyprog/math/math.h"
#include "bodyprog/screen/background_draw.h"
#include "game3ds.h"
#include "psx_memory.h"
extern void map0_s01_Map_WorldObjectsInit(void);
extern s_WorldEnvWork g_WorldEnvWork;
extern void map0_s01_MapEvent_CafeCutscene(void);
extern q19_12 map0_s01_g_Cutscene_Timer;
void stage8_r2_reload(unsigned *out)
{
    Savegame_EventFlagSet(EventFlag_M0S01_CafeCutsceneStarted);
    Savegame_EventFlagSet(EventFlag_M0S01_PickupMap);
    Savegame_EventFlagClear(EventFlag_47);
    map0_s01_Map_WorldObjectsInit();
    out[0]=g_SysWork.npcs[0].model.charaId;
    out[1]=g_SysWork.npcs[0].position.vx;
    out[2]=g_SysWork.npcs[0].position.vz;
    g_DeltaTime=g_DeltaTimeRaw=136;
    Game_NpcUpdate();
    out[3]=g_SysWork.npcs[0].model.charaId;
    out[4]=g_SysWork.npcs[0].position.vx;
}
unsigned stage8_r2_skip(void)
{
    g_GameWork.gameState=GameState_InGame;
    g_SysWork.sysFlags|=SysFlag_CutsceneActive;
    g_SysWork.sysStateSteps[0]=6;
    g_Controller0->clickedBtnFlags=g_GameWorkPtr->config.controllerConfig.skip;
    map0_s01_g_Cutscene_Timer=NO_VALUE;
    map0_s01_MapEvent_CafeCutscene();
    return g_SysWork.sysStateSteps[0];
}
void stage8_r2_flight(unsigned dt,unsigned *out)
{
    g_DeltaTime=g_DeltaTimeRaw=dt;
    GsOUT_PACKET_P=PSX_ADDR(0x801A2600);
    GsClearOt(0,0,&g_OrderingTable0[g_ActiveBufferIdx]);
    Game_NpcUpdate();
    const s_SubCharacter *n=&g_SysWork.npcs[0];
    out[0]=n->model.charaId;out[1]=n->position.vx;out[2]=n->position.vy;out[3]=n->position.vz;
    out[4]=n->model.controlState;out[5]=n->model.anim.status;out[6]=n->model.anim.time;
    out[7]=n->model.anim.flags;out[8]=n->health;
}
unsigned stage8_r2_pause(unsigned flags,unsigned border,unsigned sys)
{
    g_GameWork.gameState=GameState_InGame;g_SysWork.sysFlags=flags;
    g_SysWork.cutsceneBorderState=border;g_SysWork.sysState=sys;
    return Game3ds_CanPause();
}
void stage8_r2_transition(unsigned height)
{
    Game3ds_BeginUpdate(GameState_InGame);
    g_GameWork.gsScreenWidth=320;g_GameWork.gsScreenHeight=height;
    GsInitGraph2(320,height,height>240?5:4,0,0);GsDefDispBuff2(0,32,0,height>240?32:256);GsSwapDispBuff();
    g_ActiveBufferIdx=GsGetActiveBuff();
    GsOT *ot=&g_OrderingTable0[g_ActiveBufferIdx];
    GsClearOt(0,0,ot);
    GsSortClear(0,0,0,ot);GsDrawOt(ot);
    game3ds_gpu_frame_complete();
    GsClearOt(0,0,ot);
    Screen_BackgroundMotionBlur(2);GsDrawOt(ot);
}
void stage8_r2_fog(void)
{
    Game3ds_BeginUpdate(GameState_InGame);
    g_GameWork.gsScreenWidth=320;g_GameWork.gsScreenHeight=224;
    Screen_Init(320,false);
    GsClearOt(0,0,&g_OrderingTable0[0]);
    g_WorldEnvWork.isFogEnabled=true;g_WorldEnvWork.fog.farDistance=32767;
    g_WorldEnvWork.fog.intensity=4096;g_WorldEnvWork.fog.color=(CVECTOR){64,64,64,0};
    Gfx_FogOverlayQuadDraw(-250,-200,250,200,1000,512,&g_OrderingTable0[0],0);
    GsDrawOt(&g_OrderingTable0[0]);
}
void stage8_r2_status_return(unsigned previous)
{
    g_GameWork.gameState=GameState_InGame;
    g_GameWork.gameStatePrev=previous;
    g_GameWork.gameStateSteps[0]=0;
    g_SysWork.sysState=SysState_Gameplay;
    GameState_InGame_Update();
}
