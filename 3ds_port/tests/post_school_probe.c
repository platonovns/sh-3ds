/* Focused offline fixtures. Never part of the hardware game object graph. */
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
#include "bodyprog/dms.h"
#include "bodyprog/sys/joy.h"
#include "maps/shared.h"
#include "maps/characters/romper.h"
#include <stddef.h>
#include <string.h>

extern void DahliaAnimInfos_Init(void),RomperAnimInfos_Init(void),GroanerAnimInfos_Init(void);
extern void map2_s00_MapEvent_KGordonKeyUse(void),map2_s00_func_800EA960(void),map2_s00_func_800EAD2C(void);
extern void map2_s01_func_800CED88(void);
extern void map2_s02_Romper_Init(s_SubCharacter*),map2_s02_sharedFunc_800E6420_2_s02(s_SubCharacter*);
extern void map2_s02_Romper_Control_7(s_SubCharacter*),map2_s02_Romper_Control_8(s_SubCharacter*);
extern SVECTOR3 map2_s00_D_800F5344;
extern q19_12 map2_s01_g_Cutscene_Timer;

unsigned post_probe_out[64];
const unsigned post_probe_meta[]={sizeof(s_Savegame),offsetof(s_Savegame,eventFlags),
    offsetof(s_SysWork,sysStateSteps),offsetof(s_SysWork,sysState)};
const unsigned post_probe_items[]={InvItemId_KGordonKey,InvItemId_Flauros,InvItemId_DrawbridgeKey,InvItemId_Shotgun};
static s_Savegame_Container saved;

_Static_assert(sizeof(s_Savegame)==636,"Original save ABI");
_Static_assert(offsetof(s_SysWork,sysState)==8 && sizeof(e_SysState)==4,"Runtime observer ABI");
_Static_assert(offsetof(s_MapOverlayHdr,playerStub_F8)==0xF8,"Original player callback slot");
_Static_assert(offsetof(s_MapOverlayHdr,charaCollisionReset)==0x154,"Original collision callback slot");

unsigned post_probe_count(unsigned item)
{
    unsigned count=0;
    for(unsigned i=0;i<40;i++)if(g_SavegamePtr->items[i].id_0==item)count+=g_SavegamePtr->items[i].count_1;
    return count;
}

void post_probe_reset(unsigned map)
{
    memset(&g_SysWork,0,sizeof(g_SysWork));
    Settings_RestoreDefaults();GameBoot_SavegameInitialize(map,GameDifficulty_Normal);
    /* Synthetic post-school handoff, not a fresh Cafe exit. */
    Savegame_EventFlagSet(EventFlag_146);
    Savegame_EventFlagSet(EventFlag_132);Savegame_EventFlagSet(EventFlag_134);
    g_OvlDynamic=PSX_ADDR(0xC9578);
    Game3ds_MapBind(map);
    memset(g_Controller0,0,sizeof(*g_Controller0));
    g_SysWork.playerWork.player.health=Q12(100.0f);
    g_DeltaTime=TIMESTEP_30_FPS;g_DeltaTimeRaw=g_DeltaTime;
    DahliaAnimInfos_Init();RomperAnimInfos_Init();GroanerAnimInfos_Init();
    memset(post_probe_out,0,sizeof(post_probe_out));
}

unsigned post_probe_header(void)
{
    unsigned count=0,uses=0,transitions=0;
    for(s_EventData* e=g_MapOverlayHdr.mapEvents;e->triggerType!=TriggerType_EndOfArray;e++) {
        if(++count>256)return 1;
        if(e->sysState==SysState_EventCallback && !g_MapOverlayHdr.mapEventFuncs[e->eventParam])return 2;
        uses+=e->activationType==TriggerActivationType_Item;
        transitions+=e->sysState==SysState_LoadOverlay;
    }
    post_probe_out[0]=count;post_probe_out[1]=uses;post_probe_out[2]=transitions;
    post_probe_out[3]=(unsigned)g_MapOverlayHdr.playerStub_F8;
    post_probe_out[4]=(unsigned)g_MapOverlayHdr.charaCollisionReset;
    for(unsigned i=0;i<ARRAY_SIZE(g_MapOverlayHdr.charaUpdateFuncs);i++)post_probe_out[8+i]=(unsigned)g_MapOverlayHdr.charaUpdateFuncs[i];
    return 0;
}

/* The same inventory/event handshake as the existing School subsystem oracle. */
unsigned post_probe_use(unsigned index)
{
    s_EventData* target=&g_MapOverlayHdr.mapEvents[index];
    if(target->activationType!=TriggerActivationType_Item)return 1;
    if(target->requiredEventFlag)Savegame_EventFlagSetAlt(target->requiredEventFlag);
    s_MapPoint2d* point=&g_MapOverlayHdr.mapPoints[target->pointOfInterestIdx];
    q3_12 yaw=target->triggerType==TriggerType_TouchObbFacing ? Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(point->triggerParam0)+2048):0;
    s_SubCharacter* p=&g_SysWork.playerWork.player;
    p->position.vx=point->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    p->position.vz=point->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));p->rotation.vy=yaw;
    Event_Update(true);
    unsigned slot;
    for(slot=0;slot<5 && g_ItemTriggerItemIds[slot]!=target->requiredItemId;slot++);
    post_probe_out[0]=slot;if(slot==5)return 2;
    g_SavegamePtr->items[0].id_0=target->requiredItemId;g_SavegamePtr->items[0].count_1=1;
    Inventory_ItemUse(0);
    if(g_SysWork.playerWork.extra.lastUsedItem!=target->requiredItemId)return 3;
    Event_Update(true);
    post_probe_out[1]=g_MapEventLastUsedItem;post_probe_out[2]=g_MapEventParam;
    post_probe_out[3]=g_MapEventData-g_MapOverlayHdr.mapEvents;
    if(g_MapEventSysState!=target->sysState || g_MapEventParam!=target->eventParam)return 4;
    if(g_SysWork.playerWork.extra.lastUsedItem!=InvItemId_Unequipped)return 5;
    return 0;
}

void post_probe_pickup(unsigned index,unsigned step)
{
    g_MapEventData=&g_MapOverlayHdr.mapEvents[index];g_MapEventParam=g_MapEventData->eventParam;
    g_SysWork.sysStateSteps[1]=step;
    g_MapOverlayHdr.mapEventFuncs[g_MapEventParam]();
    post_probe_out[0]=Savegame_EventFlagGetAlt(g_MapEventData->disabledEventFlag);
    post_probe_out[1]=g_SysWork.sysState;
}

void post_probe_kgordon(void)
{
    map2_s00_MapEvent_KGordonKeyUse();
    post_probe_out[0]=post_probe_count(InvItemId_KGordonKey);
    post_probe_out[1]=Savegame_EventFlagGetAlt(EventFlag_M2S00_KGordonDoorOpen);
    post_probe_out[2]=Savegame_EventFlagGetAlt(EventFlag_MapMark_OldTown_KGordonArrowsOnly);
}

void post_probe_bridge(unsigned alternate,unsigned step)
{
    g_SysWork.sysStateSteps[0]=step;
    if(alternate)map2_s00_func_800EAD2C();else map2_s00_func_800EA960();
    post_probe_out[0]=Savegame_EventFlagGetAlt(EventFlag_164);
    post_probe_out[1]=Savegame_EventFlagGetAlt(EventFlag_165);
    post_probe_out[2]=Savegame_EventFlagGetAlt(EventFlag_166);
    post_probe_out[3]=g_SysWork.sysStateSteps[0];
    post_probe_out[4]=(s32)map2_s00_D_800F5344.vz;
    post_probe_out[5]=g_SysWork.sysState;
    post_probe_out[6]=g_Player_DisableControl;
    post_probe_out[7]=post_probe_count(InvItemId_DrawbridgeKey);
}

void post_probe_church(unsigned step,unsigned skip)
{
    g_SysWork.sysState=SysState_EventCallback;g_SysWork.sysStateSteps[0]=step;
    g_Controller0->clickedBtnFlags=skip?g_GameWorkPtr->config.controllerConfig.skip:0;
    map2_s01_g_Cutscene_Timer=NO_VALUE;
    map2_s01_func_800CED88();
    post_probe_out[0]=Savegame_EventFlagGetAlt(EventFlag_179);
    post_probe_out[1]=Savegame_EventFlagGetAlt(EventFlag_176);
    post_probe_out[2]=Savegame_EventFlagGetAlt(EventFlag_MapMark_FogCentralTown_HospitalCircle);
    post_probe_out[3]=g_SysWork.sysState;
    post_probe_out[4]=g_SysWork.sysStateSteps[0];
    post_probe_out[5]=g_Player_DisableControl;
}

void post_probe_fmv(void)
{
    g_MapEventData=&g_MapOverlayHdr.mapEvents[1];g_MapEventParam=g_MapEventData->eventParam;
    g_SysWork.sysStateSteps[0]=2;D_800A9A0C=1;
    SysState_Fmv_Update();
    post_probe_out[0]=Savegame_EventFlagGetAlt(EventFlag_181);
}

unsigned post_probe_save(unsigned map,unsigned phase)
{
    g_SavegamePtr->mapIdx=map;g_SavegamePtr->mapRoomIdx=3;
    Savegame_EventFlagSet(EventFlag_132);Savegame_EventFlagSet(EventFlag_134);
    if(phase>=1){Savegame_EventFlagSet(EventFlag_179);Savegame_EventFlagSet(EventFlag_181);}
    if(phase>=2){Savegame_EventFlagSet(EventFlag_164);Savegame_EventFlagSet(EventFlag_165);Savegame_EventFlagSet(EventFlag_166);}
    Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_Flauros,1,false);
    g_SavegamePtr->ovlEnemyStates[map]=0x1249;
    MemCard_GameDataCopy(&saved,g_SavegamePtr);
    if(!MemCard_ChecksumValidate(&saved.footer,(s8*)&saved.savegame,sizeof(saved)))return 1;
    if(memcmp(&saved.savegame,g_SavegamePtr,sizeof(s_Savegame)))return 2;
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));memcpy(g_SavegamePtr,&saved.savegame,sizeof(s_Savegame));
    if(g_SavegamePtr->mapIdx!=map || g_SavegamePtr->ovlEnemyStates[map]!=0x1249 || !post_probe_count(InvItemId_Flauros))return 3;
    if(phase>=1 && !Savegame_EventFlagGet(EventFlag_181))return 4;
    if(phase>=2 && !Savegame_EventFlagGet(EventFlag_166))return 5;
    return 0;
}

void post_probe_romper(unsigned difficulty,unsigned damage)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];memset(n,0,sizeof(*n));
    n->model.charaId=Chara_Romper;g_SavegamePtr->gameDifficulty=difficulty;
    map2_s02_Romper_Init(n);post_probe_out[0]=n->health;
    n->damage.amount=damage;map2_s02_sharedFunc_800E6420_2_s02(n);
    post_probe_out[1]=n->health;post_probe_out[2]=n->model.controlState;
    if(!n->health){
        n->model.anim.status=ANIM_STATUS(RomperAnim_JumpStunEnd,true);
        map2_s02_Romper_Control_7(n);post_probe_out[3]=n->model.controlState;
        g_SysWork.targetNpcIdx=NO_VALUE;map2_s02_Romper_Control_8(n);
    }
    post_probe_out[4]=n->health;post_probe_out[5]=n->collision.state;
}
