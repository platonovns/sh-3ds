#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/memcard.h"
#include <string.h>

_Static_assert(sizeof(s_Savegame) == 636, "Retail save ABI");
static s_Savegame_Container card;
static s_Savegame original;
extern void map7_s00_func_800D0B64(void);

unsigned map7_probe_entry_complete(void)
{
    Savegame_EventFlagClear(EventFlag_471);
    g_SysWork.sysStateSteps[0] = 99;
    map7_s00_func_800D0B64();
    return !Savegame_EventFlagGet(EventFlag_471) ||
           g_SysWork.playerWork.player.position.vx != Q12(17.8f) ||
           g_SysWork.playerWork.player.position.vz != Q12(-137.7f);
}

unsigned map7_probe_edges(unsigned target, unsigned required, unsigned param)
{
    s_EventData *e = g_MapOverlayHdr.mapEvents;
    for (unsigned i = 0; i < 400 && e[i].triggerType != TriggerType_EndOfArray; ++i)
        if (e[i].sysState == SysState_LoadOverlay && e[i].mapIdx == target &&
            e[i].requiredEventFlag == required && e[i].eventParam == param) return 0;
    return 1;
}

unsigned map7_probe_key(unsigned item, unsigned required, unsigned param)
{
    s_EventData *e = g_MapOverlayHdr.mapEvents;
    for (unsigned i = 0; i < 400 && e[i].triggerType != TriggerType_EndOfArray; ++i)
        if (e[i].activationType == TriggerActivationType_Item && e[i].requiredItemId == item &&
            e[i].requiredEventFlag == required && e[i].sysState == SysState_EventCallback &&
            e[i].eventParam == param) return 0;
    return 1;
}

unsigned map7_probe_save(unsigned rescued)
{
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    g_SavegamePtr->mapIdx = MapIdx_MAP7_S02;
    Savegame_EventFlagSet(EventFlag_391);
    if (rescued) Savegame_EventFlagSet(EventFlag_449);
    Savegame_EventFlagSet(EventFlag_M7S01_PickupKeyOfPhaleg);
    Savegame_EventFlagSet(EventFlag_M7S02_PickupKeyOfAratron);
    Event_InvItemCmd(InvItemCmd_AddItem, InvItemId_UnknownLiquid, 1, false);
    memcpy(&original, g_SavegamePtr, sizeof(original));
    MemCard_GameDataCopy(&card, g_SavegamePtr);
    if (!MemCard_ChecksumValidate(&card.footer, (s8*)&card.savegame, sizeof(card))) return 1;
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    memcpy(g_SavegamePtr, &card.savegame, sizeof(*g_SavegamePtr));
    return memcmp(&original, g_SavegamePtr, sizeof(original)) != 0;
}
