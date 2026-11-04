"""Exercise the production SELECT chords with mock button input."""
import subprocess
import tempfile
from pathlib import Path
port = Path(__file__).resolve().parents[1]
source = (port / 'source/main_game.c').read_text()
block = source[source.index('    unsigned raw_select=held&KEY_SELECT;'):source.index('    /* Defer a plain SELECT')]
driver = r'''
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
static unsigned chord(unsigned held) {
    static unsigned brightness_chord,select_consumed;
''' + block + r'''
    (void)select_consumed;(void)raw_select;return held;
}
int main(void) {
    assert(!(chord(KEY_SELECT|KEY_DRIGHT)&KEY_DRIGHT));assert(game_map_invert==1 && saves==1);
    chord(KEY_SELECT|KEY_DRIGHT);assert(game_map_invert==1 && saves==1);
    chord(KEY_SELECT);chord(KEY_SELECT|KEY_DRIGHT);assert(game_map_invert==0 && saves==2);
    chord(0);chord(KEY_SELECT|KEY_DUP);assert(game_lower_brightness==10 && saves==2);
    for(int i=0;i<12;i++){chord(0);chord(KEY_SELECT|KEY_DDOWN);}
    assert(game_lower_brightness==1 && saves==11);
    chord(0);chord(KEY_SELECT|KEY_DUP);assert(game_lower_brightness==2 && saves==12);
    chord(0);assert(!(chord(KEY_SELECT|KEY_DLEFT)&KEY_DLEFT));assert(saves==13 && !game_map_enabled);
    chord(KEY_SELECT|KEY_DLEFT);assert(saves==13 && !game_map_enabled);
    chord(KEY_SELECT);chord(KEY_SELECT|KEY_DLEFT);assert(saves==14 && game_map_enabled);
    puts("PASS: SELECT+LEFT map, RIGHT invert, UP/DOWN brightness and held-key debouncing");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-map-chord-') as name:
    root=Path(name); c=root/'chord.c'; binary=root/'chord';c.write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
