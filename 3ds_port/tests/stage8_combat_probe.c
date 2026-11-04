/* Component fixture only, never linked into the application. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/math/math.h"
#include <string.h>
#include "bodyprog/screen/screen_data.h"
#include "psx_memory.h"
#include "bodyprog/game_boot/fs_chara_anim.h"
#include "bodyprog/chara/spawn.h"
#include "bodyprog/events/npc_main.h"
#include "bodyprog/player.h"
#include "bodyprog/game_boot/chara_init.h"
extern bool map0_s01_sharedFunc_800D7EBC_0_s01(s_SubCharacter*);
unsigned stage8_hit_index(unsigned index)
{
    memset(&g_SysWork,0,sizeof(g_SysWork));
    s_SubCharacter *enemy=&g_SysWork.npcs[index],*player=&g_SysWork.playerWork.player;
    enemy->model.charaId=Chara_AirScreamer;
    enemy->health=Q12(100);enemy->field_44.field_2=41;
    player->model.charaId=Chara_Harry;player->health=Q12(100);
    VECTOR3 contact={0,0,0};
    func_8008B714(enemy,player,&contact,4096);
    return player->field_40;
}
unsigned stage8_combat_layout(unsigned which)
{
    return which ? (u8*)g_SysWork.npcs-(u8*)&g_SysWork.playerWork : sizeof(s_PlayerWork);
}
void stage8_hit_twice(unsigned *out)
{
    stage8_hit_index(0);
    out[0]=g_SysWork.playerWork.player.damage.amount;
    VECTOR3 contact={0,0,0};
    func_8008B714(&g_SysWork.npcs[0],&g_SysWork.playerWork.player,&contact,4096);
    out[1]=g_SysWork.playerWork.player.damage.amount;
}
void stage8_blood_begin(void)
{
    g_DeltaTime=g_DeltaTimeRaw=136;
    g_GameWork.config.extraBloodColor=0;
    VECTOR contact={g_SysWork.playerWork.player.position.vx,
        g_SysWork.playerWork.player.position.vy-4096,
        g_SysWork.playerWork.player.position.vz,0};
    func_8005F6B0(&g_SysWork.playerWork.player,&contact,3,1);
}
void stage8_blood_tick(void)
{
    GsOUT_PACKET_P=PSX_ADDR(0x801A2600);
    GsClearOt(0,0,&g_OrderingTable0[0]);
    func_8005E89C();
    GsDrawOt(&g_OrderingTable0[0]);
}
unsigned stage8_enemy_begin(void)
{
    g_Player_DisableControl=false;g_Player_IsInWalkToRunTransition=false;
    g_SysWork.sysState=SysState_Gameplay;g_SysWork.npcFlagsId=6;
    for(unsigned i=0;i<NPC_COUNT_MAX;i++)g_SysWork.npcs[i].model.charaId=Chara_None;
    g_SysWork.npcFlags=0;g_SysWork.field_228C[0]=0;
    Chara_Load(0,Chara_AirScreamer,g_SysWork.npcBoneCoordBuffer,CHARA_FORCE_FREE_ALL,NULL,NULL);
    Chara_ProcessLoads();
    Anim_BoneInit(g_CharaModelAnimsData[1].activeAnmHdr,g_CharaModelAnimsData[1].boneCoords);
    unsigned slot=Chara_Spawn(Chara_AirScreamer,0,g_SysWork.playerWork.player.position.vx,
        g_SysWork.playerWork.player.position.vz+4096,2048,12);
    g_DeltaTime=g_DeltaTimeRaw=136;
    Game_NpcUpdate();
    g_SysWork.npcs[slot].model.controlState=12;
    g_SysWork.npcs[slot].model.stateStep=0;
    g_SysWork.npcs[slot].model.anim.status=5;
    g_SysWork.npcs[slot].model.anim.time=16*4096;
    VECTOR3 contact=g_SysWork.playerWork.player.position;
    g_SysWork.npcs[slot].field_44.field_2=41;
    g_SysWork.npcs[slot].field_44.field_8=0;
    func_8008B714(&g_SysWork.npcs[slot],&g_SysWork.playerWork.player,&contact,4096);
    return slot;
}
void stage8_enemy_tick(unsigned *out)
{
    g_DeltaTime=g_DeltaTimeRaw=136;
    GsOUT_PACKET_P=PSX_ADDR(0x801A2600);GsClearOt(0,0,&g_OrderingTable0[0]);
    Player_Update(&g_SysWork.playerWork.player,g_CharaModelAnimsData[0].activeAnmHdr,g_SysWork.playerBoneCoords);
    Player_CombatUpdate(&g_SysWork.playerWork.player,g_SysWork.playerBoneCoords);
    func_8008A3AC(&g_SysWork.playerWork.player);
    map0_s01_sharedFunc_800D7EBC_0_s01(&g_SysWork.npcs[0]);
    func_8005E89C();GsDrawOt(&g_OrderingTable0[0]);
    s_SubCharacter *p=&g_SysWork.playerWork.player,*e=&g_SysWork.npcs[0];
    out[0]=p->health;out[1]=p->attackReceived;out[2]=g_SysWork.playerWork.extra.state;
    out[3]=e->model.controlState;out[4]=e->model.stateStep;out[5]=e->model.anim.status;
    out[6]=e->field_44.field_0;out[7]=e->field_44.field_2;out[8]=e->model.anim.keyframeIdx;
}
