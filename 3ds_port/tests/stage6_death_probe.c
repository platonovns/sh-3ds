/* CPU fixture only: enter death through the original state setter after boot.
 * Never linked into the game or used as normal-route acceptance evidence. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include "bodyprog/game_boot/fs_chara_anim.h"
#include "bodyprog/events/events_main.h"
#include "bodyprog/events/npc_main.h"
#include "bodyprog/game_boot/chara_init.h"
#include "bodyprog/chara/spawn.h"

static unsigned with_npcs;

void stage6_death_begin(unsigned npcs)
{
    s_SubCharacter *player=&g_SysWork.playerWork.player;
    s_PlayerExtra *extra=&g_SysWork.playerWork.extra;
    g_Player_DisableControl=false;
    g_Player_IsInWalkToRunTransition=false;
    player->health=0;
    Player_ExtraStateSet(player,extra,PlayerState_Death);
    with_npcs=npcs;
    if(npcs) {
        Chara_Load(1,Chara_GreyChild,g_SysWork.npcBoneCoordBuffer,0,NULL,NULL);
        Chara_ProcessLoads();
        for(unsigned i=0;i<NPC_COUNT_MAX;i++)g_SysWork.npcs[i].model.charaId=Chara_None;
        g_SysWork.npcFlags=0;g_SysWork.field_228C[0]=0;
        for(unsigned i=0;i<3;i++)
            Chara_Spawn(Chara_GreyChild,i,player->position.vx+(i+1)*1024,
                        player->position.vz+(i-1)*2048,2048,6);
        player->health=-1;
        g_Player_IsDead=true;
    }
}

void stage6_death_tick(void)
{
    g_DeltaTime=136;
    g_DeltaTimeRaw=136;
    Player_Update(&g_SysWork.playerWork.player,g_CharaModelAnimsData[0].activeAnmHdr,
                  g_SysWork.playerBoneCoords);
    if(with_npcs) {
        Player_CombatUpdate(&g_SysWork.playerWork.player,g_SysWork.playerBoneCoords);
        func_8008A3AC(&g_SysWork.playerWork.player);
        Game_NpcUpdate();
    }
}

void stage6_death_snapshot(unsigned *out)
{
    s_SubCharacter *p=&g_SysWork.playerWork.player;
    s_PlayerExtra *e=&g_SysWork.playerWork.extra;
    out[0]=e->state;
    out[1]=p->model.anim.status;out[2]=e->model.anim.status;
    out[3]=p->model.anim.keyframeIdx;out[4]=e->model.anim.keyframeIdx;
    out[5]=p->model.anim.flags;out[6]=e->model.anim.flags;
    out[7]=p->model.controlState;out[8]=e->model.controlState;
    out[9]=p->model.stateStep;out[10]=e->model.stateStep;
    out[11]=Savegame_EventFlagGet(EventFlag_25)!=0;
    out[12]=p->health;
}

unsigned stage6_death_overlay_load(void)
{
    /* Isolate the existing authored transition record after the death test.
     * The production event dispatcher, rather than this fixture, must select
     * this record during the separately required normal-route validation. */
    s_EventData *event=g_MapOverlayHdr.mapEvents;
    for(unsigned i=0;i<128;i++,event++) {
        if(event->requiredEventFlag==EventFlag_26 && event->sysState==SysState_LoadOverlay) {
            g_MapEventData=event;
            SysWork_StateSetNext(SysState_LoadOverlay);
            SysState_LoadArea_Update();
            return g_SavegamePtr->mapIdx==MapIdx_MAP0_S01;
        }
    }
    return 0;
}
