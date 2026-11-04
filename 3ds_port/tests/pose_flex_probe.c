/* Linked-ARM behavioral probe; never linked into the hardware application. */
#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include <string.h>
static GsCOORDINATE2 probe_coords[18];
static void seed(void)
{
    memset(probe_coords,0,sizeof(probe_coords));
    for (unsigned i=0;i<18;i++) for(unsigned j=0;j<3;j++) probe_coords[i].coord.m[j][j]=4096;
    MATRIX *l=&probe_coords[HarryBone_LeftUpperArm].coord;
    MATRIX *r=&probe_coords[HarryBone_RightUpperArm].coord;
    l->m[0][0]=l->m[1][1]=0; l->m[0][1]=4096; l->m[1][0]=-4096;
    r->m[1][1]=r->m[2][2]=0; r->m[1][2]=4096; r->m[2][1]=-4096;
    l->t[0]=1234; r->t[2]=-5678;
    g_SysWork.enablePlayerMatchAnim=false;
    g_Player_FlexRotationX=g_Player_FlexRotationY=0;
    g_DeltaTime=Q12(1.0f/30.0f);
}
unsigned test_pose_flex(void)
{
    unsigned failures=0;
    MATRIX left,right;
    seed(); left=probe_coords[HarryBone_LeftUpperArm].coord; right=probe_coords[HarryBone_RightUpperArm].coord;
    g_SysWork.playerWork.extra.state=PlayerState_None;
    func_8007D090(&g_SysWork.playerWork.player,&g_SysWork.playerWork.extra,probe_coords);
    if (memcmp(&left,&probe_coords[HarryBone_LeftUpperArm].coord,sizeof(left)) ||
        memcmp(&right,&probe_coords[HarryBone_RightUpperArm].coord,sizeof(right))) failures|=1;
    seed(); left=probe_coords[HarryBone_LeftUpperArm].coord; right=probe_coords[HarryBone_RightUpperArm].coord;
    g_SysWork.playerWork.extra.state=PlayerState_Unk52;
    func_8007D090(&g_SysWork.playerWork.player,&g_SysWork.playerWork.extra,probe_coords);
    if (memcmp(&left,&probe_coords[HarryBone_LeftUpperArm].coord,sizeof(left)) ||
        memcmp(&right,&probe_coords[HarryBone_RightUpperArm].coord,sizeof(right))) failures|=2;
    seed(); left=probe_coords[HarryBone_LeftUpperArm].coord;
    g_Player_FlexRotationX=Q12_ANGLE(30.0f);
    g_SysWork.playerWork.extra.state=PlayerState_None;
    func_8007D090(&g_SysWork.playerWork.player,&g_SysWork.playerWork.extra,probe_coords);
    MATRIX rotation={0}; int angle=g_Player_FlexRotationX>>1;
    rotation.m[0][0]=rotation.m[1][1]=Math_Cos(angle);
    rotation.m[0][1]=-Math_Sin(angle); rotation.m[1][0]=Math_Sin(angle);
    rotation.m[2][2]=4096;
    for (unsigned y=0;y<3;y++) for(unsigned x=0;x<3;x++) {
        int sum=0; for(unsigned k=0;k<3;k++) sum+=left.m[y][k]*rotation.m[k][x];
        int difference=probe_coords[HarryBone_LeftUpperArm].coord.m[y][x]-(sum>>12);
        if (difference < -1 || difference > 1) failures|=4;
    }
    return failures;
}
