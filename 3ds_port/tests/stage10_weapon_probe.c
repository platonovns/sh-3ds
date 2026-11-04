#include "game.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/player.h"
#include "bodyprog/item_screens.h"
#include <string.h>
void stage10_weapon_copy(unsigned weapon,unsigned *out)
{
    g_SysWork.playerCombat.weaponAttack=weapon;
    g_Player_LastWeaponSelected=weapon;
    GameFs_WeaponInfoUpdate();
    memcpy(out,D_800C44F0,sizeof(D_800C44F0));
    out[20]=(unsigned)(s32)D_800AF5C6;
    out[21]=(unsigned)(s32)D_800AF624;
    out[22]=(unsigned)(s32)D_800AF626;
}
