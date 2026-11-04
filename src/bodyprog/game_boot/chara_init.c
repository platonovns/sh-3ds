#include "game.h"
#ifdef SH_3DS_GAME
#include "game3ds.h"
#endif
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
#include "sh_log.h"
#include <stdio.h>
#endif

#include <psyq/libetc.h>
#include <psyq/libpad.h>
#include <psyq/strings.h>

#include "bodyprog/bodyprog.h"
#include "bodyprog/events/npc_main.h"
#include "bodyprog/events/collision_trigger.h"
#include "bodyprog/game_boot/fs_chara_anim.h"
#include "bodyprog/events/player_pos_update.h"
#include "bodyprog/game_boot/game_boot.h"
#include "bodyprog/gfx/map_effects.h"
#include "bodyprog/view/vc_util.h"
#include "main/fsqueue.h"

void GameFs_WeaponInfoUpdate(void);

// ========================================
// CHARACTER & GAME INIT
// ========================================

void GameBoot_NpcClear(void) // 0x80034EC8
{
    s32 i;

    g_SysWork.field_228C[0] = 0;
    g_SysWork.npcFlags = 0;

    bzero(g_SysWork.npcs, ARRAY_SIZE(g_SysWork.npcs) * sizeof(s_SubCharacter));

    for (i = 0; i < CHARA_GROUP_COUNT; i++)
    {
        g_SysWork.charaGroupFlags[i] = 0;
    }
}

void GameBoot_NpcInit(void) // 0x80034F18
{
    vcSetCameraUseWarp(&g_SysWork.playerWork.player.position, g_SysWork.cameraAngleY);
    func_8005E70C();

    if (g_SysWork.field_234A)
    {
        g_MapOverlayHdr.enviromentSet(g_SysWork.field_2349, 127);
        g_MapOverlayHdr.particlesUpdate(0, g_SavegamePtr->mapIdx, 0);
    }

    GameBoot_NpcClear();
    Game_NpcRoomInitSpawn(false);
    Game_PlayerHeightUpdate();
}

void GameBoot_InGameInit(void) // 0x80034FB8
{
    s32 mapOvlId;

    mapOvlId = g_SavegamePtr->mapIdx;
#ifdef SH_3DS_GAME
    Game3ds_Progress("MAP0_INIT_BEGIN",mapOvlId);
#endif

#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
#define HARRY_CHECK(label) ;
    HARRY_CHECK("start");
#endif
    vcInitCamera(&g_MapOverlayHdr, &g_SysWork.playerWork.player.position);
    vcSetCameraUseWarp(&g_SysWork.playerWork.player.position, g_SysWork.cameraAngleY);
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after vcInit");
#endif
    World_CollisionTriggersSet(&g_MapOverlayHdr);
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after World_CollisionTriggersSet");
#endif
    Gfx_MapEffectsSet(0);
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after MapEffectsSet");
#endif
    WorldGfx_CharaModelProcessAllLoads();
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after CharaModelProcessAllLoads");
#endif
    Game_FlashlightAttributesFix();
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after FlashlightAttribsFix");
#endif
    g_MapOverlayHdr.particlesUpdate(0, mapOvlId, NO_VALUE);
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after particlesUpdate");
#endif

    GameBoot_NpcClear();
    g_SysWork.npcFlagsId = 5;
    func_8005E650(mapOvlId);
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after func_8005E650");
#endif
    func_80037124();
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after func_80037124");
#endif
    func_8007E8C0();
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after func_8007E8C0");
#endif
    Game_NpcRoomInitSpawn(false);
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after NpcRoomInitSpawn");
#endif
    Game_PlayerHeightUpdate();
    Fs_CharaAnimBoneInfoUpdate();
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after AnimBoneInfoUpdate");
#endif
    GameFs_WeaponInfoUpdate();
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("after WeaponInfoUpdate");
#endif
    GameFs_Tim00TIMLoad();
    Fs_QueueWaitForEmpty();
    GameFs_MapItemsModelLoad(mapOvlId);
#ifdef SH_3DS_GAME
    Game3ds_Progress("MAP0_INIT_DONE",mapOvlId);
#endif
#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)
    HARRY_CHECK("COMPLETE");
#undef HARRY_CHECK
#endif
}
