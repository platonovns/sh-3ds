"""Exercise the production marker colour while keeping HUD drawing separate."""
import subprocess
import tempfile
from pathlib import Path
port=Path(__file__).resolve().parents[1]
s=(port/'source/game_lower.c').read_text()
color=s[s.index('static uint16_t map_color('):s.index('/* LCD is rotated')]
marker=s[s.index('static void marker('):s.index('static const unsigned char digits')]
driver=r"""
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
static unsigned game_lower_brightness=10,game_map_invert;
static int g_3dsMapQueryX,g_3dsMapQueryZ,g_PcMapQueryAngle;
static int Math_AngleNormalizeSigned(int a){return a;}
static int Math_Sin(int a){(void)a;return 0;}
static int Math_Cos(int a){(void)a;return 4096;}
static uint16_t observed;
static void line(uint16_t*p,int x0,int y0,int x1,int y1,uint16_t c)
{(void)p;(void)x0;(void)y0;(void)x1;(void)y1;observed=c;}
"""+color+marker+r"""
int main(void){uint16_t dummy=0;marker(&dummy);assert(observed==0xf800);
    game_map_invert=1;marker(&dummy);assert(observed==0x07ff);
    game_lower_brightness=1;marker(&dummy);assert(observed==0x00c3);
    puts("PASS: Harry marker follows map inversion; HUD is separately drawn");}
"""
with tempfile.TemporaryDirectory(prefix='sh-map-marker-') as name:
    root=Path(name);c=root/'test.c';binary=root/'test';c.write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
