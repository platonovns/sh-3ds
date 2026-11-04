/* Synthetic integer PSX mesh. Left: historical stretched grid; right: native.
 * Exact coverage is checked independently with rational scanline intersections. */
#include <3ds.h>
#include <citro3d.h>
#include <stdio.h>
#include "render_3ds.h"
#include "game_screen.h"
uint64_t game3ds_ticks(void) {return svcGetSystemTick();}
static bool triangle(const int p[3][2],unsigned panel)
{
    Render3dsVertex v[3]={0};
    for(unsigned j=0;j<3;j++) {
        v[j].x=panel?208+p[j][0]+.5f:8+p[j][0];
        v[j].y=panel?8+p[j][1]+.5f:p[j][1]*(240.0f/224);
        v[j].r=v[j].g=v[j].b=1;v[j].a=1;
    }
    return render3ds_draw_psx_triangles(v,3,NULL,0);
}
static bool surface;
static bool surface_triangle(const int p[3][2])
{
    Render3dsVertex v[3]={0};
    for(unsigned i=0;i<3;i++) {
        float point[2];game_screen_point(point,p[i][0],p[i][1]);v[i].x=point[0];v[i].y=point[1];
        v[i].r=v[i].g=v[i].b=v[i].a=1;
    }
    return render3ds_draw_psx_triangles(v,3,NULL,0);
}
int main(void)
{
    gfxInitDefault();consoleInit(GFX_BOTTOM,NULL);bool ok=render3ds_init();
    FILE *f=fopen("sdmc:/3ds/silenthill/stage5_probe_surface.txt","rb");surface=f!=NULL;
    if(f){fclose(f);remove("sdmc:/3ds/silenthill/stage5_probe_surface.txt");}
    printf("Stage5 raster grid\nLeft OLD 224 -> 240\nRight native integer samples\nSTART exits\n");
    FILE *status=fopen("sdmc:/3ds/silenthill/stage5_raster_status.txt","wb");
    if(status){fprintf(status,"init=%u surface=%u error=%s\n",ok,surface,render3ds_stats()->error);fclose(status);}
    unsigned frames=0;
    while(ok && aptMainLoop()) {
        hidScanInput();if(hidKeysDown()&KEY_START)break;
        if(!(surface?render3ds_begin_psx_frame(320,224):render3ds_begin_frame()))break;
        C3D_TexBind(0,NULL);
        for(unsigned panel=0;panel<(surface?1u:2u);panel++)for(int row=0;row<9;row++) {
            int y=20+row*20;
            const int a[3][2]={{8,y-6},{120,y-6},{8,y}};
            const int b[3][2]={{120,y-6},{120,y-3},{8,y}};
            const int c[3][2]={{8,y},{64,y-1},{8,y+7}};
            const int d[3][2]={{64,y-1},{64,y+7},{8,y+7}};
            const int e[3][2]={{64,y-1},{120,y-3},{64,y+7}};
            const int f[3][2]={{120,y-3},{120,y+7},{64,y+7}};
            if(surface)ok=surface_triangle(a)&&surface_triangle(b)&&surface_triangle(c)&&surface_triangle(d)&&surface_triangle(e)&&surface_triangle(f)&&ok;
            else ok=triangle(a,panel)&&triangle(b,panel)&&triangle(c,panel)&&triangle(d,panel)&&triangle(e,panel)&&triangle(f,panel)&&ok;
        }
        render3ds_end_frame();
        if(!frames++) {
            status=fopen("sdmc:/3ds/silenthill/stage5_raster_status.txt","ab");
            if(status){fprintf(status,"frame_ok=%u vertices=%lu rejected=%lu surface_bytes=%lu\n",ok,
                (unsigned long)render3ds_stats()->vertices_used,(unsigned long)render3ds_stats()->rejected_draws,
                (unsigned long)render3ds_psx_surface_bytes());fclose(status);}
        }
        gspWaitForVBlank();
    }
    render3ds_shutdown();gfxExit();return 0;
}
