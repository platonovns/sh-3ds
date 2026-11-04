#include <3ds.h>
#include <stdio.h>
#include "render_3ds.h"
uint64_t game3ds_ticks(void) {return svcGetSystemTick();}
static bool fill(float x,float y,float w,float h,float r,float g,float b)
{
    Render3dsVertex v[6]={
        {x,y,0,0,0,r,g,b,1},{x+w,y,0,0,0,r,g,b,1},{x,y+h,0,0,0,r,g,b,1},
        {x+w,y,0,0,0,r,g,b,1},{x+w,y+h,0,0,0,r,g,b,1},{x,y+h,0,0,0,r,g,b,1}};
    return render3ds_draw_psx_triangles(v,6,NULL,0);
}
int main(void)
{
    gfxInitDefault();consoleInit(GFX_BOTTOM,NULL);
    bool ok=render3ds_init();unsigned bad_edges=0,bad_samples=0,old_left=0,old_bands=0;
    if(ok)ok=render3ds_set_display(0) && render3ds_begin_psx_frame(400,240);
    if(ok) {
        /* Exact Stage 7 GsSortClear vertices after width-only expansion. */
        render3ds_set_psx_mask(0);ok=fill(.5f,8.5f,400,224,0,0,0);
        render3ds_end_frame();
        uint16_t row[400];
        for(unsigned y=0;y<240;y++) {
            ok=render3ds_read_psx(0,y,400,1,row,400)&&ok;
            if(row[0])old_left++;
            for(unsigned x=1;x<400;x++)if(row[x])old_bands++;
        }
        ok=render3ds_begin_psx_frame(400,240)&&ok;
        ok=fill(0,0,400,240,0,0,0)&&ok;render3ds_end_frame();
        for(unsigned y=0;y<240;y++) {
            ok=render3ds_read_psx(0,y,400,1,row,400)&&ok;
            for(unsigned x=0;x<400;x++)if(row[x])bad_edges++;
        }
        ok=render3ds_begin_psx_frame(400,240)&&ok;
        ok=fill(0,0,200,120,1,0,0)&&ok;
        ok=fill(200,0,200,120,0,1,0)&&ok;
        ok=fill(0,120,200,120,0,0,1)&&ok;
        ok=fill(200,120,200,120,1,1,1)&&ok;
        render3ds_end_frame();
        for(unsigned y=0;y<224;y++) {
            ok=render3ds_resolve_psx(0,y*240/224,400,1,320,1,row,400)&&ok;
            for(unsigned x=0;x<320;x++) {
                uint16_t expected=y<112?(x<160?0x001f:0x03e0):(x<160?0x7c00:0x7fff);
                if(row[x]!=expected)bad_samples++;
            }
        }
    }
    ok=ok && !bad_edges && !bad_samples;
    FILE *f=fopen("sdmc:/3ds/silenthill/stage8_surface_probe.txt","wb");
    if(f){fprintf(f,"stage7_geometry_uncleared_left_rows=%u\nstage7_geometry_uncleared_band_pixels=%u\nblack_400x240_bad_pixels=%u\nresolve_400_to_320_bad_samples=%u\nresult=%s\n",old_left,old_bands,bad_edges,bad_samples,ok?"PASS":"FAIL");fclose(f);}
    while(aptMainLoop()){hidScanInput();if(hidKeysDown()&KEY_START)break;gspWaitForVBlank();}
    render3ds_shutdown();gfxExit();return ok?0:1;
}
