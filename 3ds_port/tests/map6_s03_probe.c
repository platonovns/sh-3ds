/* Offline-only second-sewer tests against the linked game. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/memcard.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "maps/characters/hanged_scratcher.h"
#include <string.h>

_Static_assert(sizeof(s_Savegame) == 636, "Retail save ABI");
static s_Savegame_Container card;
static s_Savegame original;
extern void map6_s03_HangedScratcher_Init(s_SubCharacter*);
extern void map6_s03_sharedFunc_800CFF74_5_s00(s_SubCharacter*);
extern void map6_s03_Ai_Stalker_Init(s_SubCharacter*);
extern void map6_s03_sharedFunc_800D3308_0_s00(s_SubCharacter*);
extern q19_12 map6_s03_sharedData_800E3A20_0_s00, map6_s03_sharedData_800E3A24_0_s00;
extern q19_12 map6_s03_sharedData_800E3A28_0_s00, map6_s03_sharedData_800E3A2C_0_s00;
extern s_AnimInfo HANGED_SCRATCHER_ANIM_INFOS[], STALKER_M5S02_ANIM_INFOS[];

unsigned map6_s03_probe_entrance(void)
{
    for (s_EventData *e = g_MapOverlayHdr.mapEvents; e->triggerType != TriggerType_EndOfArray; ++e)
        if (e->sysState == SysState_LoadOverlay && e->mapIdx == MapIdx_MAP6_S03)
            return e->requiredEventFlag != EventFlag_411 || e->eventParam != 11;
    return 2;
}

unsigned map6_s03_probe_unlock_entrance(void)
{
    for (s_EventData *e = g_MapOverlayHdr.mapEvents; e->triggerType != TriggerType_EndOfArray; ++e) {
        if (e->sysState == SysState_ReadMessage && e->requiredEventFlag == EventFlag_426 &&
            e->disabledEventFlag == EventFlag_411) {
            Savegame_EventFlagClear(EventFlag_411);
            g_MapEventData = e;
            g_MapEventParam = e->eventParam;
            SysState_ReadMessage_Update();
            return !Savegame_EventFlagGet(EventFlag_411);
        }
    }
    return 2;
}

unsigned map6_s03_probe_edges(void)
{
    s_EventData *e = g_MapOverlayHdr.mapEvents;
    if (e[3].sysState != SysState_Fmv || e[3].eventParam != 9 ||
        e[3].requiredEventFlag != EventFlag_426 || e[3].disabledEventFlag != EventFlag_438) return 1;
    if (e[4].disabledEventFlag != EventFlag_431 || e[5].requiredEventFlag != EventFlag_431 ||
        e[5].disabledEventFlag != EventFlag_432 || e[5].sysState != SysState_LoadRoom) return 2;
    if (e[9].sysState != SysState_LoadOverlay || e[9].mapIdx != MapIdx_MAP6_S04 ||
        e[9].requiredEventFlag != EventFlag_433 || e[9].eventParam != 7) return 3;
    if (e[12].disabledEventFlag != EventFlag_M6S03_PickupMap ||
        e[12].sysState != SysState_EventCallback) return 4;
    return 0;
}

unsigned map6_s03_probe_map_granted(void)
{
    return !Savegame_EventFlagGet(EventFlag_M6S03_PickupMap) ||
           !(g_SavegamePtr->paperMapFlags & (1 << 15));
}

unsigned map6_s03_probe_save(unsigned phase)
{
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    g_SavegamePtr->mapIdx = MapIdx_MAP6_S03;
    g_SavegamePtr->mapRoomIdx = 17;
    Savegame_EventFlagSet(EventFlag_410);
    Savegame_EventFlagSet(EventFlag_426);
    if (phase & 1) { Savegame_EventFlagSet(EventFlag_431); Savegame_EventFlagSet(EventFlag_432); }
    if (phase & 2) { Savegame_EventFlagSet(EventFlag_433); Savegame_EventFlagSet(EventFlag_435); }
    if (phase & 4) Savegame_EventFlagSet(EventFlag_391);
    if (phase & 8) Savegame_EventFlagSet(EventFlag_449);
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_UnknownLiquid, 1, false);
    memcpy(&original, g_SavegamePtr, sizeof(original));
    MemCard_GameDataCopy(&card, g_SavegamePtr);
    if (!MemCard_ChecksumValidate(&card.footer, (s8*)&card.savegame, sizeof(card))) return 1;
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    memcpy(g_SavegamePtr, &card.savegame, sizeof(*g_SavegamePtr));
    if (memcmp(&original, g_SavegamePtr, sizeof(original))) return 2;
    ((u8*)&card.savegame)[19] ^= 1;
    return MemCard_ChecksumValidate(&card.footer, (s8*)&card.savegame, sizeof(card)) ? 3 : 0;
}

unsigned map6_s03_probe_enemy(unsigned lethal)
{
    s_SubCharacter* n = &g_SysWork.npcs[0];
    memset(n, 0, sizeof(*n));
    n->model.charaId = Chara_HangedScratcher;
    n->model.stateStep = 7;
    map6_s03_HangedScratcher_Init(n);
    if (n->health != Q12(350.0f)) return 1;
    n->damage.amount = lethal ? Q12(350.0f) : Q12(100.0f);
    map6_s03_sharedFunc_800CFF74_5_s00(n);
    return n->health != (lethal ? 0 : Q12(250.0f));
}

unsigned map6_s03_probe_anim_reload(void)
{
    Game3ds_MapBind(MapIdx_MAP6_S03);
    q19_12 h = HANGED_SCRATCHER_ANIM_INFOS[9].duration.constant;
    q19_12 s = STALKER_M5S02_ANIM_INFOS[9].duration.constant;
    HANGED_SCRATCHER_ANIM_INFOS[9].duration.constant = 123;
    STALKER_M5S02_ANIM_INFOS[9].duration.constant = 456;
    Game3ds_MapBind(MapIdx_MAP6_S03);
    return HANGED_SCRATCHER_ANIM_INFOS[9].duration.constant != h ||
           STALKER_M5S02_ANIM_INFOS[9].duration.constant != s;
}

unsigned map6_s03_probe_mumbler(unsigned lethal)
{
    s_SubCharacter* n = &g_SysWork.npcs[0];
    memset(n, 0, sizeof(*n));
    n->model.charaId = Chara_Mumbler;
    n->model.stateStep = 8;
    map6_s03_sharedData_800E3A20_0_s00 = Q12(350.0f);
    map6_s03_sharedData_800E3A24_0_s00 = Q12(100.0f);
    map6_s03_sharedData_800E3A28_0_s00 = Q12(3.0f);
    map6_s03_sharedData_800E3A2C_0_s00 = Q12(50.0f);
    map6_s03_Ai_Stalker_Init(n);
    if (n->health != Q12(525.0f)) return 1;
    n->damage.amount = lethal ? n->health : Q12(10.0f);
    n->damage.position.vz = Q12(1.0f);
    map6_s03_sharedFunc_800D3308_0_s00(n);
    return n->health != (lethal ? 0 : Q12(515.0f));
}
