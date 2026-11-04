"""Exercise SELECT release and SELECT+LEFT through the production pad path."""
from pathlib import Path
import subprocess
import tempfile

port=Path(__file__).resolve().parents[1]
source=(port/'source/main_game.c').read_text()
start=source.index('    unsigned raw_select=held&KEY_SELECT;')
end=source.index('    unsigned start_down=',start)
body=source[start:end]
driver=r'''
#include <assert.h>
#include <stdio.h>
#define KEY_SELECT 1u
#define KEY_START 2u
#define KEY_DUP 4u
#define KEY_DDOWN 8u
#define KEY_DRIGHT 16u
#define KEY_DLEFT 32u
static unsigned game_lower_brightness=10,game_map_invert,game_map_enabled=1,saves;
static int Game3ds_CanPause(void){return 1;}
static void settings_save(void){saves++;}
static unsigned poll(unsigned held) {
    static unsigned brightness_chord,select_pending,select_consumed;
''' + body + r'''
    return held;
}
int main(void) {
    assert(!(poll(KEY_SELECT|KEY_DLEFT)&(KEY_SELECT|KEY_DLEFT)));
    assert(!game_map_enabled && saves==1);
    assert(!(poll(0)&KEY_SELECT));
    assert(!(poll(KEY_SELECT)&KEY_SELECT));
    assert(poll(0)&KEY_SELECT); /* original map remains available with Map Off */
    assert(!(poll(KEY_SELECT|KEY_DLEFT)&KEY_DLEFT));
    assert(game_map_enabled && saves==2);
    assert(!(poll(0)&KEY_SELECT));
    puts("PASS: plain SELECT opens manual map with Map Off; shortcut is consumed");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-manual-map-') as name:
    root=Path(name);(root/'test.c').write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(root/'test.c'),
                    '-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)
