/* Offline component fixtures; never linked into the hardware game. */
#include "game.h"
#include "game3ds.h"
#include "psx_memory.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/game_boot/game_boot.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/player.h"
#include "bodyprog/math/math.h"
#include "bodyprog/events/events_main.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "bodyprog/memcard.h"
#include "bodyprog/sys/joy.h"
#include "maps/shared.h"
#include <stddef.h>
#include <string.h>

extern u8 map3_s03_D_800D8140[],map3_s03_D_800D8144,map3_s03_D_800D8145;
extern u8 map3_s03_D_800D6B40[][2];
extern s32 map3_s03_D_800D6BD0,map3_s03_D_800D6BD4;
extern void map3_s03_func_800D1A58(void);
extern u8 map3_s01_sharedData_800D4CD4_3_s01[][2];
extern s32 map3_s01_sharedData_800D4D10_3_s01,map3_s01_sharedData_800D4D14_3_s01;
extern void map3_s01_sharedFunc_800D15F0_3_s01(void);
extern void map3_s03_Bloodsucker_Init(s_SubCharacter*);
unsigned alchemilla_probe_out[64];
unsigned alchemilla_probe_callbacks[256];
const unsigned alchemilla_probe_items[]={InvItemId_PlasticBottle,InvItemId_UnknownLiquid,
    InvItemId_BloodPack,InvItemId_DisinfectingAlcohol,InvItemId_Lighter,
    InvItemId_PlateOfTurtle,InvItemId_PlateOfHatter,InvItemId_PlateOfCat,InvItemId_PlateOfQueen,
    InvItemId_AntiqueShopKey};
static s_Savegame_Container saved;
static const unsigned persistence[]={EventFlag_M3S01_BasementDoorOpen,EventFlag_M3S01_GeneratorOn,
    EventFlag_M3S01_PickupUnknownLiquid,EventFlag_250,EventFlag_MapMark_713,
    EventFlag_M3S05_CabinetPushed,EventFlag_M3S05_AlcoholPouredOnVines,EventFlag_284,
    EventFlag_294,EventFlag_295,EventFlag_297,EventFlag_M3S06_PickupAntiqueShopKey,
    EventFlag_265,EventFlag_270,EventFlag_275,EventFlag_280};
const unsigned alchemilla_probe_flags[]={EventFlag_M3S01_PickupUnknownLiquid,
    EventFlag_M3S05_AlcoholPouredOnVines,EventFlag_284,EventFlag_MapMark_713};
const unsigned alchemilla_probe_keys[]={InvItemId_BasementKey,EventFlag_M3S01_BasementDoorOpen,
    InvItemId_BasementStoreroomKey,EventFlag_256,InvItemId_ExaminationRoomKey,EventFlag_258};
_Static_assert(sizeof(s_Savegame)==636,"Original save ABI");
_Static_assert(offsetof(s_MapOverlayHdr,playerStub_F8)==0xF8,"Original player slot");

unsigned alchemilla_probe_count(unsigned item)
{
    unsigned n=0;
    for(unsigned i=0;i<40;i++)if(g_SavegamePtr->items[i].id_0==item)n+=g_SavegamePtr->items[i].count_1;
    return n;
}
unsigned alchemilla_probe_flag(unsigned flag){return Savegame_EventFlagGetAlt(flag);}
void alchemilla_probe_add(unsigned item){Event_InvItemCmd(InvItemCmd_AddItem,item,1,false);}
void alchemilla_probe_reset(unsigned map)
{
    memset(&g_SysWork,0,sizeof(g_SysWork));Settings_RestoreDefaults();
    GameBoot_SavegameInitialize(map,GameDifficulty_Normal);
    /* Nearby chapter fixture; does not claim traversal from Cafe. */
    Savegame_EventFlagSet(EventFlag_132);Savegame_EventFlagSet(EventFlag_134);
    Savegame_EventFlagSet(EventFlag_146);Savegame_EventFlagSet(EventFlag_179);
    g_OvlDynamic=PSX_ADDR(0xC9578);Game3ds_MapBind(map);
    g_MapEventLastUsedItem=InvItemId_Unequipped;g_MapEventData=NULL;g_MapEventParam=0;
    memset(g_Controller0,0,sizeof(*g_Controller0));
    g_SysWork.playerWork.player.health=Q12(100.0f);
    g_SysWork.playerCombat.weaponAttack=NO_VALUE;
    g_DeltaTime=TIMESTEP_30_FPS;g_DeltaTimeRaw=g_DeltaTime;
    memset(alchemilla_probe_out,0,sizeof(alchemilla_probe_out));
}
unsigned alchemilla_probe_header(void)
{
    unsigned count=0,uses=0,transitions=0;
    for(s_EventData* e=g_MapOverlayHdr.mapEvents;e->triggerType!=TriggerType_EndOfArray;e++){
        if(++count>256)return 1;
        alchemilla_probe_callbacks[count-1]=0;
        if(e->sysState==SysState_EventCallback){
            if(!g_MapOverlayHdr.mapEventFuncs[e->eventParam])return 2;
            alchemilla_probe_callbacks[count-1]=(unsigned)g_MapOverlayHdr.mapEventFuncs[e->eventParam];
        }
        uses+=e->activationType==TriggerActivationType_Item;
        transitions+=e->sysState==SysState_LoadOverlay;
    }
    alchemilla_probe_out[0]=count;alchemilla_probe_out[1]=uses;alchemilla_probe_out[2]=transitions;
    alchemilla_probe_out[3]=(unsigned)g_MapOverlayHdr.playerStub_F8;
    alchemilla_probe_out[4]=(unsigned)g_MapOverlayHdr.charaCollisionReset;
    for(unsigned i=0;i<ARRAY_SIZE(g_MapOverlayHdr.charaUpdateFuncs);i++)alchemilla_probe_out[8+i]=(unsigned)g_MapOverlayHdr.charaUpdateFuncs[i];
    return 0;
}
unsigned alchemilla_probe_use(unsigned index)
{
    s_EventData* target=&g_MapOverlayHdr.mapEvents[index];
    if(target->activationType!=TriggerActivationType_Item)return 1;
    if(target->requiredEventFlag)Savegame_EventFlagSetAlt(target->requiredEventFlag);
    if(target->disabledEventFlag)Savegame_EventFlagClear(target->disabledEventFlag);
    s_MapPoint2d* point=&g_MapOverlayHdr.mapPoints[target->pointOfInterestIdx];
    q3_12 yaw=target->triggerType==TriggerType_TouchObbFacing?Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(point->triggerParam0)+2048):0;
    s_SubCharacter* p=&g_SysWork.playerWork.player;
    p->position.vx=point->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    p->position.vz=point->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));p->rotation.vy=yaw;
    Event_Update(true);
    unsigned slot;
    for(slot=0;slot<5 && g_ItemTriggerItemIds[slot]!=target->requiredItemId;slot++);
    alchemilla_probe_out[0]=slot;if(slot==5)return 2;
    g_SavegamePtr->items[0].id_0=target->requiredItemId;g_SavegamePtr->items[0].count_1=1;
    Inventory_ItemUse(0);
    if(g_SysWork.playerWork.extra.lastUsedItem!=target->requiredItemId)return 3;
    Event_Update(true);
    alchemilla_probe_out[1]=g_MapEventLastUsedItem;alchemilla_probe_out[2]=g_MapEventParam;
    alchemilla_probe_out[3]=g_MapEventData-g_MapOverlayHdr.mapEvents;
    if(g_MapEventSysState!=target->sysState || g_MapEventParam!=target->eventParam)return 4;
    if(g_SysWork.playerWork.extra.lastUsedItem!=InvItemId_Unequipped)return 5;
    return 0;
}
void alchemilla_probe_event(unsigned index,unsigned step)
{
    g_MapEventData=&g_MapOverlayHdr.mapEvents[index];g_MapEventParam=g_MapEventData->eventParam;
    g_SysWork.sysState=SysState_EventCallback;g_SysWork.sysStateSteps[0]=step;
    g_MapOverlayHdr.mapEventFuncs[g_MapEventParam]();
    alchemilla_probe_out[0]=g_SysWork.sysState;
    alchemilla_probe_out[1]=g_SysWork.sysStateSteps[0];
    alchemilla_probe_out[2]=g_Player_DisableControl;
    alchemilla_probe_out[3]=Savegame_EventFlagGetAlt(g_MapEventData->disabledEventFlag);
    for(unsigned i=0;i<3;i++)alchemilla_probe_out[4+i]=g_SysWork.npcs[i].model.controlState;
}
void alchemilla_probe_pickup(unsigned index,unsigned step)
{
    g_MapEventData=&g_MapOverlayHdr.mapEvents[index];g_MapEventParam=g_MapEventData->eventParam;
    g_SysWork.sysStateSteps[1]=step;g_MapOverlayHdr.mapEventFuncs[g_MapEventParam]();
    alchemilla_probe_out[0]=Savegame_EventFlagGetAlt(g_MapEventData->disabledEventFlag);
}
void alchemilla_probe_fmv(unsigned index)
{
    g_MapEventData=&g_MapOverlayHdr.mapEvents[index];g_MapEventParam=g_MapEventData->eventParam;
    g_SysWork.sysStateSteps[0]=2;D_800A9A0C=1;SysState_Fmv_Update();
    alchemilla_probe_out[0]=Savegame_EventFlagGetAlt(g_MapEventData->disabledEventFlag);
}
void alchemilla_probe_plates_init(void)
{
    for(unsigned i=0;i<16;i++)Savegame_EventFlagClear(EventFlag_265+i);
    Savegame_EventFlagClear(EventFlag_MapMark_713);
    memset(map3_s03_D_800D8140,8,4);map3_s03_D_800D8145=0;
}
void alchemilla_probe_elevator(unsigned extra)
{
    if(extra){
        Savegame_EventFlagSet(EventFlag_MapMark_AltHospital2F_OperatingPrepRoomArrow);
        Savegame_EventFlagSet(EventFlag_MapMark_AltHospital2F_CorridorMidArrows);
    }else{
        Savegame_EventFlagClear(EventFlag_MapMark_AltHospital2F_OperatingPrepRoomArrow);
        Savegame_EventFlagClear(EventFlag_MapMark_AltHospital2F_CorridorMidArrows);
    }
    Savegame_EventFlagClear(EventFlag_224);
    map3_s01_sharedData_800D4D10_3_s01=(map3_s01_sharedData_800D4CD4_3_s01[5][0]-150)*4096;
    map3_s01_sharedData_800D4D14_3_s01=(map3_s01_sharedData_800D4CD4_3_s01[5][1]-110)*4096;
    g_Controller0->clickedBtnFlags=g_GameWorkPtr->config.controllerConfig.enter;
    g_SysWork.sysStateSteps[0]=4;map3_s01_sharedFunc_800D15F0_3_s01();
    alchemilla_probe_out[0]=Savegame_EventFlagGetAlt(EventFlag_224);
    alchemilla_probe_out[1]=g_SysWork.sysStateSteps[0];
}
void alchemilla_probe_bloodsucker(unsigned fed)
{
    if(fed)Savegame_EventFlagSet(EventFlag_250);else Savegame_EventFlagClear(EventFlag_250);
    for(unsigned i=0;i<3;i++){
        s_SubCharacter* n=&g_SysWork.npcs[i];memset(n,0,sizeof(*n));
        n->model.charaId=Chara_Bloodsucker;n->model.stateStep=18+i;
        map3_s03_Bloodsucker_Init(n);
        alchemilla_probe_out[i*3]=n->model.controlState;
        alchemilla_probe_out[i*3+1]=n->model.stateStep;
        alchemilla_probe_out[i*3+2]=n->model.anim.status;
    }
}
void alchemilla_probe_plate(unsigned slot,unsigned plate,unsigned remove)
{
    map3_s03_D_800D8144=plate;
    map3_s03_D_800D6BD0=(map3_s03_D_800D6B40[slot][0]-146)*4096;
    map3_s03_D_800D6BD4=(map3_s03_D_800D6B40[slot][1]-106)*4096;
    g_Controller0->clickedBtnFlags=g_GameWorkPtr->config.controllerConfig.enter;
    g_SysWork.sysStateSteps[0]=remove?12:8;map3_s03_func_800D1A58();
    alchemilla_probe_out[0]=g_SysWork.sysStateSteps[0];
    alchemilla_probe_out[1]=Savegame_EventFlagGetAlt(EventFlag_MapMark_713);
    for(unsigned i=0;i<4;i++)alchemilla_probe_out[2+i]=map3_s03_D_800D8140[i];
}
unsigned alchemilla_probe_save(unsigned map,unsigned phase)
{
    g_SavegamePtr->mapIdx=map;g_SavegamePtr->mapRoomIdx=3;
    for(unsigned i=0;i<ARRAY_SIZE(persistence);i++){
        if((i+phase)%3)Savegame_EventFlagSet(persistence[i]);else Savegame_EventFlagClear(persistence[i]);
    }
    Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_UnknownLiquid,1,false);
    g_SavegamePtr->ovlEnemyStates[map]=0x1249;
    MemCard_GameDataCopy(&saved,g_SavegamePtr);
    if(!MemCard_ChecksumValidate(&saved.footer,(s8*)&saved.savegame,sizeof(saved)))return 1;
    if(memcmp(&saved.savegame,g_SavegamePtr,sizeof(s_Savegame)))return 2;
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));memcpy(g_SavegamePtr,&saved.savegame,sizeof(s_Savegame));
    if(g_SavegamePtr->mapIdx!=map || g_SavegamePtr->ovlEnemyStates[map]!=0x1249 || !alchemilla_probe_count(InvItemId_UnknownLiquid))return 3;
    for(unsigned i=0;i<ARRAY_SIZE(persistence);i++)if(!!Savegame_EventFlagGet(persistence[i])!=!!((i+phase)%3))return 4;
    /* Checksum must reject a changed payload as well as accept a valid one. */
    ((u8*)&saved.savegame)[19]^=1;
    if(MemCard_ChecksumValidate(&saved.footer,(s8*)&saved.savegame,sizeof(saved)))return 5;
    return 0;
}
