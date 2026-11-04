"""Check the production mask vertices for both source edges and output rows."""
from pathlib import Path
import subprocess
import tempfile

port = Path(__file__).resolve().parents[1]
source = (port / 'source/render_3ds.c').read_text()
start = source.index('if(renderer.ambient_mask_target) {', source.index('static void finish_frame('))
end = source.index('GSPGPU_FlushDataCache(renderer.present_vertices,n*sizeof(Render3dsVertex));', start)
block = source[start:end]
driver = r'''
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "render_3ds.h"
static Render3dsVertex vertices[270];
static struct {void *ambient_mask_target;struct {unsigned width;} native_color;
               Render3dsVertex *present_vertices;} renderer;
static unsigned produce(float u,float v) {unsigned n=210;
''' + block + r'''
 return n;}
int main(void) {
    renderer.ambient_mask_target=vertices;renderer.native_color.width=512;
    renderer.present_vertices=vertices;
    for(unsigned height=224;height<=448;height+=224) {
        float u=320.f/512.f,v=height/512.f;
        assert(produce(u,v)==270);
        for(unsigned side=0;side<2;side++)for(unsigned tap=0;tap<4;tap++) {
            Render3dsVertex *q=&vertices[210+(side*4+tap)*6];
            float source_x=(side?280.f:0.f)+tap*10.f+5.f;
            assert(fabsf(q[0].u-source_x/512.f)<0.000001f);
            assert(q[0].x==(side?4.f:0.f) && q[1].x==(side?8.f:4.f));
            assert(q[0].y==0 && q[2].y==240 && q[0].v==0 && q[2].v==v);
        }
        for(unsigned side=0;side<2;side++) {
            Render3dsVertex *q=&vertices[258+side*6];
            assert(q[0].x==(side?360.f:0.f) && q[1].x==(side?400.f:40.f));
            assert(q[0].u==(side?.75f:.25f) && q[2].v==240.f/256.f);
            for(unsigned y=0;y<240;y++) {
                float source_y=(y+.5f)*v/240.f;
                float mask_y=(y+.5f)*(240.f/256.f)/240.f;
                assert(fabsf(source_y-(mask_y*256.f/240.f)*v)<0.000001f);
            }
        }
    }
    puts("PASS: static ambient mask uses four matching edge samples per row and side");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-static-mask-') as name:
    root = Path(name)
    (root / 'test.c').write_text(driver)
    subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I'+str(port/'include'),
                    str(root/'test.c'), '-lm', '-o', str(root/'test')], check=True)
    subprocess.run([str(root/'test')], check=True)
