"""Exercise the actual carousel glow-grid producer on the host."""
from pathlib import Path
import subprocess
import tempfile

port = Path(__file__).resolve().parents[1]
source = (port.parent / 'src/maps/map6_s04/map6_s04_2.c').read_text()
body = source[source.index('void* func_800DE380('):source.index('\nvoid func_800DE5CC(')]
driver = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef int32_t s32; typedef uint32_t u32;
typedef uint32_t GsOT_TAG; typedef unsigned char PACKET;
typedef struct {int16_t x0,y0,x1,y1,x2,y2,x3,y3; s32 r0,r1,r2,r3;} POLY_G4;
typedef struct {unsigned x;} DR_TPAGE;
static u32 width=400;static unsigned count;
void game3ds_gpu_extent(u32 *w,u32 *h){*w=width;*h=240;}
static s32 func_800DE350(int n){(void)n;return 1;}
#define setPolyG4(p) ((void)(p))
#define addPrim(ot,p) ((void)(ot),(void)(p))
#define getTPageN(a,b,c,d) (0)
#define setDrawTPage(p,a,b,c) ((void)(p))
''' + body + r'''
int main(void){
    POLY_G4 cells[27*18+4];GsOT_TAG ot=0;
    func_800DE380(&ot,(PACKET*)cells);
    for(int y=0;y<18;y++)for(int x=0;x<27;x++){
        POLY_G4 *p=&cells[y*27+x];
        assert(p->x0==-200+x*400/27 && p->x1==-200+(x+1)*400/27);
        assert(p->x0==p->x2 && p->x1==p->x3);
        if(x)assert(cells[y*27+x-1].x1==p->x0);
    }
    assert(cells[0].x0==-200 && cells[26].x1==200);
    width=320;func_800DE380(&ot,(PACKET*)cells);
    assert(cells[0].x0==-166 && cells[26].x1==158);
    puts("PASS: glow grid covers 400px without seams; classic coordinates preserved");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-flauros-') as name:
    path = Path(name)
    (path / 'test.c').write_text(driver)
    subprocess.run(['gcc', '-std=c11', '-DSH_3DS_PORT', str(path / 'test.c'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
