"""Exercise the real movement gate during aim/reload handoff."""
from pathlib import Path
import subprocess,tempfile
port=Path(__file__).resolve().parents[1]
s=(port/'source/game_controls.c').read_text()
body=s[s.index('static int free_locomotion(void)'):s.index('void Game3ds_MovementApply(void)')]
driver=r'''
#include <stdint.h>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include "game_modern_controls.h"
#define ABS(x) abs(x)
enum {GameState_InGame=11,SysState_Gameplay=0,SysFlag_CutsceneActive=1,SysFlag_DemoActive=2,PlayerState_None=0,PlayerState_Combat=1,PlayerLowerBodyState_RunLeft=8,PlayerUpperBodyState_WalkBackward=8,PlayerUpperBodyState_Reload=26};
typedef struct {int vy;} SVECTOR; typedef struct {int vx,vz;} VECTOR3;
static struct {int gameState;struct {int extraWeaponCtrl;} config;} g_GameWork;
static struct {int sysState,sysFlags;struct {int isAiming;} playerCombat;struct {struct {int state,lowerBodyState,upperBodyState;} extra;} playerWork;} g_SysWork;
static struct {int mapIdx,mapRoomIdx;} save,*g_SavegamePtr=&save;
static int g_Player_DisableControl,g_Player_IsAiming,g_Player_IsMovingForward,g_Player_IsMovingBackward,g_Player_IsTurningLeft,g_Player_IsTurningRight,g_Player_IsSteppingLeftHold,g_Player_IsSteppingRightHold,g_Player_IsSteppingLeftTap,g_Player_IsSteppingRightTap,g_Player_HasMoveInput,g_DeltaTime=136;
static int circle_x,circle_y,modern,have_camera,have_travel,locked,last_mode=-1,previous_yaw,travel_yaw,lock_yaw,lock_stick,map=-1,room=-1;
static VECTOR3 previous_camera;static uint32_t keys,last_move_clock,mode;
static int norm(int a){return ((a+2048)&4095)-2048;}
static void Game3ds_ControlsReset(void){modern=have_camera=have_travel=locked=0;}
static unsigned game3ds_control_mode(void){return mode;} static uint32_t game3ds_q12_clock(void){return 100;}
static void vwGetViewAngle(SVECTOR *a){a->vy=0;} static void vwGetViewPosition(VECTOR3 *p){p->vx=p->vz=0;}
static int ratan2(int x,int z){(void)x;(void)z;return 0;}
'''+body+r'''
static void seed(void){g_Player_IsMovingBackward=1;g_Player_IsMovingForward=1;g_Player_IsTurningRight=1;g_Player_HasMoveInput=1;}
int main(void){
 g_GameWork.gameState=GameState_InGame;g_SysWork.sysState=SysState_Gameplay;
 g_SysWork.playerWork.extra.upperBodyState=PlayerUpperBodyState_Reload;g_SysWork.playerWork.extra.lowerBodyState=20;circle_y=-100;
 mode=GAME_CONTROL_MODERN;seed();Game3ds_MovementInput();assert(!g_Player_IsMovingBackward&&!g_Player_IsMovingForward&&!g_Player_HasMoveInput);
 mode=GAME_CONTROL_HYBRID;keys=0;seed();Game3ds_MovementInput();assert(!g_Player_IsMovingBackward);
 g_SysWork.playerCombat.isAiming=1;g_GameWork.config.extraWeaponCtrl=0;seed();Game3ds_MovementInput();assert(g_Player_IsMovingBackward);
 g_GameWork.config.extraWeaponCtrl=1;seed();Game3ds_MovementInput();assert(!g_Player_IsMovingBackward);g_SysWork.playerCombat.isAiming=0;
 keys=1<<7;seed();Game3ds_MovementInput();assert(g_Player_IsMovingBackward);
 mode=GAME_CONTROL_TANK;keys=0;seed();Game3ds_MovementInput();assert(g_Player_IsMovingBackward);
 mode=GAME_CONTROL_MODERN;g_SysWork.playerWork.extra.state=2;seed();Game3ds_MovementInput();assert(g_Player_HasMoveInput);
 g_SysWork.playerWork.extra.state=PlayerState_None;
 mode=GAME_CONTROL_MODERN;g_Player_IsAiming=1;seed();Game3ds_MovementInput();assert(g_Player_IsMovingBackward);
 g_Player_IsAiming=0;g_SysWork.playerWork.extra.lowerBodyState=0;seed();Game3ds_MovementInput();assert(modern && g_Player_IsMovingForward && !g_Player_IsMovingBackward);
 g_SysWork.playerWork.extra.state=PlayerState_Combat;seed();Game3ds_MovementInput();assert(modern && g_Player_IsMovingForward && !g_Player_IsMovingBackward);
 puts("PASS: modern/hybrid suppress tank intent during reload; tank and aim preserved");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-control-transition-') as d:
 f=Path(d)/'test.c';exe=Path(d)/'test';f.write_text(driver)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-I'+str(port/'include'),str(f),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
