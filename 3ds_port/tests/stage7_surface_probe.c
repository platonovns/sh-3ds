#include <3ds.h>
#include <stdio.h>
#include "render_3ds.h"
uint64_t game3ds_ticks(void) {return svcGetSystemTick();}
static bool quad(float x,float y,float r,float g,float b)
{
    Render3dsVertex v[6]={
        {x,y,0,0,0,r,g,b,1},{x+24,y,0,0,0,r,g,b,1},{x,y+24,0,0,0,r,g,b,1},
        {x+24,y,0,0,0,r,g,b,1},{x+24,y+24,0,0,0,r,g,b,1},{x,y+24,0,0,0,r,g,b,1}};
    return render3ds_draw_psx_triangles(v,6,NULL,0);
}
static bool page(unsigned display,unsigned height)
{
    if(!render3ds_set_display(display))return false;
    if(!render3ds_begin_psx_frame(display?320:400,height))return false;
    render3ds_set_psx_mask(0);bool ok=quad(16.5f,16.5f,1,0,0);
    render3ds_set_psx_mask(1);ok=quad(56.5f,16.5f,0,1,0)&&ok;
    render3ds_set_psx_mask(0);ok=quad(96.5f,16.5f,0,0,1)&&ok;
    render3ds_end_frame();
    render3ds_continue_psx_frame(true);
    ok=render3ds_begin_psx_frame(display?320:400,height)&&ok;
    /* Lower field on interlaced pages: catch accidental 240-row clipping. */
    render3ds_set_psx_mask(0);ok=quad(136.5f,height-40+.5f,1,1,0)&&ok;
    render3ds_end_frame();
    uint16_t red[4],green[4],blue[4],yellow[4];
    ok=render3ds_read_psx(20,20,2,2,red,2)&&ok;
    ok=render3ds_read_psx(60,20,2,2,green,2)&&ok;
    ok=render3ds_read_psx(100,20,2,2,blue,2)&&ok;
    ok=render3ds_read_psx(140,height-36,2,2,yellow,2)&&ok;
    for(unsigned i=0;i<4;i++)ok=ok && red[i]==0x001f && green[i]==0x83e0 && blue[i]==0x7c00 && yellow[i]==0x03ff;
    FILE *f=fopen("sdmc:/3ds/silenthill/stage7_surface_probe.txt",display?"ab":"wb");
    if(f){fprintf(f,"display=%u source=%ux%u physical=%ux240 format=%u red=%04x green=%04x blue=%04x yellow=%04x result=%s\n",display,display?320:400,height,display?320:400,
        (unsigned)gfxGetScreenFormat(display?GFX_BOTTOM:GFX_TOP),red[0],green[0],blue[0],yellow[0],ok?"PASS":"FAIL");fclose(f);}
    return ok;
}
int main(void)
{
    gfxInitDefault();consoleInit(GFX_BOTTOM,NULL);
    bool ok=render3ds_init();if(ok)ok=page(0,240);
    if(ok)ok=page(1,448);
    /* Bottom is now owned by the GPU. Evidence is in the SD report. */
    while(aptMainLoop()) {hidScanInput();if(hidKeysDown()&KEY_START)break;gspWaitForVBlank();}
    render3ds_shutdown();gfxExit();return ok?0:1;
}
