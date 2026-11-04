#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/game_boot/game_boot.h"
#include "bodyprog/memcard.h"
#include "screens/saveload.h"
static int scan(void)
{
    MemCard_SysInit();MemCard_SysEnable();MemCard_InitStatus();
    for(unsigned i=0;i<8192;i++) {
        MemCard_Update();
        if((MemCard_StatusGet(MemCard_AllMemCardsStatusGet(),0))==MemCardState_Available)return 1;
    }
    return 0;
}
unsigned stage7_save_create(void)
{
    Settings_RestoreDefaults();GameBoot_SavegameInitialize(1,GameDifficulty_Normal);
    if(!scan())return 1;
    g_SavegamePtr->locationId=SaveLocationId_Cafe;
    g_SelectedDeviceId=0;g_SelectedFileIdx=0;g_Savegame_SelectedElementIdx=0;
    g_GameWork.gameState=GameState_SaveScreen;
    g_GameWork.gameStateSteps[0]=3;g_GameWork.gameStateSteps[1]=0;
    for(unsigned i=0;i<8192;i++) {
        MemCard_Update();SaveScreen_SaveGame();
        if(g_GameWork.gameStateSteps[0]==1 && g_GameWork.gameStateSteps[1]==0)
            return MemCard_LastMemCardResultGet()==MemCardResult_FileIoComplete?0:2;
    }
    return 4;
}
unsigned stage7_save_load(void)
{
    Settings_RestoreDefaults();GameBoot_SavegameInitialize(0,GameDifficulty_Hard);
    if(!scan())return 1;
    if(MemCard_UsedFileCount(0)!=1)return 2;
    if(!MemCard_ProcessSet(MemCardProcess_Load_Settings,0,0,0))return 4;
    for(unsigned i=0;i<8192 && MemCard_LastMemCardResultGet()==MemCardResult_Success;i++)MemCard_Update();
    if(MemCard_LastMemCardResultGet()!=MemCardResult_FileIoComplete)return 8;
    if(!MemCard_ProcessSet(MemCardProcess_Load_Game,0,0,0))return 16;
    for(unsigned i=0;i<8192 && MemCard_LastMemCardResultGet()==MemCardResult_Success;i++)MemCard_Update();
    if(MemCard_LastMemCardResultGet()!=MemCardResult_FileIoComplete)return 32;
    if(g_SavegamePtr->mapIdx!=1 || g_SavegamePtr->locationId!=SaveLocationId_Cafe || g_SavegamePtr->gameDifficulty!=GameDifficulty_Normal)return 64;
    return 0;
}
