#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/sys/game_main.h"
#include "psx_memory.h"
#include "bodyprog/sys/joy.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "bodyprog/player.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/sound/sound_system.h"
#include "game_audio.h"
#include "game_xa.h"
#include "game_profile.h"
#include "game_lower_policy.h"
#if defined(SH_CPU_AUDIT_RECORDER)
#include "bodyprog/view/vw_main.h"
void Game3ds_CpuRecorderView(int32_t out[7])
{
    SVECTOR angles;VECTOR3 position;
    vwGetViewAngle(&angles);vwGetViewPosition(&position);
    out[0]=g_SysWork.field_2388.isFlashlightOn_15!=0;
    out[1]=position.vx;out[2]=position.vy;out[3]=position.vz;
    out[4]=angles.vx;out[5]=angles.vy;out[6]=angles.vz;
}
#endif

int Game3ds_RetailMain(void);
void PcPort_InitCharaAnimInfo(void); /* Runtime relocation of original static RAM pointers. */
void AsRodata_Reformat(void);
void GroanerAnimInfos_Init(void);
void GroanerM4S02AnimInfos_Init(void);
void CatAnimInfos_Init(void);
void CreeperAnimInfos_Init(void);
void SplitHeadAnimInfos_Init(void);
void LockerDeadBodyAnimInfos_Init(void);
void DahliaAnimInfos_Init(void);
void RomperAnimInfos_Init(void);
void KaufmannAnimInfos_Init(void);
void LisaAnimInfos_Init(void);
void AlessaAnimInfos_Init(void);
void BloodsuckerAnimInfos_Init(void);
void PuppetNurseData_Init(void);
void DahliaM3S06AnimInfos_Init(void);
void TwinfeelerAnimInfos_Init(void);
void FloatstingerAnimInfos_Init(void);
void HangedScratcherAnimInfos_Init(void);
PsxVram *game3ds_canonical;
/* The native disc gate accepts the retail USA data set. */
e_GameRegion g_GameRegion=Region_USA;
void game3ds_run(Stage4FsResult *result, PsxVram *vram)
{
    PsxMemory_Init();
    PcPort_InitCharaAnimInfo();
    AsRodata_Reformat();
    GroanerAnimInfos_Init();
    GroanerM4S02AnimInfos_Init();
    CatAnimInfos_Init();
    CreeperAnimInfos_Init();
    SplitHeadAnimInfos_Init();
    LockerDeadBodyAnimInfos_Init();
    DahliaAnimInfos_Init();
    RomperAnimInfos_Init();
    KaufmannAnimInfos_Init();
    LisaAnimInfos_Init();
    AlessaAnimInfos_Init();
    BloodsuckerAnimInfos_Init();
    PuppetNurseData_Init();
    DahliaM3S06AnimInfos_Init();
    TwinfeelerAnimInfos_Init();
    FloatstingerAnimInfos_Init();
    HangedScratcherAnimInfos_Init();
    game3ds_canonical = vram;
    if (!stage4_fs_game_open(result, vram, "sdmc:/3ds/silenthill/sh1.bin", "sdmc:/3ds/silenthill/sh1.cue"))
        game3ds_halt(result->first_failure, result->operation, result->detail);
    stage4_fs_game_allow_span(FILE_BG_BG_ITEM_PLM, &g_WorldGfxWork.itemLmHdr, 4096);
    Game3ds_RetailMain();
    game3ds_halt(421, "original MainLoop returned", 0);
}

void Game3ds_Observe(void)
{
    int idx=g_SavegamePtr->paperMapIdx;
    game3ds_lower_backlight_observe(g_GameWork.gameState,g_SysWork.sysState,
        (g_SysWork.sysFlags&SysFlag_CutsceneActive)!=0,g_Player_DisableControl,
        idx>0 && idx<24 && HAS_MAP(idx));
    extern void game3ds_hp_observe(uint32_t valid, int32_t health);
    /* Death animation restores HP before its event or Game Over runs. Keep
     * that transient value hidden until a death destination has been reached
     * and a living, controllable gameplay session is active again. */
    static int hp_death_latched, hp_death_destination, hp_death_map, hp_death_restart, hp_death_gameover;
    int harry = g_SysWork.playerWork.player.model.charaId == Chara_Harry &&
        g_WorldGfxWork.registeredCharaModels[Chara_Harry] != NULL;
    int death_state = g_SysWork.playerWork.extra.state == PlayerState_Death ||
        g_SysWork.playerWork.extra.state == PlayerState_InstantDeath;
    if (!hp_death_latched && g_GameWork.gameState == GameState_InGame && harry &&
        (g_SysWork.sysState == SysState_Gameplay || g_SysWork.sysState == SysState_GameOver) &&
        (g_SysWork.playerWork.player.health <= 0 || g_Player_IsDead || death_state || g_SysWork.sysState == SysState_GameOver)) {
        hp_death_latched = 1;
        hp_death_map = g_SavegamePtr->mapIdx;
        hp_death_restart = hp_death_gameover = 0;
    }
    /* An FMV or a Game Over state may return briefly to gameplay while the
     * death event is still running. Only a new map or a load/menu lifecycle
     * can make the following live gameplay a new session. */
    if (hp_death_latched && g_GameWork.gameState == GameState_InGame && g_SysWork.sysState == SysState_GameOver)
        hp_death_gameover = 1;
    if (hp_death_latched && (g_GameWork.gameState == GameState_MainMenu ||
        g_GameWork.gameState == GameState_MovieOpening ||
        (hp_death_gameover && g_GameWork.gameState == GameState_MainLoadScreen)))
        hp_death_restart = 1;
    if (hp_death_latched && ((g_GameWork.gameState == GameState_InGame &&
        g_SavegamePtr->mapIdx != hp_death_map) ||
        hp_death_restart))
        hp_death_destination = 1;
    int hp_valid = g_GameWork.gameState == GameState_InGame &&
        g_SysWork.sysState == SysState_Gameplay &&
        !(g_SysWork.sysFlags & (SysFlag_CutsceneActive | SysFlag_DemoActive)) &&
        Game3ds_CanPause() &&
        !g_Player_DisableControl && harry && !death_state &&
        g_SysWork.playerWork.player.health > 0;
    /* The opening death loads the cafe before its automatic FMV and scene;
     * map loading alone is not proof that control has actually resumed. */
    int opening_pending = hp_death_latched && !hp_death_restart && hp_death_map == MapIdx_MAP0_S00 &&
        (g_SavegamePtr->mapIdx != MapIdx_MAP0_S01 ||
         !Savegame_EventFlagGet(EventFlag_M0S01_FmvStarted) ||
         !Savegame_EventFlagGet(EventFlag_M0S01_CafeCutsceneStarted));
    if (hp_death_latched && hp_death_destination && hp_valid && !opening_pending)
        hp_death_latched = hp_death_destination = 0;
    int hp_hold=!hp_valid && hp_led_hold_policy(g_GameWork.gameState,g_SysWork.sysState,
        (g_SysWork.sysFlags&SysFlag_CutsceneActive)!=0,(g_SysWork.sysFlags&SysFlag_DemoActive)!=0) &&
        !(g_GameWork.gameState==GameState_InGame && g_SysWork.sysState==SysState_Gameplay &&
          g_SysWork.playerWork.player.health<=0);
    /* Status keeps the gameplay LED state, but a heal must update it while
     * the menu remains open. Do not change the LED merely on menu entry. */
    static int status_hp_seen;
    static int32_t status_hp_previous;
    if(g_GameWork.gameState==GameState_InventoryScreen) {
        int32_t hp=g_SysWork.playerWork.player.health;
        if(status_hp_seen && hp!=status_hp_previous && hp>0 && hp_hold)hp_valid=1;
        status_hp_seen=1;status_hp_previous=hp;
    } else status_hp_seen=0;
    if (hp_death_latched) hp_valid = hp_hold = 0;
    game3ds_hp_observe(hp_valid?1:hp_hold?2:0, hp_valid ? g_SysWork.playerWork.player.health : 0);
    if(game_prof_enabled) {
        unsigned enemies=0;
        for(unsigned i=0;i<NPC_COUNT_MAX;i++)
            enemies+=g_SysWork.npcs[i].model.charaId!=Chara_None &&
                g_SysWork.npcs[i].health>0;
        game_prof_scene(g_SavegamePtr->mapIdx,g_SavegamePtr->mapRoomIdx,
            (g_SysWork.sysFlags&SysFlag_CutsceneActive)!=0,enemies);
    }
    /* Audio lifecycle only. A native skip must cancel speech even when the
     * original event jumps over its ordinary subtitle completion/stop path. */
    static uint32_t audio_context_valid,audio_map,audio_room,audio_state,audio_sys,audio_skip;
    uint32_t skip=g_Controller0->clickedBtnFlags & g_GameWorkPtr->config.controllerConfig.skip;
    if(audio_context_valid && game_audio_xa_pending() &&
        (audio_map!=g_SavegamePtr->mapIdx || audio_room!=g_SavegamePtr->mapRoomIdx ||
         (g_GameWork.gameState==GameState_MainMenu && audio_state!=GameState_MainMenu) ||
         (audio_sys!=SysState_Gameplay && g_SysWork.sysState==SysState_Gameplay) || (skip && !audio_skip))) {
        uint32_t reason=(skip && !audio_skip)?XA_CANCEL_SKIP:
            (g_GameWork.gameState==GameState_MainMenu?XA_CANCEL_TITLE:
            (audio_map!=g_SavegamePtr->mapIdx || audio_room!=g_SavegamePtr->mapRoomIdx)?XA_CANCEL_ROOM:XA_CANCEL_GAMEPLAY);
        game_audio_xa_cancel(reason,(audio_sys<<16)|g_SysWork.sysState,
            (audio_map<<24)|(audio_room<<16)|(g_SavegamePtr->mapIdx<<8)|g_SavegamePtr->mapRoomIdx);
    }
    audio_context_valid=1;audio_map=g_SavegamePtr->mapIdx;audio_room=g_SavegamePtr->mapRoomIdx;
    audio_state=g_GameWork.gameState;audio_sys=g_SysWork.sysState;
    audio_skip=skip;
    if(game3ds_debug_enabled()) {
        static uint32_t last;
        uint32_t now=game3ds_vblank_clock();
        if(now-last>=60) {
            last=now;
            for(unsigned i=0;i<NPC_COUNT_MAX;i++) {
                const s_SubCharacter *n=&g_SysWork.npcs[i];
                unsigned id=n->model.charaId;
                int32_t row[15]={id,n->model.controlState,n->model.anim.status,
                    n->position.vx,n->position.vy,n->position.vz,n->health,n->flags,
                    id<Chara_Count && g_WorldGfxWork.registeredCharaModels[id]!=NULL,
                    g_SysWork.sysState,g_SysWork.sysFlags,
                    Savegame_EventFlagGet(EventFlag_41),Savegame_EventFlagGet(EventFlag_42),
                    Savegame_EventFlagGet(EventFlag_46),Savegame_EventFlagGet(EventFlag_47)};
                game3ds_visibility_observe(i,row);
            }
        }
    }
    uint32_t slots[40];
    for(unsigned i=0;i<40;i++)slots[i]=g_SavegamePtr->items[i].id_0 | ((uint32_t)g_SavegamePtr->items[i].count_1<<8);
    game3ds_inventory_observe(g_SavegamePtr->inventorySlotCount,g_SavegamePtr->equippedWeapon,
        g_Inventory_SelectedItemIdx,g_SavegamePtr->pickedUpItemCount,slots);
    stage4_fs_game_observe();
    game3ds_map_observe(g_SavegamePtr->mapIdx, g_SavegamePtr->mapRoomIdx,
        g_SysWork.playerWork.player.health, g_Player_DisableControl);
    game3ds_player_observe(g_SysWork.playerWork.player.position.vx,
        g_SysWork.playerWork.player.position.vz,g_SysWork.playerWork.player.rotation.vy,
        g_SysWork.sysState,g_Controller0->heldBtnFlags,
        g_SysWork.sysStateSteps[0],g_SysWork.sysStateSteps[1],g_MapEventParam);
    game3ds_animation_observe(g_SysWork.playerWork.extra.state,g_SysWork.playerWork.extra.upperBodyState,
        g_SysWork.playerWork.player.model.anim.status,g_SysWork.playerWork.extra.model.anim.status,
        g_SysWork.playerWork.player.model.anim.keyframeIdx,g_SysWork.playerWork.extra.model.anim.keyframeIdx);
    game3ds_observe(g_GameWork.gameState, g_GameWork.gameStateSteps[0], g_FsQueue.state, g_FsQueue.postLoadState);
}

void Game3ds_Progress(const char *phase, uint32_t detail)
{
    Game3ds_Observe();
    game3ds_progress(phase, detail);
}


