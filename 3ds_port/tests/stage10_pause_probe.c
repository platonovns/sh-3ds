#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_data.h"
#include "psx_memory.h"
void stage10_original_pause(unsigned resume,unsigned *out)
{
    g_GameWork.gameState=GameState_InGame;
    if(!resume)SysWork_StateSetNext(SysState_GamePaused);
    g_Controller0->clickedBtnFlags=resume?g_GameWorkPtr->config.controllerConfig.pause:0;
    g_Controller0->heldBtnFlags=0;
    g_DeltaTimeRaw=136;
    GsOUT_PACKET_P=PSX_ADDR(0x801A2600);
    GsClearOt(0,0,&g_OrderingTable2[g_ActiveBufferIdx]);
    SysState_GamePaused_Update();
    out[0]=g_SysWork.sysState;out[1]=g_SysWork.sysStateSteps[0];
}
