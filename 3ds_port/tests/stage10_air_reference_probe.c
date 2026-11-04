#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include <stddef.h>
#include <string.h>
extern s32 map0_s01_sharedFunc_800D3814_0_s01(s_SubCharacter *enemy);
const unsigned stage10_air_layout[]={sizeof(g_SysWork),offsetof(__typeof__(g_SysWork),npcs)};
unsigned stage10_air_setup(unsigned yaw,unsigned distance,unsigned enemy_yaw)
{
    s_SubCharacter *p=&g_SysWork.playerWork.player,*e=&g_SysWork.npcs[0];
    memset(&g_SysWork,0,sizeof(g_SysWork));g_Player_IsAiming=0;
    p->rotation.vy=yaw;p->collision.cylinder.radius=2048;
    p->collision.box.offsetY=-5120;p->collision.box.top=-2458;
    e->position.vz=distance;e->position.vy=-4096;e->rotation.vy=enemy_yaw;
    e->collision.cylinder.radius=1024;e->properties.airScreamer.groundHeight=0;
    return (unsigned)e;
}
