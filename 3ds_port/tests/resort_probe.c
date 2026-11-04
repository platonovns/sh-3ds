/* Offline save fixtures only; never part of the game. */
#include "bodyprog/bodyprog.h"
#include "bodyprog/memcard.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include <string.h>
_Static_assert(sizeof(s_Savegame)==636,"Retail save size");
static s_Savegame_Container copy;
static s_Savegame before;
unsigned resort_probe_save(unsigned phase)
{
    const unsigned flags[]={358,371,375,376,377,378,379,380,386,389,390,391,394,395,396,397,398,402,403,423,424,1024};
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));
    g_SavegamePtr->mapIdx=phase<2?MapIdx_MAP5_S01:phase<5?MapIdx_MAP5_S03:phase==5?MapIdx_MAP6_S00:MapIdx_MAP6_S01;
    Savegame_EventFlagSet(358);
    if(phase>=1) {Savegame_EventFlagSet(402);Savegame_EventFlagSet(403);}
    if(phase==2 || phase==3 || phase==4) {
        Savegame_EventFlagSet(378);Savegame_EventFlagSet(379);Savegame_EventFlagSet(380);
        Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_Receipt,1,false);
        if(phase==2) Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_KaufmannKey,1,false);
        if(phase>=3) {Savegame_EventFlagSet(394);Savegame_EventFlagSet(376);Savegame_EventFlagSet(386);Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_Magnet,1,false);}
        if(phase==4) {Savegame_EventFlagSet(390);Savegame_EventFlagSet(391);Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_MotorcycleKey,1,false);}
    }
    if(phase>=6) {Savegame_EventFlagSet(423);Savegame_EventFlagSet(424);Savegame_EventFlagSet(1024);} if(phase==7) {Savegame_EventFlagSet(390);Savegame_EventFlagSet(391);Savegame_EventFlagSet(394);Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_Receipt,1,false);Event_InvItemCmd(InvItemCmd_AddItem,InvItemId_MotorcycleKey,1,false);}
    (void)flags;
    memcpy(&before,g_SavegamePtr,sizeof(before));MemCard_GameDataCopy(&copy,g_SavegamePtr);
    if(!MemCard_ChecksumValidate(&copy.footer,(s8*)&copy.savegame,sizeof(copy)))return 1;
    if(memcmp(&before,&copy.savegame,sizeof(before)))return 2;
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));memcpy(g_SavegamePtr,&copy.savegame,sizeof(*g_SavegamePtr));
    if(memcmp(&before,g_SavegamePtr,sizeof(before)))return 3;
    ((u8*)&copy.savegame)[19]^=1;
    return MemCard_ChecksumValidate(&copy.footer,(s8*)&copy.savegame,sizeof(copy))?4:0;
}
#include "bodyprog/item_screens.h"
#include "bodyprog/events/events_main.h"
unsigned resort_probe_wrong_use(unsigned event)
{
    s_EventData* e=&g_MapOverlayHdr.mapEvents[event];
    s_MapPoint2d* p=&g_MapOverlayHdr.mapPoints[e->pointOfInterestIdx];
    if(e->requiredEventFlag) Savegame_EventFlagSetAlt(e->requiredEventFlag);
    if(e->disabledEventFlag) Savegame_EventFlagClear(e->disabledEventFlag);
    g_SysWork.playerWork.player.position.vx=p->positionX+Q12(100.0f);
    g_SysWork.playerWork.player.position.vz=p->positionZ;
    Event_Update(true);
    g_SavegamePtr->items[0].id_0=e->requiredItemId;g_SavegamePtr->items[0].count_1=1;
    Inventory_ItemUse(0);
    return g_SysWork.playerWork.extra.lastUsedItem==InvItemId_Unequipped && g_SavegamePtr->items[0].count_1==1 ? 0 : 1;
}
extern void map5_s02_Ai_Stalker_Init(s_SubCharacter*);
extern void map5_s02_sharedFunc_800D3308_0_s00(s_SubCharacter*);
extern q19_12 map5_s02_sharedData_800E3A20_0_s00, map5_s02_sharedData_800E3A24_0_s00, map5_s02_sharedData_800E3A28_0_s00, map5_s02_sharedData_800E3A2C_0_s00;
unsigned resort_stalker_out[4];
void resort_probe_stalker(unsigned lethal)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];
    memset(n,0,sizeof(*n));n->model.charaId=Chara_Stalker;n->model.stateStep=8;
    map5_s02_sharedData_800E3A20_0_s00=Q12(350.0f);map5_s02_sharedData_800E3A24_0_s00=Q12(100.0f);
    map5_s02_sharedData_800E3A28_0_s00=Q12(3.0f);map5_s02_sharedData_800E3A2C_0_s00=Q12(50.0f);
    map5_s02_Ai_Stalker_Init(n);resort_stalker_out[0]=n->health;
    n->damage.amount=lethal?Q12(350.0f):Q12(10.0f);n->damage.position.vz=Q12(1.0f);
    map5_s02_sharedFunc_800D3308_0_s00(n);
    resort_stalker_out[1]=n->health;resort_stalker_out[2]=n->model.controlState;resort_stalker_out[3]=n->model.anim.status;
}
#include "maps/characters/romper.h"
extern void map6_s00_Romper_Init(s_SubCharacter*),map6_s00_sharedFunc_800E6420_2_s02(s_SubCharacter*);
extern void map6_s00_Romper_Control_7(s_SubCharacter*),map6_s00_Romper_Control_8(s_SubCharacter*);
unsigned resort_romper_out[6];
void resort_probe_romper(unsigned lethal)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];memset(n,0,sizeof(*n));n->model.charaId=Chara_Romper;
    map6_s00_Romper_Init(n);resort_romper_out[0]=n->health;
    n->damage.amount=lethal?n->health:Q12(10.0f);map6_s00_sharedFunc_800E6420_2_s02(n);
    resort_romper_out[1]=n->health;resort_romper_out[2]=n->model.controlState;
    if(!n->health){n->model.anim.status=ANIM_STATUS(RomperAnim_JumpStunEnd,true);map6_s00_Romper_Control_7(n);resort_romper_out[3]=n->model.controlState;g_SysWork.targetNpcIdx=NO_VALUE;map6_s00_Romper_Control_8(n);}
    resort_romper_out[4]=n->health;resort_romper_out[5]=n->collision.state;
}
extern void map6_s00_Ai_Groaner_Init(s_SubCharacter*),map6_s00_sharedFunc_800E33DC_2_s00(s_SubCharacter*);
unsigned resort_groaner_out[3];
void resort_probe_groaner(unsigned lethal)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];memset(n,0,sizeof(*n));n->model.charaId=Chara_Groaner;n->model.stateStep=3;
    map6_s00_Ai_Groaner_Init(n);resort_groaner_out[0]=n->health;
    n->damage.amount=lethal?n->health:Q12(10.0f);n->damage.position.vz=Q12(1.0f);map6_s00_sharedFunc_800E33DC_2_s00(n);
    resort_groaner_out[1]=n->health;resort_groaner_out[2]=n->model.controlState;
}
