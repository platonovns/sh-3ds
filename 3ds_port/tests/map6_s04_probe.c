#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/memcard.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include <string.h>

_Static_assert(sizeof(s_Savegame) == 636, "Retail save ABI");
static s_Savegame_Container card;
static s_Savegame original;
extern void Inventory_ItemUse(s32 index);
extern void map6_s04_func_800E3244(void);
extern void map6_s04_MapEvent_CutsceneCybilDeath(void);

unsigned map6_s04_probe_entry(void)
{
    s_EventData *e = &g_MapOverlayHdr.mapEvents[9];
    return e->sysState != SysState_LoadOverlay || e->mapIdx != MapIdx_MAP6_S04 ||
           e->requiredEventFlag != EventFlag_433 || e->eventParam != 7;
}

unsigned map6_s04_probe_events(void)
{
    s_EventData *e = g_MapOverlayHdr.mapEvents;
    if (e[3].sysState != SysState_LoadOverlay || e[3].mapIdx != MapIdx_MAP7_S00 ||
        e[3].requiredEventFlag != EventFlag_451 || e[3].eventParam != 8) return 1;
    if (e[4].requiredEventFlag != EventFlag_440 || e[5].requiredEventFlag != EventFlag_441 ||
        e[6].requiredEventFlag != EventFlag_442 || e[7].requiredEventFlag != EventFlag_443 ||
        e[8].requiredEventFlag != EventFlag_444) return 2;
    if (e[9].requiredEventFlag != EventFlag_446 || e[10].requiredEventFlag != EventFlag_470 ||
        e[10].eventParam != 7 || e[11].requiredEventFlag != EventFlag_448 ||
        e[11].disabledEventFlag != EventFlag_449 || e[11].eventParam != 8) return 3;
    if (e[12].requiredEventFlag != EventFlag_450 || e[13].requiredEventFlag != EventFlag_468) return 4;
    return 0;
}

unsigned map6_s04_probe_liquid(unsigned near)
{
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    memset(&g_SysWork.playerWork, 0, sizeof(g_SysWork.playerWork));
    memset(&g_SysWork.npcs[0], 0, sizeof(g_SysWork.npcs[0]));
    g_SavegamePtr->mapIdx = MapIdx_MAP6_S04;
    g_SavegamePtr->items[0].id_0 = InvItemId_UnknownLiquid;
    g_SysWork.npcs[0].model.charaId = Chara_MonsterCybil;
    g_SysWork.npcs[0].position.vx = near ? Q12(0.1f) : Q12(4.0f);
    Inventory_ItemUse(0);
    return Savegame_EventFlagGet(EventFlag_448) != near ||
           g_SavegamePtr->items[0].id_0 != InvItemId_UnknownLiquid;
}

unsigned map6_s04_probe_outcome(unsigned rescued)
{
    Savegame_EventFlagClear(EventFlag_447);
    Savegame_EventFlagClear(EventFlag_449);
    Savegame_EventFlagClear(EventFlag_450);
    g_SysWork.sysStateSteps[0] = 99;
    if (rescued) map6_s04_func_800E3244();
    else map6_s04_MapEvent_CutsceneCybilDeath();
    return !Savegame_EventFlagGet(EventFlag_450) ||
           !!Savegame_EventFlagGet(EventFlag_449) != rescued ||
           !!Savegame_EventFlagGet(EventFlag_447) == rescued;
}

unsigned map6_s04_probe_save(unsigned rescued)
{
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    g_SavegamePtr->mapIdx = MapIdx_MAP6_S04;
    Savegame_EventFlagSet(EventFlag_391);
    if (rescued) { Savegame_EventFlagSet(EventFlag_448); Savegame_EventFlagSet(EventFlag_449); }
    else { Savegame_EventFlagSet(EventFlag_446); Savegame_EventFlagSet(EventFlag_447); }
    Savegame_EventFlagSet(EventFlag_450);
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_UnknownLiquid, 1, false);
    memcpy(&original, g_SavegamePtr, sizeof(original));
    MemCard_GameDataCopy(&card, g_SavegamePtr);
    if (!MemCard_ChecksumValidate(&card.footer, (s8*)&card.savegame, sizeof(card))) return 1;
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    memcpy(g_SavegamePtr, &card.savegame, sizeof(*g_SavegamePtr));
    return memcmp(&original, g_SavegamePtr, sizeof(original)) != 0;
}
