#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include <stddef.h>
#define FIELD(m) {offsetof(__typeof__(g_SysWork),m),sizeof(g_SysWork.m)}
const unsigned stage10_air_runtime_layout[]={sizeof(g_SysWork),offsetof(__typeof__(g_SysWork),npcs),sizeof(g_SysWork.npcs[0])};
const unsigned stage10_air_runtime_fields[][2]={
    FIELD(playerWork.player.rotation.vy),FIELD(npcs[0].rotation.vy),
    FIELD(playerWork.player.collision),FIELD(npcs[0].collision),
    FIELD(npcs[0].properties.airScreamer.targetPosition),
    FIELD(npcs[0].properties.airScreamer.position_110)};
const unsigned stage10_save_event_flags=offsetof(__typeof__(*g_SavegamePtr),eventFlags);
const unsigned stage10_reload_inventory_layout[]={offsetof(__typeof__(*g_SavegamePtr),items),
    sizeof(g_SavegamePtr->items[0]),offsetof(__typeof__(g_SavegamePtr->items[0]),count_1)};
const unsigned stage10_reload_fields[][2]={
    FIELD(sysState),FIELD(playerWork.extra.state),FIELD(playerWork.extra.upperBodyState),
    FIELD(playerWork.extra.lowerBodyState),FIELD(playerWork.extra.model.anim.status),
    FIELD(playerWork.extra.model.anim.keyframeIdx),FIELD(playerWork.extra.model.anim.time),
    FIELD(playerWork.extra.model.controlState),FIELD(playerWork.extra.model.stateStep),
    FIELD(playerCombat.isAiming),FIELD(playerCombat.currentWeaponAmmo),FIELD(playerCombat.totalWeaponAmmo),
    FIELD(playerWork.player.properties.player.flags),FIELD(playerWork.player.model.anim.status),
    FIELD(playerWork.player.model.anim.keyframeIdx)};
const unsigned stage10_combat_fields[][2]={
    FIELD(sysState),FIELD(playerWork.player.health),FIELD(npcs[0].health),
    FIELD(playerWork.extra.state),FIELD(playerWork.extra.upperBodyState),
    FIELD(playerWork.player.model.anim.status),FIELD(playerWork.player.model.anim.keyframeIdx),
    FIELD(npcs[0].model.controlState),FIELD(npcs[0].model.stateStep),FIELD(npcs[0].model.anim.status),
    FIELD(npcs[0].position.vx),FIELD(npcs[0].position.vy),FIELD(npcs[0].position.vz),
    FIELD(playerWork.player.position.vx),FIELD(playerWork.player.position.vz),FIELD(playerWork.player.rotation.vy),
    FIELD(playerCombat.weaponInventoryIdx),FIELD(playerCombat.currentWeaponAmmo),
    FIELD(playerWork.player.damage.amount),FIELD(npcs[0].damage.amount),FIELD(playerWork.player.attackReceived),
    FIELD(playerCombat.isAiming),FIELD(playerCombat.weaponAttack),FIELD(npcs[0].field_44.field_2)};
void stage10_combat_snapshot(unsigned *v)
{
    s_SubCharacter *p=&g_SysWork.playerWork.player,*e=&g_SysWork.npcs[0];
    v[0]=g_SysWork.sysState;v[1]=p->health;v[2]=e->health;
    v[3]=g_SysWork.playerWork.extra.state;v[4]=g_SysWork.playerWork.extra.upperBodyState;
    v[5]=p->model.anim.status;v[6]=p->model.anim.keyframeIdx;
    v[7]=e->model.controlState;v[8]=e->model.stateStep;v[9]=e->model.anim.status;
    v[10]=e->position.vx;v[11]=e->position.vy;v[12]=e->position.vz;
    v[13]=p->position.vx;v[14]=p->position.vz;v[15]=p->rotation.vy;
    v[16]=g_SavegamePtr->equippedWeapon;v[17]=g_SysWork.playerCombat.weaponInventoryIdx;
    v[18]=g_SysWork.playerCombat.currentWeaponAmmo;
    v[19]=p->damage.amount;v[20]=e->damage.amount;v[21]=p->attackReceived;
    v[22]=Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDied);
    v[23]=g_Player_DisableControl;v[24]=g_Player_IsAiming;
    v[25]=g_Controller0->heldBtnFlags;v[26]=g_SysWork.playerCombat.weaponAttack;
    v[27]=e->field_44.field_2;
    v[28]=Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDeathPlayed);
}
