"""Exercise the production settings parser and migration in a temporary directory."""
import subprocess
import tempfile
from pathlib import Path

port = Path(__file__).resolve().parents[1]
source = (port / 'source/main_game.c').read_text()
settings = source[source.index('static unsigned fps_limit='):source.index('void Game3ds_FpsLimit(')]
driver = r'''
#include <stdio.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
#include <assert.h>
#include "game_modern_controls.h"
unsigned game_hp_indicator=1,game_ammo_display=1,game_map_enabled=1;
static unsigned lower_auto=1;
static unsigned initial_card;
static void game_card_set_initial(unsigned card) {initial_card=card;}
static void game3ds_recoverable(const char *op,int detail) {(void)op;(void)detail;}
''' + settings + r'''
int main(void) {
    const char *p="sdmc:/3ds/silenthill/native_settings.cfg";
    FILE *f=fopen(p,"wb");assert(f);
    fputs("SH3DS4\nmode=2\nfps=60\noverlay=3\nstyle=2\ncursor=1\nbrightness=3\nlower=1\ncard=8\nhp=2\nammo=3\ninvert=1\nhud_invert=1\n",f);fclose(f);
    settings_load();
    assert(control_mode==2 && fps_limit==60 && game_lower_brightness==6 && initial_card==8);
    assert(game_hp_indicator==2 && game_ammo_display==2 && game_map_enabled==1);
    for(unsigned old=0;old<4;old++) {
        f=fopen(p,"wb");assert(f);
        fprintf(f,"SH3DS8\nmode=0\nfps=30\noverlay=0\nstyle=0\nbrightness=10\ncard=1\nhp=2\nammo=%u\nauto_lcd=1\nmap_invert=1\n",old);fclose(f);
        game_map_enabled=0;settings_load();
        assert(game_map_enabled==1 && game_map_invert==1);
        assert(game_ammo_display==(old==3?2:old==2?0:old));
    }
    for(unsigned old=0;old<3;old++) {
        f=fopen(p,"wb");assert(f);
        fprintf(f,"SH3DS10\nmode=2\nfps=60\noverlay=1\nstyle=2\nbrightness=7\ncard=3\nhp=2\nammo=1\nauto_lcd=0\nmap_invert=1\nmap_enabled=0\nculling=%u\n",old);fclose(f);
        settings_load();
        assert(control_mode==2 && fps_limit==60 && game_overlay_mode==1 && game_text_style==2);
        assert(game_lower_brightness==7 && game_card_number==3 && game_hp_indicator==2 && game_ammo_display==1);
        assert(lower_auto==0 && game_map_invert==1 && game_map_enabled==0);
    }
    game_lower_brightness=1;game_map_invert=1;game_map_enabled=0;game_ammo_display=2;settings_save();assert(!settings_error);
    game_lower_brightness=10;game_map_invert=0;game_map_enabled=1;game_ammo_display=0;
    settings_load();assert(game_lower_brightness==1 && game_map_invert==1 && game_map_enabled==0 && game_ammo_display==2);
    f=fopen(p,"rb");assert(f);char b[512];size_t n=fread(b,1,sizeof(b)-1,f);fclose(f);b[n]=0;
    assert(strstr(b,"SH3DS9\n") && !strstr(b,"cursor=") && !strstr(b,"lower=") && strstr(b,"map_invert=1\n") && strstr(b,"map_enabled=0\n"));
    puts("PASS: legacy settings migration and 10% brightness persistence");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-polish-settings-') as name:
    root = Path(name)
    (root / 'sdmc:/3ds/silenthill').mkdir(parents=True)
    c = root / 'settings.c'
    c.write_text(driver)
    binary = root / 'settings'
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-I' + str(port / 'include'),
                    str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], cwd=root, check=True)
