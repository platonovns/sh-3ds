/* Offline-only tests against the real resident overlay and memory-card code. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/memcard.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include <string.h>

_Static_assert(sizeof(s_Savegame) == 636, "Original save ABI");
static s_Savegame_Container card;
static s_Savegame original;
extern void map6_s02_func_800CF0B8(void);
extern void map6_s02_Chara_CollisionReset(s_SubCharacter*);
extern void map6_s02_sharedFunc_800D2E6C_0_s00(void);

unsigned map6_s02_probe_save(unsigned phase)
{
    memset(g_SavegamePtr, 0, sizeof(*g_SavegamePtr));
    g_SavegamePtr->mapIdx = MapIdx_MAP6_S02;
    g_SavegamePtr->mapRoomIdx = 3;
    if (phase & 1) Savegame_EventFlagSet(EventFlag_410);
    if (phase & 2) Savegame_EventFlagSet(EventFlag_391);
    Savegame_EventFlagSet(EventFlag_424);
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

unsigned map6_s02_probe_edges(void)
{
    s_EventData *e = g_MapOverlayHdr.mapEvents;
    if (g_MapOverlayHdr.charaCollisionReset != map6_s02_Chara_CollisionReset ||
        g_MapOverlayHdr.func_104 != map6_s02_sharedFunc_800D2E6C_0_s00) return 5;
    /* Lighthouse exit and its save points must remain gated by flag 416. */
    if (e[3].sysState != SysState_LoadOverlay || e[3].mapIdx != MapIdx_MAP6_S00 ||
        e[3].eventParam != 1 || e[3].requiredEventFlag != EventFlag_416) return 1;
    for (unsigned i = 0; i != 3; ++i)
        if (e[i].sysState != SysState_SaveMenu1 || e[i].requiredEventFlag != EventFlag_416) return 2;
    if (e[7].requiredEventFlag != EventFlag_409 || e[7].disabledEventFlag != EventFlag_410 ||
        e[7].sysState != SysState_EventCallback || !g_MapOverlayHdr.mapEventFuncs[e[7].eventParam]) return 3;
    if (e[9].requiredItemId != InvItemId_ChannelingStone || e[9].sysState != SysState_EventCallback ||
        !g_MapOverlayHdr.mapEventFuncs[e[9].eventParam]) return 4;
    return 0;
}

unsigned map6_s02_probe_entrance(void)
{
    s_EventData *e = &g_MapOverlayHdr.mapEvents[8];
    return e->sysState != SysState_LoadOverlay || e->mapIdx != MapIdx_MAP6_S02 ||
           e->eventParam != 8 || e->pointOfInterestIdx != 7;
}

unsigned map6_s02_probe_lighthouse_complete(void)
{
    Savegame_EventFlagClear(EventFlag_410);
    Savegame_EventFlagSet(EventFlag_407);
    Savegame_EventFlagClear(EventFlag_MapMark_ResortTown_LighthouseCheck);
    g_SysWork.sysStateSteps[0] = 22;
    map6_s02_func_800CF0B8();
    return !Savegame_EventFlagGet(EventFlag_410) || Savegame_EventFlagGet(EventFlag_407) ||
           !Savegame_EventFlagGet(EventFlag_MapMark_ResortTown_LighthouseCheck);
}
