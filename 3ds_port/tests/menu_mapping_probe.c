#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/sys/joy.h"
unsigned test_menu_mapping(void)
{
    Settings_RestoreDefaults(); /* Includes inlined USA control preset 0. */
    unsigned flags=0;
#ifdef SH_3DS_PORT
    if(g_GameWorkPtr->config.controllerConfig.map==ControllerFlag_Select)flags|=1;
    if(g_GameWorkPtr->config.controllerConfig.item==ControllerFlag_Triangle)flags|=2;
#else
    if(g_GameWorkPtr->config.controllerConfig.map==ControllerFlag_Triangle)flags|=1;
    if(g_GameWorkPtr->config.controllerConfig.item==ControllerFlag_Select)flags|=2;
#endif
    if(SysState_MapScreen==3 && SysState_StatusMenu==2)flags|=4;
    return flags;
}
