/* Internal component fixture, never linked into a game build. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/memcard.h"
#include "bodyprog/events/events_main.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "bodyprog/math/math.h"
#include "bodyprog/player.h"
#include "maps/map4/map4_s03.h"
#include "maps/characters/twinfeeler.h"
#include "maps/characters/floatstinger.h"
#include <string.h>

static s_Savegame_Container copy;
extern void map4_s03_func_800D3E58(s_SubCharacter*);
extern void map4_s03_Twinfeeler_Control_9(s_SubCharacter*);
extern void map4_s05_Floatstinger_Init(s_SubCharacter*);
extern void map4_s05_func_800D1968(s_SubCharacter*);
extern void map4_s05_func_800D2B90(s_SubCharacter*);
unsigned block3_probe_out[16];

void block3_probe_twinfeeler(unsigned lethal)
{
    s_SubCharacter* n = &g_SysWork.npcs[0];
    memset(n,0,sizeof(*n));
    n->model.charaId=Chara_Twinfeeler;
    n->model.controlState=TwinfeelerControl_4;
    n->model.anim.status=ANIM_STATUS(TwinfeelerAnim_Idle,false);
    n->health=Q12(3000.0f);
    n->damage.amount=lethal?Q12(3000.0f):Q12(100.0f);
    map4_s03_func_800D3E58(n);
    block3_probe_out[0]=n->health;
    block3_probe_out[1]=n->model.controlState;
    block3_probe_out[2]=n->damage.amount;
    if(lethal && n->model.controlState==TwinfeelerControl_9) {
        n->model.stateStep=6;
        n->model.anim.status=ANIM_STATUS(TwinfeelerAnim_Idle,false);
        map4_s03_Twinfeeler_Control_9(n);
    }
    block3_probe_out[3]=Savegame_EventFlagGet(EventFlag_326);
}

void block3_probe_floatstinger(unsigned difficulty,unsigned lethal)
{
    s_SubCharacter* n=&g_SysWork.npcs[0];
    memset(n,0,sizeof(*n));
    n->model.charaId=Chara_Floatstinger;
    n->model.stateStep=4;
    g_SavegamePtr->gameDifficulty=difficulty;
    map4_s05_Floatstinger_Init(n);
    block3_probe_out[0]=n->health;
    if(lethal)n->health=Q12(100.0f);
    n->damage.amount=Q12(100.0f);
    map4_s05_func_800D1968(n);
    block3_probe_out[1]=n->health;
    block3_probe_out[2]=n->model.controlState;
    block3_probe_out[3]=n->damage.amount;
    if(lethal && n->health==0)map4_s05_func_800D2B90(n);
    block3_probe_out[4]=Savegame_EventFlagGet(EventFlag_350);
}
static const unsigned flags[] = {190, 296, 306, 319, 320, 321, 323, 324, 326, 327,
                                 330, 331, 332, 337, 338, 339, 340, 346, 347, 348, 349, 350, 351, 352};
unsigned block3_probe_key_use(void)
{
    s_EventData* e = &g_MapOverlayHdr.mapEvents[10];
    Savegame_EventFlagSet(296);
    Savegame_EventFlagClear(190);
    s_MapPoint2d* point = &g_MapOverlayHdr.mapPoints[e->pointOfInterestIdx];
    q3_12 yaw = Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(point->triggerParam0)+2048);
    s_SubCharacter* player = &g_SysWork.playerWork.player;
    player->position.vx = point->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    player->position.vz = point->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));
    player->rotation.vy = yaw;
    Event_Update(true);
    unsigned trigger;
    for(trigger=0;trigger<5 && g_ItemTriggerItemIds[trigger]!=InvItemId_AntiqueShopKey;trigger++);
    if(trigger==5)return 1;
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_AntiqueShopKey, 1, false);
    unsigned slot;
    for(slot=0;slot<40 && g_SavegamePtr->items[slot].id_0!=InvItemId_AntiqueShopKey;slot++);
    if(slot==40)return 2;
    Inventory_ItemUse(slot);
    if(g_SysWork.playerWork.extra.lastUsedItem!=InvItemId_AntiqueShopKey)return 3;
    Event_Update(true);
    if(g_MapEventSysState!=e->sysState || g_MapEventParam!=e->eventParam)return 4;
    if(g_SysWork.playerWork.extra.lastUsedItem!=InvItemId_Unequipped)return 5;
    return 0;
}
unsigned block3_probe_save(unsigned map, unsigned phase)
{
    g_SavegamePtr->mapIdx = map;
    g_SavegamePtr->mapRoomIdx = 3;
    g_SavegamePtr->playerHealth = Q12(73.0f);
    g_SavegamePtr->playerPositionX = Q12(-118.0f);
    g_SavegamePtr->playerPositionZ = Q12(108.0f);
    g_SavegamePtr->ovlEnemyStates[map] = 0x1249;
    for (unsigned i=0; i<ARRAY_SIZE(flags); i++) {
        if ((i+phase)%3) Savegame_EventFlagSet(flags[i]);
        else Savegame_EventFlagClear(flags[i]);
    }
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_UnknownLiquid, 1, false);
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_Axe, 1, false);
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_HuntingRifle, 1, false);
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_RifleShells, 8, false);
    MemCard_GameDataCopy(&copy, g_SavegamePtr);
    if (!MemCard_ChecksumValidate(&copy.footer, (s8*)&copy.savegame, sizeof(copy))) return 1;
    if (memcmp(&copy.savegame, g_SavegamePtr, sizeof(s_Savegame))) return 2;
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    memcpy(g_SavegamePtr, &copy.savegame, sizeof(s_Savegame));
    if (g_SavegamePtr->mapIdx != map || g_SavegamePtr->ovlEnemyStates[map] != 0x1249 ||
        g_SavegamePtr->playerHealth != Q12(73.0f) || g_SavegamePtr->playerPositionX != Q12(-118.0f) ||
        g_SavegamePtr->playerPositionZ != Q12(108.0f)) return 3;
    for (unsigned i=0; i<ARRAY_SIZE(flags); i++)
        if (!!Savegame_EventFlagGet(flags[i]) != !!((i+phase)%3)) return 4;
    ((u8*)&copy.savegame)[19] ^= 1;
    if (MemCard_ChecksumValidate(&copy.footer, (s8*)&copy.savegame, sizeof(copy))) return 5;
    return 0;
}
