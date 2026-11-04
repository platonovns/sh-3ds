/* Offline fixture only; not linked into the game. */
#include "bodyprog/bodyprog.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/memcard.h"
#include "bodyprog/events/events_main.h"
#include "bodyprog/math/math.h"
#include "bodyprog/player.h"
#include "game3ds.h"
#include <string.h>
#include "maps/characters/hanged_scratcher.h"
#include "maps/characters/creeper.h"

_Static_assert(sizeof(s_Savegame) == 636, "Retail save size");
static s_Savegame_Container copy;
static s_Savegame before;
extern void map5_s00_HangedScratcher_Init(s_SubCharacter*);
extern void map5_s00_sharedFunc_800CFF74_5_s00(s_SubCharacter*);
extern void map5_s00_Creeper_Init(s_SubCharacter*);
extern void map5_s00_sharedFunc_800D7EE8_1_s02(s_SubCharacter*);
extern void map5_s00_HangedScratcher_Control_4(s_SubCharacter*);
extern void map5_s00_HangedScratcher_CollisionUpdate(s_SubCharacter*);
extern void map5_s00_sharedFunc_800D3300_5_s00(s_SubCharacter*);
extern void map5_s00_Creeper_ControlAttack(s_SubCharacter*);
extern void map5_s00_Creeper_CollisionUpdate(s_SubCharacter*);
extern s_AnimInfo HANGED_SCRATCHER_ANIM_INFOS[54], CREEPER_ANIM_INFOS[36], GROANER_M5S01_ANIM_INFOS[48];
unsigned sewer1_enemy_out[4];
void sewer1_probe_attack(unsigned creeper)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];
    memset(n,0,sizeof(*n));
    g_SysWork.playerWork.player.position.vz=Q12(0.5f);
    if(creeper) {
        n->model.charaId=Chara_Creeper;
        n->model.anim.status=ANIM_STATUS(CreeperAnim_Attack,true);
        n->model.anim.time=Q12(9.0f);
        map5_s00_Creeper_ControlAttack(n);
        map5_s00_Creeper_CollisionUpdate(n);
        sewer1_enemy_out[0]=n->collision.box.field_8;
    } else {
        n->model.charaId=Chara_HangedScratcher;
        n->model.anim.status=ANIM_STATUS(HangedScratcherAnim_4,true);
        n->model.anim.time=Q12(104.0f);
        map5_s00_HangedScratcher_Control_4(n);
        map5_s00_HangedScratcher_CollisionUpdate(n);
        map5_s00_sharedFunc_800D3300_5_s00(n);
    }
}
void sewer1_probe_creeper(void)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];
    memset(n,0,sizeof(*n)); n->model.charaId=Chara_Creeper;
    map5_s00_Creeper_Init(n);
    n->damage.amount=Q12(10.0f);
    map5_s00_sharedFunc_800D7EE8_1_s02(n);
    sewer1_enemy_out[0]=n->health; sewer1_enemy_out[1]=n->damage.amount;
    n->model.anim.status=ANIM_STATUS(CreeperAnim_Stun,true);
    n->damage.amount=Q12(10.0f);
    map5_s00_sharedFunc_800D7EE8_1_s02(n);
    sewer1_enemy_out[2]=n->health; sewer1_enemy_out[3]=n->damage.amount;
}
void sewer1_probe_flag_set(unsigned flag) { Savegame_EventFlagSetAlt(flag); }
unsigned sewer1_probe_anim_reload(void)
{
    Game3ds_MapBind(MapIdx_MAP5_S00);
    q19_12 h=HANGED_SCRATCHER_ANIM_INFOS[9].duration.constant;
    q19_12 c=CREEPER_ANIM_INFOS[9].duration.constant;
    HANGED_SCRATCHER_ANIM_INFOS[9].duration.constant=123;
    CREEPER_ANIM_INFOS[9].duration.constant=456;
    Game3ds_MapBind(MapIdx_MAP5_S00);
    if(HANGED_SCRATCHER_ANIM_INFOS[9].duration.constant!=h || CREEPER_ANIM_INFOS[9].duration.constant!=c) return 1;
    Game3ds_MapBind(MapIdx_MAP5_S01);
    q19_12 g=GROANER_M5S01_ANIM_INFOS[5].duration.constant;
    GROANER_M5S01_ANIM_INFOS[5].duration.constant=789;
    Game3ds_MapBind(MapIdx_MAP5_S01);
    return GROANER_M5S01_ANIM_INFOS[5].duration.constant==g ? 0 : 2;
}
unsigned sewer1_probe_invalid_use(unsigned event, unsigned unlocked)
{
    s_EventData* e=&g_MapOverlayHdr.mapEvents[event];
    s_MapPoint2d* p=&g_MapOverlayHdr.mapPoints[e->pointOfInterestIdx];
    q3_12 yaw=Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(p->triggerParam0)+2048);
    Savegame_EventFlagSet(355); Savegame_EventFlagSetAlt(e->requiredEventFlag);
    if (unlocked) Savegame_EventFlagSetAlt(e->disabledEventFlag);
    g_SysWork.playerWork.player.position.vx=p->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    g_SysWork.playerWork.player.position.vz=p->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));
    g_SysWork.playerWork.player.rotation.vy=yaw;
    if (!unlocked) g_SysWork.playerWork.player.position.vx+=Q12(100.0f);
    Event_Update(true);
    g_SavegamePtr->items[0].id_0=e->requiredItemId; g_SavegamePtr->items[0].count_1=1;
    Inventory_ItemUse(0);
    if (g_SysWork.playerWork.extra.lastUsedItem!=InvItemId_Unequipped) return 1;
    return g_SavegamePtr->items[0].count_1==1 ? 0 : 2;
}

void sewer1_probe_hanged(unsigned lethal)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];
    memset(n,0,sizeof(*n));
    n->model.charaId=Chara_HangedScratcher; n->model.stateStep=7;
    map5_s00_HangedScratcher_Init(n);
    sewer1_enemy_out[0]=n->health;
    n->damage.amount=lethal ? n->health : Q12(100.0f);
    map5_s00_sharedFunc_800CFF74_5_s00(n);
    sewer1_enemy_out[1]=n->health; sewer1_enemy_out[2]=n->model.controlState;
    sewer1_enemy_out[3]=n->damage.amount;
}

unsigned sewer1_probe_save(unsigned phase)
{
    const unsigned flags[] = {193, 350, 352, 353, 354, 355, 356, 357, 358, 359, 361, 1371, 1391};
    g_SavegamePtr->mapIdx = phase == 0 ? MapIdx_MAP2_S00 : phase == 5 ? MapIdx_MAP5_S01 : MapIdx_MAP5_S00;
    g_SavegamePtr->mapRoomIdx = phase;
    g_SavegamePtr->ovlEnemyStates[MapIdx_MAP5_S00] = 0x1249;
    for (unsigned i=0;i<sizeof(flags)/sizeof(flags[0]);i++) Savegame_EventFlagClear(flags[i]);
    Savegame_EventFlagSet(193); Savegame_EventFlagSet(350); Savegame_EventFlagSet(352);
    if (phase >= 1) { Savegame_EventFlagSet(353); Savegame_EventFlagSet(355); Savegame_EventFlagSet(361); }
    if (phase >= 2) Savegame_EventFlagSet(1371);
    if (phase >= 3) Savegame_EventFlagSet(354);
    if (phase >= 4) Savegame_EventFlagSet(1391);
    if (phase == 5) Savegame_EventFlagSet(358);
    if (phase == 1) Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_SewerKey, 1, false);
    if (phase == 3) Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_SewerExitKey, 1, false);
    memcpy(&before,g_SavegamePtr,sizeof(before));
    MemCard_GameDataCopy(&copy,g_SavegamePtr);
    if (!MemCard_ChecksumValidate(&copy.footer,(s8*)&copy.savegame,sizeof(copy))) return 1;
    if (memcmp(&before,&copy.savegame,sizeof(before))) return 2;
    memset(g_SavegamePtr,0,sizeof(*g_SavegamePtr));
    memcpy(g_SavegamePtr,&copy.savegame,sizeof(*g_SavegamePtr));
    if (memcmp(&before,g_SavegamePtr,sizeof(before))) return 3;
    ((u8*)&copy.savegame)[19] ^= 1;
    return MemCard_ChecksumValidate(&copy.footer,(s8*)&copy.savegame,sizeof(copy)) ? 4 : 0;
}
