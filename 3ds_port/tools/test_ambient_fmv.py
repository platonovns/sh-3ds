"""Exercise the actual FMV present routine against a synthetic letterboxed frame."""
import subprocess
import tempfile
from pathlib import Path

port = Path(__file__).resolve().parents[1]
source = (port / 'source/game_fmv.c').read_text()
present = source[source.index('static void present('):source.index('static uint32_t feed_audio(')]
driver = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint16_t u16;
#define FMV_WIDTH 320
#define FMV_HEIGHT 208
#define GFX_TOP 0
#define GFX_LEFT 0
static uint8_t fb[400*240*3];
static uint8_t *gfxGetFramebuffer(int a,int b,u16 *w,u16 *h){(void)a;(void)b;*w=400;*h=240;return fb;}
static void gfxFlushBuffers(void){} static void gfxSwapBuffers(void){} static void gspWaitForVBlank(void){}
''' + present + r'''
int main(void) {
    static uint8_t rgb[320*208*3];
    for(unsigned y=30;y<180;y++)for(unsigned x=0;x<320;x++) {
        rgb[(y*320+x)*3]=200;rgb[(y*320+x)*3+1]=100;rgb[(y*320+x)*3+2]=50;
    }
    present(rgb);
    for(unsigned x=0;x<400;x++)for(unsigned y=0;y<240;y++) {
        unsigned i=(x*240+239-y)*3;
        if(y<46 || y>=196) assert(!fb[i] && !fb[i+1] && !fb[i+2]);
        else if(x>=42 && x<358) assert(fb[i]==50 && fb[i+1]==100 && fb[i+2]==200);
        else if(x==40 || x==359) assert(fb[i]==41 && fb[i+1]==82 && fb[i+2]==165);
        else if(x==41 || x==358) assert(fb[i]==45 && fb[i+1]==91 && fb[i+2]==182);
        else if(y>=64 && y<176 && (x<40 || x>=360)) assert(fb[i]==32 && fb[i+1]==65 && fb[i+2]==130);
    }
    for(unsigned y=0;y<208;y++)for(unsigned x=0;x<320;x++)for(unsigned c=0;c<3;c++)
        rgb[(y*320+x)*3+c]=((x+y)&1)?200:0;
    present(rgb);
    for(unsigned y=0;y<208;y++)for(unsigned x=0;x<40;x++) {
        unsigned i=(x*240+239-(y+16))*3;
        assert(fb[i]==65 && fb[i+1]==65 && fb[i+2]==65);
    }
    assert(fb[(100*240+239-100)*3]==rgb[((100-16)*320+(100-40))*3+2]);
    puts("PASS: FMV 2px blend, sharp center, averaged margins and full-width black bars");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-ambient-') as name:
    root = Path(name); c = root / 'test.c'; binary = root / 'test'
    c.write_text(driver)
    subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
