/* Nearby fixture setup only. No progression item or event flag writes. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include "bodyprog/math/math.h"
#include "bodyprog/memcard.h"
#include "bodyprog/game_boot/game_boot.h"
#include "bodyprog/events/player_pos_update.h"
#include "screens/saveload.h"
#include <stddef.h>
const unsigned stage10_progression_meta[]={offsetof(__typeof__(*g_SavegamePtr),items),
    sizeof(g_SavegamePtr->items[0]),offsetof(__typeof__(*g_SavegamePtr),eventFlags),
    sizeof(*g_SavegamePtr),GameState_SaveScreen,offsetof(__typeof__(*g_SavegamePtr),mapIdx),
    offsetof(__typeof__(*g_SavegamePtr),mapRoomIdx),offsetof(__typeof__(*g_SavegamePtr),locationId)};
const unsigned stage10_progression_targets[][4]={
    {14,0,EventFlag_M2S00_DogHouseNoteFound,InvItemId_NoteDoghouse},
    {16,1,EventFlag_M2S00_PickupDogHouseKey,InvItemId_HouseKey},
    {17,1,EventFlag_M2S00_PickupKeyOfLion,InvItemId_KeyOfLion},
    {18,0,EventFlag_M2S00_PickupKeyOfWoodman,InvItemId_KeyOfWoodman},
    {19,0,EventFlag_M2S00_PickupKeyOfScarecrow,InvItemId_KeyOfScarecrow},
    {22,1,EventFlag_153,0}};
const unsigned stage10_progression_sys_meta[]={offsetof(__typeof__(g_SysWork),sysState),
    sizeof(g_SysWork.sysState),offsetof(__typeof__(g_SysWork),sysStateSteps),
    offsetof(__typeof__(g_SysWork),playerWork.player.position),
    offsetof(__typeof__(g_SysWork),playerWork.player.rotation.vy)};
const unsigned stage10_progression_savepose[]={offsetof(__typeof__(*g_SavegamePtr),playerPositionX),
    offsetof(__typeof__(*g_SavegamePtr),playerPositionZ),offsetof(__typeof__(*g_SavegamePtr),playerRotationY)};
const unsigned stage10_progression_route_flags[]={EventFlag_M2S00_LockOfLionOpen,EventFlag_M2S00_LockOfWoodmanOpen,
    EventFlag_M2S00_LockOfScarecrowOpen,EventFlag_M2S00_DoorOfEclypseOpen,EventFlag_158,EventFlag_159};
extern bool Event_CollideObbFacingCheck(s_MapPoint2d *point);
unsigned stage10_progression_place(unsigned poi,unsigned obb)
{
    const s_MapPoint2d *point=&g_MapOverlayHdr.mapPoints[poi];
    s_SubCharacter *p=&g_SysWork.playerWork.player;
    q3_12 yaw=obb?Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(point->triggerParam0)+2048):0;
    p->position.vx=point->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    p->position.vz=point->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));
    p->rotation.vy=yaw;
    Game_PlayerHeightUpdate();
    return !obb || Event_CollideObbFacingCheck((s_MapPoint2d*)point);
}
static int scan(void)
{
    MemCard_SysInit();MemCard_SysEnable();MemCard_InitStatus();
    for(unsigned i=0;i<8192;i++) {
        MemCard_Update();
        if((MemCard_StatusGet(MemCard_AllMemCardsStatusGet(),0))==MemCardState_Available)return 1;
    }
    return 0;
}
unsigned stage10_progression_save_current(void)
{
    if(!scan())return 1;
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
unsigned stage10_progression_load(void)
{
    Settings_RestoreDefaults();GameBoot_SavegameInitialize(0,GameDifficulty_Hard);
    if(!scan())return 1;
    if(MemCard_UsedFileCount(0)!=1)return 2;
    if(!MemCard_ProcessSet(MemCardProcess_Load_Settings,0,0,0))return 4;
    for(unsigned i=0;i<8192 && MemCard_LastMemCardResultGet()==MemCardResult_Success;i++)MemCard_Update();
    if(MemCard_LastMemCardResultGet()!=MemCardResult_FileIoComplete)return 8;
    if(!MemCard_ProcessSet(MemCardProcess_Load_Game,0,0,0))return 16;
    for(unsigned i=0;i<8192 && MemCard_LastMemCardResultGet()==MemCardResult_Success;i++)MemCard_Update();
    return MemCard_LastMemCardResultGet()==MemCardResult_FileIoComplete?0:32;
}
