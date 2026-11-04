#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_data.h"
void GameState_MainMenu_Update(void);
unsigned stage8_route(unsigned state,unsigned next,unsigned h)
{
    Game3ds_BeginUpdate(state);
    GsInitGraph2(320,h,0,0,0);GsDefDispBuff2(0,32,0,h>240?32:256);GsSwapDispBuff();
    g_GameWork.gameState=next;
    GsClearOt(0,0,&g_OrderingTable0[0]);
    GsSortClear(0,0,0,&g_OrderingTable0[0]);GsDrawOt(&g_OrderingTable0[0]);
    uint32_t w,height;game3ds_gpu_extent(&w,&height);
    return w|(height<<10)|(game3ds_gpu_display()<<20);
}
unsigned stage8_title_idle_probe(void)
{
    /* Component-only clock setup: cross both retail attract thresholds. */
    g_SysWork.counters_1C[1]=2400;
    GameState_MainMenu_Update();
    return g_GameWork.gameState;
}
