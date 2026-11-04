#include "game.h"
#include "game3ds.h"
#include "game_controls.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include <psyq/libpad.h>
#include "bodyprog/screen/cutscene_border.h"
static unsigned char modern_pad[8],other_pad[8];
void stage10_modern_setup(unsigned blocked)
{
    Game3ds_ControlsReset();
    g_Player_IsAiming=0;
    g_DeltaTime=136;
    g_GameWork.gameState=GameState_InGame;g_SysWork.sysState=SysState_Gameplay;
    g_SysWork.sysFlags=0;g_SysWork.cutsceneBorderState=CutsceneBorderState_None;
    g_Player_DisableControl=blocked==1;
    g_SysWork.playerCombat.isAiming=blocked==2;
    g_SysWork.playerWork.extra.upperBodyState=blocked==3?PlayerUpperBodyState_Reload:0;
    g_SysWork.playerWork.extra.lowerBodyState=0;
    g_SysWork.playerWork.player.rotation.vy=123;
    if(blocked==4)g_SysWork.sysFlags|=SysFlag_CutsceneActive;
    PadInitDirect(modern_pad,other_pad);
}
void stage10_analog(int x,int y) {Game3ds_InputSample(0,0,0,x,y);}
unsigned stage10_modern_result(void)
{
    return (unsigned short)g_SysWork.playerWork.player.rotation.vy|
        ((unsigned)(unsigned short)~(modern_pad[2]|(modern_pad[3]<<8))<<16);
}
unsigned stage10_camera_result(void)
{
    MATRIX camera={0};
    camera.m[0][0]=camera.m[1][1]=camera.m[2][2]=4096;
    camera.t[0]=11;camera.t[1]=22;camera.t[2]=33;
    Game3ds_CameraLook(&camera);
    return (unsigned short)camera.m[0][2]|((camera.t[0]!=11 || camera.t[1]!=22 || camera.t[2]!=33)?1u<<31:0);
}
int stage10_camera_pitch(void)
{
    MATRIX camera={0};camera.m[0][0]=camera.m[1][1]=camera.m[2][2]=4096;
    Game3ds_CameraLook(&camera);return camera.m[1][2];
}
