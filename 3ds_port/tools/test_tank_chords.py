"""Exercise the production Tank chord translation with isolated semantic inputs."""
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).resolve().parents[1]
src=(p/'source/game_controls.c').read_text()
function=src[src.index('void Game3ds_TankActions(void)'):src.index('void Game3ds_InputSample(')]
driver=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
enum {GAME_CONTROL_TANK=0,GAME_CONTROL_MODERN=1,GAME_CONTROL_HYBRID=2,ControllerFlag_Square=1<<15};
enum {PlayerLowerBodyState_JumpBackward=10,PlayerLowerBodyState_QuickTurnRight=11,PlayerLowerBodyState_QuickTurnLeft=12};
static uint32_t keys;static unsigned tank_chord,tank_pending,mode;
struct Controller {unsigned heldBtnFlags;} controller,*g_Controller0=&controller;
struct {struct {int extraWalkRunCtrl;} config;} g_GameWork;
struct {struct {int isAiming;} playerCombat;struct {struct {int lowerBodyState;} extra;} playerWork;} g_SysWork;
int g_Player_DisableControl,g_Player_IsAiming,g_Player_IsSteppingLeftTap,g_Player_IsSteppingRightTap;
int g_Player_IsSteppingLeftHold,g_Player_IsSteppingRightHold,g_Player_IsMovingBackward,g_Player_IsMovingForward,g_Player_IsRunning;
unsigned game3ds_control_mode(void) {return mode;}
int Game3ds_CanPause(void) {return 1;}
'''+function+r'''
int main(void) {
 mode=0;keys=1<<9;Game3ds_TankActions();assert(g_Player_IsSteppingLeftHold && !g_Player_IsSteppingRightHold);
 keys=1<<8;Game3ds_TankActions();assert(g_Player_IsSteppingRightHold && !g_Player_IsSteppingLeftHold);
 keys=(1<<8)|(1<<9);Game3ds_TankActions();assert(!g_Player_IsSteppingRightHold && !g_Player_IsSteppingLeftHold && g_Player_IsMovingBackward && g_Player_IsRunning);
 g_SysWork.playerWork.extra.lowerBodyState=PlayerLowerBodyState_JumpBackward;Game3ds_TankActions();assert(!g_Player_IsMovingBackward && !g_Player_IsSteppingLeftTap && !g_Player_IsSteppingRightTap);
 keys=0;g_SysWork.playerWork.extra.lowerBodyState=0;Game3ds_TankActions();keys=1<<7;controller.heldBtnFlags=ControllerFlag_Square;Game3ds_TankActions();
 assert(g_Player_IsSteppingLeftTap && g_Player_IsSteppingRightTap && !g_Player_IsMovingBackward);
 g_SysWork.playerWork.extra.lowerBodyState=PlayerLowerBodyState_QuickTurnLeft;Game3ds_TankActions();assert(!g_Player_IsSteppingLeftTap && !g_Player_IsSteppingRightTap);
 mode=1;g_Player_IsSteppingLeftTap=7;Game3ds_TankActions();assert(g_Player_IsSteppingLeftTap==7);
 mode=2;Game3ds_TankActions();assert(g_Player_IsSteppingLeftTap==7);
 puts("PASS: Tank chord priority, one-shot behavior and Modern/Hybrid isolation");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-tank-') as tmp:
    f=Path(tmp)/'tank.c';exe=Path(tmp)/'tank';f.write_text(driver)
    subprocess.run(['cc','-std=c11','-Wall','-Werror',str(f),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
