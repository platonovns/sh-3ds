#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_draw.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/text/text_draw.h"
void stage10_status_text(unsigned high_res,unsigned lines)
{
    g_GameWork.gameState=GameState_InventoryScreen;g_GameWork.gameStateSteps[1]=1;
    Game3ds_BeginUpdate(GameState_InventoryScreen);
    Screen_Init(320,true);g_ActiveBufferIdx=GsGetActiveBuff();
    GsClearOt(0,0,&g_OrderingTable2[g_ActiveBufferIdx]);
    GsOUT_PACKET_P=(PACKET*)TEMP_MEMORY_ADDR;
    g_SysWork.enableHighResGlyphs=high_res;
    Gfx_StringSetColor(0);Gfx_StringSetPosition(60,42);
    Gfx_StringDraw(lines?"HANDGUN\nHANDGUN\nHANDGUN":"HANDGUN",100);
    GsDrawOt(&g_OrderingTable2[g_ActiveBufferIdx]);
}
