/* Native input intent. The original lower/upper-body, speed, animation and
 * swept collision machines retain ownership of locomotion and combat. */
#include "game.h"
#include "game3ds.h"
#include "game_controls.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include "bodyprog/view/vw_main.h"
#include <string.h>
extern s32 D_800C454C;
extern q19_12 g_Player_HeadingAngle;
static uint32_t keys;
static unsigned tank_chord,tank_pending;
static int circle_x,circle_y,look_x,look_y;
static int modern,have_camera,have_travel,locked,last_mode=-1;
static int previous_yaw,travel_yaw,lock_yaw,lock_stick,map=-1,room=-1;
static VECTOR3 previous_camera;
static uint32_t last_move_clock;
/* Q12 sub-angle precision prevents a low analog deflection being rounded to
 * zero at 60 Hz. The view is an offset on a fresh authored matrix each update. */
static int look_yaw,look_pitch;
static uint32_t look_clock;
static int look_started;
static int norm(int a) {return ((a+2048)&4095)-2048;}
void Game3ds_ControlsReset(void)
{
    modern=have_camera=have_travel=locked=0;
    look_yaw=look_pitch=look_started=0;
    tank_chord=tank_pending=0;
}
void Game3ds_TankActions(void)
{
    if(game3ds_control_mode()!=GAME_CONTROL_TANK) {tank_chord=tank_pending=0;return;}
    unsigned lr=(keys&((1u<<9)|(1u<<8)))==((1u<<9)|(1u<<8));
    unsigned quick=(keys&(1u<<7)) && (g_Controller0->heldBtnFlags & ControllerFlag_Square);
    unsigned chord=lr?1:quick?2:0;
    int active=Game3ds_CanPause() && !g_Player_DisableControl && !g_Player_IsAiming && !g_SysWork.playerCombat.isAiming;
    if(!active || !chord)tank_pending=0;
    else if(chord!=tank_chord)tank_pending=chord;
    if((tank_pending==1 && g_SysWork.playerWork.extra.lowerBodyState==PlayerLowerBodyState_JumpBackward) ||
       (tank_pending==2 && (g_SysWork.playerWork.extra.lowerBodyState==PlayerLowerBodyState_QuickTurnRight ||
                            g_SysWork.playerWork.extra.lowerBodyState==PlayerLowerBodyState_QuickTurnLeft)))tank_pending=0;
    g_Player_IsSteppingLeftTap=g_Player_IsSteppingRightTap=0;
    if(active) {
        g_Player_IsSteppingLeftHold=(keys&(1u<<9)) && !lr;
        g_Player_IsSteppingRightHold=(keys&(1u<<8)) && !lr;
    }
    if(active && chord) {
        g_Player_IsSteppingLeftHold=g_Player_IsSteppingRightHold=0;
        g_Player_IsMovingBackward=0;g_Player_IsMovingForward=0;
        if(tank_pending==chord) {
            if(chord==2)g_Player_IsSteppingLeftTap=g_Player_IsSteppingRightTap=1;
            else {
                g_Player_IsMovingBackward=1;
                g_Player_IsRunning=!g_GameWork.config.extraWalkRunCtrl;
            }
        }
    }
    tank_chord=chord;
}
void Game3ds_InputSample(uint32_t value,int cx,int cy,int rx,int ry)
{
    keys=value;circle_x=cx;circle_y=cy;look_x=rx;look_y=ry;
}
static int free_locomotion(void)
{
    /* Gameplay can resume while the cinematic border is still retracting.
     * Pause/camera ownership includes that border, movement ownership does
     * not: falling back to tank here would reverse the first held direction. */
    return g_GameWork.gameState==GameState_InGame && g_SysWork.sysState==SysState_Gameplay &&
        !(g_SysWork.sysFlags&SysFlag_CutsceneActive) && !g_Player_DisableControl &&
        !g_SysWork.playerCombat.isAiming && !g_Player_IsAiming &&
        !(keys&(1u<<15)) &&
        !(game3ds_control_mode()==GAME_CONTROL_TANK && (keys&2u)) &&
        (g_SysWork.playerWork.extra.state==PlayerState_None ||
         g_SysWork.playerWork.extra.state==PlayerState_Combat) &&
        g_SysWork.playerWork.extra.lowerBodyState<=PlayerLowerBodyState_RunLeft &&
        !(g_SysWork.sysFlags&SysFlag_DemoActive);
}
void Game3ds_MovementInput(void)
{
    int mode=game3ds_control_mode(),x,z;
    modern=0;
    if(mode!=last_mode) {Game3ds_ControlsReset();last_mode=mode;}
    /* Combat and aim-stop animations can outlive the released aim input.
     * While they finish, do not feed their temporary tank fallback a held
     * modern direction: down+run would otherwise start a backward jump. */
    if(mode!=GAME_CONTROL_TANK && !(mode==GAME_CONTROL_HYBRID && (keys&0xf0)) &&
       g_GameWork.gameState==GameState_InGame && g_SysWork.sysState==SysState_Gameplay &&
       !(g_SysWork.sysFlags&(SysFlag_CutsceneActive|SysFlag_DemoActive)) &&
       (g_SysWork.playerWork.extra.state==PlayerState_None ||
        g_SysWork.playerWork.extra.state==PlayerState_Combat) &&
       !g_Player_DisableControl && !g_Player_IsAiming && !(keys&(1u<<15)) &&
       (!g_SysWork.playerCombat.isAiming || g_GameWork.config.extraWeaponCtrl) &&
       !free_locomotion()) {
        g_Player_IsMovingForward=g_Player_IsMovingBackward=0;
        g_Player_IsTurningLeft=g_Player_IsTurningRight=0;
        g_Player_IsSteppingLeftHold=g_Player_IsSteppingRightHold=0;
        g_Player_IsSteppingLeftTap=g_Player_IsSteppingRightTap=0;
        g_Player_HasMoveInput=0;
    }
    if(!free_locomotion() || mode==GAME_CONTROL_TANK ||
       (mode==GAME_CONTROL_HYBRID && (keys&0xf0))) {
        have_camera=have_travel=locked=0;return;
    }
    modern=1;
    int moving=game_control_vector(mode,keys,circle_x,circle_y,&x,&z);
    uint32_t now=game3ds_q12_clock();
    if(now-last_move_clock>1229 || map!=g_SavegamePtr->mapIdx || room!=g_SavegamePtr->mapRoomIdx)
        have_camera=have_travel=locked=0;
    last_move_clock=now;map=g_SavegamePtr->mapIdx;room=g_SavegamePtr->mapRoomIdx;
    SVECTOR angle;VECTOR3 position;
    vwGetViewAngle(&angle);vwGetViewPosition(&position);
    int yaw=angle.vy&4095,snap=0;
    if(have_camera) {
        int64_t dx=position.vx-previous_camera.vx,dz=position.vz-previous_camera.vz;
        int threshold=(284*(g_DeltaTime>0?g_DeltaTime:136))/136;
        snap=dx*dx+dz*dz>12288LL*12288 || ABS(norm(yaw-previous_yaw))>threshold;
    }
    previous_camera=position;previous_yaw=yaw;have_camera=1;
    if(moving) {
        int stick=ratan2(x,z);
        if(snap && have_travel && !locked) {locked=1;lock_yaw=travel_yaw;lock_stick=stick;}
        int steer=norm(stick-lock_stick);
        if(locked && ABS(steer)>512)locked=0;
        travel_yaw=(locked?lock_yaw+steer:yaw+stick)&4095;
        have_travel=1;
    } else locked=0;
    /* Semantic locomotion intent, not synthetic tank pad presses. Forward
     * history remains a two-bit register aged by Player_Controller itself. */
    g_Player_IsMovingForward=(g_Player_IsMovingForward&2)|(moving!=0);
    g_Player_IsMovingBackward=g_Player_IsTurningLeft=g_Player_IsTurningRight=0;
    g_Player_IsSteppingLeftHold=g_Player_IsSteppingRightHold=0;
    g_Player_IsSteppingLeftTap=g_Player_IsSteppingRightTap=0;
    g_Player_HasMoveInput=moving;
}
void Game3ds_MovementApply(void)
{
    if(!modern || !free_locomotion() || !have_travel)return;
    s_SubCharacter *p=&g_SysWork.playerWork.player;
    int difference=norm(travel_yaw-p->rotation.vy);
    int max_step=341*g_DeltaTime/136; /* ~900 degrees/s, PC's cosmetic slew. */
    int step=CLAMP(difference,-max_step,max_step);
    D_800C454C=step*16;
    g_Player_HeadingAngle=norm(travel_yaw-(p->rotation.vy+step));
    p->properties.player.headingAngle=g_Player_HeadingAngle;
}
static int axis(int value)
{
    /* C-stick service range is +/-156. Keep proportional input outside 15%. */
    int magnitude=ABS(value);if(magnitude<=24)return 0;
    if(magnitude>156)magnitude=156;
    return (value<0?-1:1)*(magnitude-24)*4096/132;
}
static int ease(int current,int target,unsigned dt)
{
    /* 70 ms first-order response, bounded to 150 deg/s. */
    int delta=(int)((int64_t)(target-current)*dt/(287+dt));
    int limit=(int)(1707LL*4096*dt/4096);
    return current+CLAMP(delta,-limit,limit);
}
void Game3ds_CameraLook(void *matrix)
{
    uint32_t now=game3ds_q12_clock(),dt=look_started?now-look_clock:136;
    look_clock=now;look_started=1;if(dt>273)dt=273;
    if(!Game3ds_CanPause() || !free_locomotion() ||
       g_SysWork.playerWork.extra.upperBodyState>PlayerUpperBodyState_WalkBackward) {look_yaw=look_pitch=0;return;}
    look_yaw=ease(look_yaw,axis(look_x)*228,dt);
    look_pitch=ease(look_pitch,axis(look_y)*136,dt);
    if(!look_yaw && !look_pitch)return;
    MATRIX rotation,result,*camera=matrix;
    SVECTOR offset={look_pitch/4096,look_yaw/4096,0,0};
    RotMatrix(&offset,&rotation);MulMatrix0(camera,&rotation,&result);
    memcpy(camera->m,result.m,sizeof(camera->m));
}
