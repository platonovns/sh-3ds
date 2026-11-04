"""Exercise mask-stage setup after Citro3D consumed the previous dirty flag."""
from pathlib import Path
import subprocess
import tempfile

port=Path(__file__).resolve().parents[1]
source=(port/'source/render_3ds.c').read_text()
start=source.index('C3D_TexSetFilter(&renderer.native_color,GPU_NEAREST',
                   source.index('C3D_FrameDrawOn(renderer.ambient_mask_target)'))
end=source.index('draw_arrays(210,48);',start)+len('draw_arrays(210,48);')
setup=source[start:end]
driver=r'''
#include <assert.h>
#include <stdio.h>
enum {GPU_NEAREST,GPU_TEXTURE0,GPU_PRIMARY_COLOR,GPU_PREVIOUS,
 GPU_TEVOP_A_SRC_R,GPU_TEVOP_A_SRC_G,GPU_TEVOP_A_SRC_ALPHA,GPU_TEVOP_A_SRC_B,
 GPU_TEVOP_RGB_SRC_ALPHA,GPU_TEVOP_RGB_SRC_COLOR,GPU_ADD,GPU_TEVSCALE_4,
 GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,C3D_Alpha,C3D_RGB};
typedef struct {int alpha_source,alpha_func,op1,op2;} C3D_TexEnv;
static C3D_TexEnv stages[4];static int dirty[4];
static struct {int native_color;} renderer;
static C3D_TexEnv *C3D_GetTexEnv(int i){dirty[i]=1;return &stages[i];}
static void C3D_TexSetFilter(int *t,int a,int b){(void)t;(void)a;(void)b;}
static void C3D_TexBind(int u,int *t){(void)u;(void)t;}
static void C3D_TexEnvInit(C3D_TexEnv *e){*e=(C3D_TexEnv){0};}
static void C3D_TexEnvSrc(C3D_TexEnv *e,int m,int a,int b,int c)
{(void)b;(void)c;if(m==C3D_Alpha)e->alpha_source=a;}
static void C3D_TexEnvOpAlpha(C3D_TexEnv *e,int a,int b,int c)
{(void)c;e->op1=a;e->op2=b;}
static void C3D_TexEnvFunc(C3D_TexEnv *e,int m,int f){if(m==C3D_Alpha)e->alpha_func=f;}
static void C3D_TexEnvScale(C3D_TexEnv *e,int m,int s){(void)e;(void)m;(void)s;}
static void C3D_TexEnvOpRgb(C3D_TexEnv *e,int a,int b,int c){(void)e;(void)a;(void)b;(void)c;}
static void C3D_AlphaBlend(int a,int b,int c,int d,int e,int f)
{(void)a;(void)b;(void)c;(void)d;(void)e;(void)f;}
static void draw_arrays(int first,int count) {
    assert(first==210 && count==48);
    assert(dirty[0] && stages[0].alpha_source==GPU_TEXTURE0);
    assert(stages[0].alpha_func==GPU_ADD && stages[0].op1==GPU_TEVOP_A_SRC_R && stages[0].op2==GPU_TEVOP_A_SRC_G);
}
int main(void) {C3D_TexEnv *env=&stages[0];
''' + setup + r'''
puts("PASS: source-dependent mask stage is marked dirty before GPU draw");}
'''
with tempfile.TemporaryDirectory(prefix='sh-mask-state-') as name:
    root=Path(name)
    (root/'test.c').write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(root/'test.c'),
                    '-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)

start=source.index('Mtx_OrthoTilt(&present_projection')
end=source.index('C3D_TexSetFilter(&renderer.native_color,GPU_NEAREST',start)
present=source[start:end]
assert present.index('draw_arrays(198,12)') < present.index('draw_arrays(258,12)')
assert 'GPU_ZERO,GPU_SRC_COLOR' in present
print('PASS: final side output applies mask after ambient interpolation')
