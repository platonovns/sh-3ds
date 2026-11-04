#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_data.h"
unsigned stage7_route_probe(unsigned state,unsigned height)
{
    g_GameWork.gameState=state;Game3ds_BeginUpdate(state);
    GsInitGraph2(320,height,0,0,0);GsDefDispBuff2(0,0,0,0);GsSwapDispBuff();
    GsClearOt(0,0,&g_OrderingTable0[0]);GsDrawOt(&g_OrderingTable0[0]);
    uint32_t w,h;game3ds_gpu_extent(&w,&h);
    return w|(h<<10)|(game3ds_gpu_display()<<20);
}
