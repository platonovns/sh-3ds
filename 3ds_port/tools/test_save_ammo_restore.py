#!/usr/bin/env python3
"""Exercise the production save-inventory restoration code in isolation."""

from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[2] / "src/bodyprog/player_control.c").read_text()
start = source.index("    itemGroupId = INV_ITEM_GROUP(g_SavegamePtr->equippedWeapon);", source.index("void Game_PlayerInfoInit("))
end = source.index("    g_SysWork.playerCombat.isAiming = false;", start)
block = source[start:end]

harness = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define INV_ITEM_COUNT_MAX 40
#define INV_ITEM_GROUP(id) ((id) >> 5)
#define INV_WEAPON_AMMO_ID(id) ((id) + 32)
#define NO_VALUE (-1)
enum { InvItemGroup_MeleeWeapons = 4, InvItemGroup_GunWeapons = 5,
       InvItemId_KitchenKnife = 128 };
typedef struct { uint8_t id_0, count_1, command_2, field_3; } Item;
struct Save { Item items[40]; uint8_t following[512]; uint8_t equippedWeapon; } save;
struct Save *g_SavegamePtr = &save;
struct { struct { int weaponAttack, currentWeaponAmmo, totalWeaponAmmo,
                  weaponInventoryIdx; } playerCombat; } g_SysWork;
static void restore(void) {
    int i, itemGroupId;
''' + block + r'''
}
static void reset(int weapon) {
    memset(&save, 0, sizeof(save));
    memset(&g_SysWork, 0xff, sizeof(g_SysWork));
    save.equippedWeapon = weapon;
    save.items[0].id_0 = weapon;
    save.items[0].count_1 = 3;
    /* A false ammo entry immediately after the inventory triggered the bug. */
    save.following[0] = weapon + 32;
    save.following[1] = 255;
}
int main(void) {
    for (int gun = 160; gun <= 162; ++gun) {
        reset(gun);
        restore();
        assert(g_SysWork.playerCombat.currentWeaponAmmo == 3);
        assert(g_SysWork.playerCombat.totalWeaponAmmo == 0);
        assert(g_SysWork.playerCombat.weaponInventoryIdx == 0);
        const int counts[] = {0, 1, 127, 128, 200, 255};
        for (unsigned n = 0; n < sizeof(counts)/sizeof(counts[0]); ++n) {
            reset(gun);
            save.items[39].id_0 = gun + 32;
            save.items[39].count_1 = counts[n];
            restore();
            assert(g_SysWork.playerCombat.totalWeaponAmmo == counts[n]);
        }
        reset(gun);
        save.items[0].id_0 = 0; /* Invalid save: equipped gun absent. */
        restore();
        assert(g_SysWork.playerCombat.weaponAttack == NO_VALUE);
        assert(g_SysWork.playerCombat.weaponInventoryIdx == NO_VALUE);
        assert(g_SysWork.playerCombat.currentWeaponAmmo == 0);
        assert(g_SysWork.playerCombat.totalWeaponAmmo == 0);
    }
    reset(128); /* Melee weapons have no reserve. */
    restore();
    assert(g_SysWork.playerCombat.totalWeaponAmmo == 0);
    reset(0); /* No weapon equipped. */
    restore();
    assert(g_SysWork.playerCombat.weaponAttack == NO_VALUE);
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="save-ammo-test-") as temp:
    path = Path(temp)
    (path / "test.c").write_text(harness)
    subprocess.run(["cc", "-std=c11", "-O2", "-fsanitize=address,undefined", "-o", str(path / "test"), str(path / "test.c")], check=True)
    subprocess.run([str(path / "test")], check=True)
print("Save ammo restoration regression checks passed")
