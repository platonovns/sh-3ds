"""Exercise the production quick-reload entry and its state/ammo guards."""
from pathlib import Path
import subprocess
import tempfile

port = Path(__file__).resolve().parents[1]
source = (port.parent / 'src/bodyprog/player_control.c').read_text()
start = source.index('    {\n        extern u8 g_Items_GunsMaxLoadAmmo[36];',
                     source.index('void Player_CombatStateUpdate'))
end = source.index('\n#endif', start)
body = source[start:end]
driver = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int32_t s32;
enum {EquippedWeaponId_Handgun=32, EquippedWeaponId_Shotgun=34,
      AttackInputType_Tap=0, InvItemId_KitchenKnife=128,
      PlayerUpperBodyState_WalkBackward=2, PlayerUpperBodyState_TurnRight=3,
      PlayerUpperBodyState_TurnLeft=4, PlayerUpperBodyState_Aim=5,
      PlayerUpperBodyState_AimTargetLock=6, PlayerUpperBodyState_Reload=7,
      PlayerLowerBodyState_Reload=7, PlayerState_None=0, PlayerState_Combat=1,
      SysState_Gameplay=0, SysFlag_CutsceneActive=1, SysFlag_DemoActive=2,
      PlayerFlag_Unk2=2, PlayerFlag_Unk9=512, NO_VALUE=-1};
#define WEAPON_ATTACK(w,t) ((w)+(t)*10)
#define Q12(x) ((x)*4096)
#define D_800AF624 17
typedef struct {int keyframeIdx,time;} Anim;
typedef struct {int stateStep,controlState; Anim anim;} Model;
typedef struct {int state,upperBodyState,lowerBodyState; Model model;} Extra;
typedef struct {Model model;} Player;
static struct {struct {struct {u16 aim,run;} controllerConfig;} config;} work;
static struct {u16 heldBtnFlags,clickedBtnFlags;} pad;
static struct {int equippedWeapon;} save;
static struct {int sysState,sysFlags,targetNpcIdx; struct {
    int weaponAttack,totalWeaponAmmo,currentWeaponAmmo,isAiming;} playerCombat;} g_SysWork;
static struct {int flags;} playerProps;
static int g_Player_DisableControl, g_Player_TargetNpcIdx;
static u8 g_Items_GunsMaxLoadAmmo[36];
#define g_GameWorkPtr (&work)
#define g_Controller0 (&pad)
#define g_SavegamePtr (&save)
static void update(Player *player, Extra *extra) {
''' + body + r'''
}
static void setup(int weapon) {
    work.config.controllerConfig.aim=1;work.config.controllerConfig.run=2;
    pad.heldBtnFlags=3;pad.clickedBtnFlags=2;
    g_SysWork.sysState=0;g_SysWork.sysFlags=0;g_Player_DisableControl=0;
    g_SysWork.playerCombat.weaponAttack=weapon;
    g_SysWork.playerCombat.currentWeaponAmmo=1;
    g_SysWork.playerCombat.totalWeaponAmmo=5;
    g_SysWork.playerCombat.isAiming=0;
    save.equippedWeapon=weapon+InvItemId_KitchenKnife;
    g_Items_GunsMaxLoadAmmo[32]=15;g_Items_GunsMaxLoadAmmo[33]=6;
    g_Items_GunsMaxLoadAmmo[34]=6;
}
static int invoke(void) {Player p={0};Extra e={0};update(&p,&e);
    if(e.upperBodyState==PlayerUpperBodyState_Reload) {
        assert(e.lowerBodyState==PlayerLowerBodyState_Reload);
        assert(e.model.anim.keyframeIdx==D_800AF624);
        assert(g_SysWork.playerCombat.currentWeaponAmmo==1);
        assert(g_SysWork.playerCombat.totalWeaponAmmo==5);
        return 1;
    } return 0;
}
int main(void) {
    for(int weapon=32;weapon<=34;weapon++) {
        setup(weapon);assert(invoke());
        setup(weapon);g_SysWork.playerCombat.totalWeaponAmmo=0;assert(!invoke());
        setup(weapon);g_SysWork.playerCombat.currentWeaponAmmo=g_Items_GunsMaxLoadAmmo[weapon];assert(!invoke());
        setup(weapon);save.equippedWeapon++;assert(!invoke());
        setup(weapon);pad.clickedBtnFlags=0;assert(!invoke());
        setup(weapon);pad.heldBtnFlags=1;assert(!invoke());
        setup(weapon);g_SysWork.sysFlags=SysFlag_CutsceneActive;assert(!invoke());
        setup(weapon);g_SysWork.sysFlags=SysFlag_DemoActive;assert(!invoke());
        setup(weapon);g_Player_DisableControl=1;assert(!invoke());
        setup(weapon);g_SysWork.sysState=1;assert(!invoke());
    }
    setup(0);assert(!invoke());setup(35);assert(!invoke());
    puts("PASS: handgun/rifle/shotgun use common reload; ammo, state and weapon guards");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-reload-') as temp:
    root = Path(temp)
    (root / 'test.c').write_text(driver)
    subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(root / 'test.c'), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True)
