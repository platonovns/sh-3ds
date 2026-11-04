/* Host fixture links against the actual native Gfx_MapMsg_Draw. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/sys/joy.h"
#include "bodyprog/events/map_msg.h"
void stage9_r5_message_setup(unsigned idx)
{
    g_Controller0->clickedBtnFlags=0;g_Controller0->heldBtnFlags=0;
    g_SysWork.bgmStatusFlags=BgmStatusFlag_VoiceDialog;
    g_SysWork.isMgsStringSet=false;g_DeltaTimeRaw=137;
    Gfx_MapMsg_Draw(idx);
    g_MapMsg_AudioLoadBlock=2;g_SysWork.mapMsgTimer=4096;
}
unsigned stage9_r5_message_draw(unsigned idx)
{
    Gfx_MapMsg_Draw(idx);
    return g_SysWork.mapMsgTimer;
}
