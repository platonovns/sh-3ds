/* Development-only scenario setup. This object is never linked in a normal
 * hardware candidate. All movement, combat, events and AI after entry use the
 * original game paths. No save file is changed by selecting a scenario. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/screen/cutscene_border.h"
#include "bodyprog/game_boot/chara_init.h"
#include "bodyprog/events/player_pos_update.h"
#include "bodyprog/chara/spawn.h"
#include "bodyprog/math/math.h"
#ifndef SH_3DS_DEV_SCENE
#error Diagnostic scenario object must never enter a production build
#endif
extern void map0_s01_func_800D39F4(s_SubCharacter*);
extern s_MapOverlayHdr map0_s01_g_MapOverlayHeader_map0_s01;
extern s_MapOverlayHdr map2_s00_g_MapOverlayHeader_map2_s00;
static unsigned enter_pending;
void Game3ds_DevNewGame(void)
{
    g_SavegamePtr->mapIdx=SH_3DS_DEV_SCENE==7?MapIdx_MAP1_S00:
        SH_3DS_DEV_SCENE==9?MapIdx_MAP0_S02:
        (SH_3DS_DEV_SCENE==5 || SH_3DS_DEV_SCENE==8)?MapIdx_MAP2_S00:
        SH_3DS_DEV_SCENE==4?MapIdx_MAP0_S00:MapIdx_MAP0_S01;
    enter_pending=1;
    if(SH_3DS_DEV_SCENE==1 || SH_3DS_DEV_SCENE==4)return;
    Savegame_EventFlagSet(EventFlag_M0S01_CafeCutsceneStarted);
    Savegame_EventFlagSet(EventFlag_M0S01_FmvStarted);
    Savegame_EventFlagSet(EventFlag_49);
    Savegame_EventFlagSet(EventFlag_M0S01_PickupMap);
    Savegame_EventFlagSet(EventFlag_M0S01_PickupKitchenKnife);
    Savegame_EventFlagSet(EventFlag_M0S01_PickupFlashlight);
    Savegame_EventFlagSet(EventFlag_M0S01_PickupPocketRadio);
    Savegame_EventFlagSet(EventFlag_41);
    Savegame_EventFlagSet(EventFlag_42);
    if(SH_3DS_DEV_SCENE==3 || SH_3DS_DEV_SCENE==5 || SH_3DS_DEV_SCENE>=7) {
        Savegame_EventFlagSet(EventFlag_47);
        Savegame_EventFlagSet(EventFlag_M0S01_AirScreamerDied);
        Savegame_EventFlagSet(EventFlag_M0S01_AirScreamerDeathPlayed);
    }
    if(SH_3DS_DEV_SCENE==5) {
        /* This scenario starts after the Cafe map pickup. Match its original
         * save mutation as well as the event flag; no production availability
         * or possession check is bypassed. */
#ifndef SH_STAGE10_NO_MAP
        g_SavegamePtr->paperMapFlags|=1<<PaperMapIdx_OldTown;
#endif
        /* Arrival records belong to the SOURCE map. Cafe's real exit uses
         * its point 7, not point 7 of the destination overlay. */
        const s_MapPoint2d *entry=&map0_s01_g_MapOverlayHeader_map0_s01.mapPoints[7];
        g_SavegamePtr->playerPositionX=entry->positionX;g_SavegamePtr->playerPositionZ=entry->positionZ;
        g_SavegamePtr->playerRotationY=0;
        Savegame_EventFlagClear(EventFlag_49);Savegame_EventFlagClear(EventFlag_50);
    }
    const unsigned ids[]={InvItemId_Flashlight,InvItemId_PocketRadio,InvItemId_KitchenKnife,
        InvItemId_Handgun,InvItemId_HandgunBullets,InvItemId_HealthDrink};
    const unsigned counts[]={1,1,1,15,60,3};
    for(unsigned i=0;i<6;i++) {
        g_SavegamePtr->items[i].id_0=ids[i];g_SavegamePtr->items[i].count_1=counts[i];
    }
    g_SavegamePtr->equippedWeapon=InvItemId_Handgun;
    func_8004F190(g_SavegamePtr);
    if(SH_3DS_DEV_SCENE>=7) {
        /* Nearby fixture entries only: progression items/flags are never
         * injected. All pickups and door conditions run in original events. */
        unsigned point=SH_3DS_DEV_SCENE==7?47:SH_3DS_DEV_SCENE==9?102:14;
        const s_MapPoint2d *entry=&map2_s00_g_MapOverlayHeader_map2_s00.mapPoints[point];
        g_SavegamePtr->playerPositionX=entry->positionX;
        g_SavegamePtr->playerPositionZ=entry->positionZ;
        g_SavegamePtr->playerRotationY=0;
        Savegame_EventFlagClear(EventFlag_49);Savegame_EventFlagClear(EventFlag_50);
    }
}
void Game3ds_DevEnter(void)
{
    if(!enter_pending)return;
    enter_pending=0;
    if(SH_3DS_DEV_SCENE>=7) {
        unsigned point=SH_3DS_DEV_SCENE==7?47:SH_3DS_DEV_SCENE==9?102:14;
        Chara_PositionSet(&map2_s00_g_MapOverlayHeader_map2_s00.mapPoints[point]);
        Game_PlayerHeightUpdate();return;
    }
    if(SH_3DS_DEV_SCENE==5) {
        Chara_PositionSet(&map0_s01_g_MapOverlayHeader_map0_s01.mapPoints[7]);
        Game_PlayerHeightUpdate();return;
    }
    if(SH_3DS_DEV_SCENE==1 || SH_3DS_DEV_SCENE==4)return;
    s_SubCharacter *p=&g_SysWork.playerWork.player;
    p->position.vx=Q12(2.0f);p->position.vy=0;p->position.vz=Q12(270.0f);
    p->rotation.vy=0;
    g_MapOverlayHdr.playerControlUnfreeze(false);
    g_SysWork.sysFlags&=~(SysFlag_5|SysFlag_9|SysFlag_CutsceneActive);
    g_SysWork.cutsceneBorderState=CutsceneBorderState_None;
    SysWork_StateSetNext(SysState_Gameplay);
    if(SH_3DS_DEV_SCENE==2) {
        s_SubCharacter *e=&g_SysWork.npcs[0];
        if(e->model.charaId!=Chara_AirScreamer)game3ds_halt(459,"Cafe diagnostic original spawn missing",e->model.charaId);
        Savegame_EventFlagSet(EventFlag_M0S01_AirScreamerIntroCutsceneStarted);
        Savegame_EventFlagSet(EventFlag_46);Savegame_EventFlagSet(EventFlag_47);
        e->position.vx=p->position.vx;e->position.vy=Q12(-1.0f);e->position.vz=p->position.vz+Q12(3.0f);
        map0_s01_func_800D39F4(e);
    }
    if(SH_3DS_DEV_SCENE==6) {
        /* Before the window event, with the original CAFE2 DMS and bird
         * loaded by Map_WorldObjectsInit. The original door trigger starts
         * the complete event; no cutscene step or enemy state is skipped. */
        p->position.vx=Q12(0.95f);p->position.vz=Q12(269.5f);
        p->rotation.vy=Q12_ANGLE(270.0f);
    }
}
