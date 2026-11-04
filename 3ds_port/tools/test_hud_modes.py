"""Run the production HP/ammo HUD for all three display modes."""
from pathlib import Path
import subprocess
import tempfile

port=Path(__file__).resolve().parents[1]
source=(port/'source/game_lower.c').read_text()
color=source[source.index('static uint16_t map_color('):source.index('static void map_load(')]
glyphs=source[source.index('static const unsigned char digits'):source.index('void Game3ds_LowerCounter(')]
hud=source[source.index('static void hud('):source.index('int Game3ds_LowerDraw(')]
driver=r'''
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <assert.h>
#define Q12(x) ((int)((x)*4096))
#define Chara_Harry 1
#define InvItemGroup_GunWeapons 1
#define InvItemId_HyperBlaster 99
#define INV_ITEM_GROUP(x) ((x)==2?1:0)
static unsigned game_lower_brightness=10,game_text_style=0,game_hp_indicator=2,game_ammo_display;
static int g_Player_DisableControl,g_Inventory_EquippedItem=2;
static struct {struct {struct {struct {int charaId;} model;int health;} player;} playerWork;
               struct {int currentWeaponAmmo,totalWeaponAmmo,isAiming;} playerCombat;} g_SysWork;
static struct {void *registeredCharaModels[2];} g_WorldGfxWork;
static int Game3ds_CanPause(void){return 1;}
''' + color + glyphs + hud + r'''
int main(void) {
    uint16_t p[320*240];
    g_SysWork.playerWork.player.model.charaId=Chara_Harry;
    g_SysWork.playerWork.player.health=100*4096;
    g_WorldGfxWork.registeredCharaModels[Chara_Harry]=p;
    g_SysWork.playerCombat.currentWeaponAmmo=12;g_SysWork.playerCombat.totalWeaponAmmo=37;
    for(unsigned mode=0;mode<3;mode++) {
        memset(p,0,sizeof(p));game_ammo_display=mode;hud(p);
        unsigned green=0,white=0;for(unsigned i=0;i<320*240;i++){green+=p[i]==0x07e0;white+=p[i]==0xffff;}
        if(mode==2)assert(!green && !white);else assert(green==64 && white>0);
    }
    puts("PASS: Current and Current+Reserve show HP/ammo; Off hides both");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-hud-') as name:
    root=Path(name);(root/'test.c').write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(root/'test.c'),
                    '-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
