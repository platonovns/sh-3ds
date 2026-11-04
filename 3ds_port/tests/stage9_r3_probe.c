#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/sys/joy.h"
#include "game3ds.h"
void Game3ds_Observe(void);
void stage9_r3_context(unsigned game,unsigned sys,unsigned room,unsigned skip)
{
    g_GameWork.gameState=game;
    g_SysWork.sysState=sys;
    g_SavegamePtr->mapIdx=0;g_SavegamePtr->mapRoomIdx=room;
    g_GameWorkPtr->config.controllerConfig.skip=ControllerFlag_Start;
    g_Controller0->clickedBtnFlags=skip?ControllerFlag_Start:0;
    Game3ds_Observe();
}
