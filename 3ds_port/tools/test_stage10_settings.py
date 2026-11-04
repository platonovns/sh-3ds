"""Production native-settings parser and file replacement on FAT-like rename.
Temporary host directory only; no user configuration or PSX card is touched.
"""
import hashlib,json,subprocess,tempfile
from pathlib import Path
p=Path(__file__).resolve().parents[1]
source=(p/'source/main_game.c').read_text()
block=source[source.index('static unsigned fps_limit='):source.index('void Game3ds_FpsLimit(')]
display_defaults=next(line for line in source.splitlines() if line.startswith('unsigned game_hp_indicator ='))
lower_defaults=next(line for line in source.splitlines() if line.startswith('static unsigned lower_auto='))
driver=r'''
#include <stdio.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
#include <assert.h>
#include "game_modern_controls.h"
'''+display_defaults+'\n'+lower_defaults+r'''
static unsigned initial_card;
static void game_card_set_initial(unsigned card) {initial_card=card;}
static void game3ds_recoverable(const char *op,int detail) {(void)op;(void)detail;}
static int fail_new;
static int fat_rename(const char *from,const char *to) {
    FILE *f=fopen(to,"rb");if(f){fclose(f);errno=EEXIST;return -1;}
    if(fail_new && strstr(from,".tmp")){fail_new=0;errno=EIO;return -1;}
    return rename(from,to);
}
#define rename fat_rename
'''+block+r'''
int main(void) {
    const char *path="sdmc:/3ds/silenthill/native_settings.cfg";
    const char *backup="sdmc:/3ds/silenthill/native_settings.bak";
    settings_load();assert(control_mode==GAME_CONTROL_HYBRID && fps_limit==60);
    assert(game_overlay_mode==0 && game_text_style==0 && game_lower_brightness==4 && game_card_number==1);
    assert(game_hp_indicator==1 && game_ammo_display==2 && game_map_enabled==1 && lower_auto==1 && game_map_invert==0);
    control_mode=2;fps_limit=60;game_overlay_mode=3;game_text_style=2;
    game_lower_brightness=3;game_card_number=8;settings_save();assert(!settings_error);
    control_mode=0;fps_limit=30;game_overlay_mode=0;game_text_style=0;game_lower_brightness=10;game_card_number=1;
    settings_load();assert(control_mode==2 && fps_limit==60 && game_overlay_mode==3 && game_text_style==2 && game_lower_brightness==3 && game_card_number==8 && initial_card==8);
    control_mode=1;fps_limit=30;settings_save();assert(!settings_error);
    control_mode=0;fps_limit=60;fail_new=1;settings_save();assert(settings_error==2);
    control_mode=0;fps_limit=30;settings_error=0;settings_load();assert(control_mode==1 && fps_limit==30);
    remove(backup);assert(!fat_rename(path,backup));
    control_mode=0;settings_load();assert(control_mode==1);
    FILE *f=fopen(path,"wb");assert(f);fputs("SH3DS1\nmode=99\nfps=99\n",f);fclose(f);
    control_mode=0;settings_load();assert(control_mode==1 && fps_limit==30);
    f=fopen(path,"wb");assert(f);fputs("SH3DS1\nmode=2\nfps=60\n",f);fclose(f);
    settings_load();assert(control_mode==2 && fps_limit==60 && game_card_number==1 && game_lower_brightness==10 && game_overlay_mode==0);
    puts("PASS: requested defaults, repeated saves, restart, FAT rename, failed commit and interrupted commit recovery.");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-settings-') as directory:
    root=Path(directory);(root/'sdmc:/3ds/silenthill').mkdir(parents=True)
    c=root/'test.c';c.write_text(driver);exe=root/'test'
    subprocess.run(['gcc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-I'+str(p/'include'),str(c),'-o',str(exe)],check=True)
    run=subprocess.run([str(exe)],cwd=root,capture_output=True,text=True,check=True)
    assert 'PASS' in run.stdout and not run.stderr,run
    report=dict(status='PASS',scope=__doc__,result=run.stdout.strip(),production_settings_sha256=hashlib.sha256(block.encode()).hexdigest())
    print(json.dumps(report,indent=2))
