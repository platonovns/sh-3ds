/* Emulator diagnostic only: fine spatial pattern, real PICA render/readback,
 * PS1 quantization and repeated feedback. No game state or memory card writes. */
#include <3ds.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "render_3ds.h"
#include "game_feedback.h"
#include "psx_game_pixel.h"
uint64_t game3ds_ticks(void) {return svcGetSystemTick();}
static uint16_t *pixels;
static unsigned modulation=128;
static uint16_t pattern(unsigned x,unsigned y)
{return ((x*7+y*13)%31+1)|(((x/3+y*5)%31+1)<<5)|(((x+y/5)%31+1)<<10);}
static bool row(void *unused,unsigned y,uint8_t *rgba,unsigned width)
{
    (void)unused;
    memset(rgba,0,width*4);
    if(y<240)for(unsigned x=0;x<400;x++) {
        uint16_t w=game_feedback_modulate(pixels[y*400+x],modulation,modulation,modulation);
        psx_game_pixel(w,rgba+x*4);
    }
    return true;
}
int main(void)
{
    gfxInitDefault();consoleInit(GFX_BOTTOM,NULL);
    bool ok=render3ds_init();unsigned passes=0,bad=0,first_x=0,first_y=0,actual=0,expected=0;
    pixels=malloc(400*240*2);
    if(!pixels)ok=false;
    if(ok)for(unsigned y=0;y<240;y++)for(unsigned x=0;x<400;x++)pixels[y*400+x]=pattern(x,y);
    Render3dsTexture *texture=ok?render3ds_texture_create_rows(512,256,row,NULL,NULL,NULL):NULL;
    if(!texture)ok=false;
    else render3ds_texture_psx_coverage(texture,1);
    const float u=400/512.0f,v=1-240/256.0f;
    const Render3dsVertex quad[6]={
        {0,0,0,0,1,1,1,1,1},{400,0,0,u,1,1,1,1,1},{0,240,0,0,v,1,1,1,1},
        {400,0,0,u,1,1,1,1,1},{400,240,0,u,v,1,1,1,1},{0,240,0,0,v,1,1,1,1}};
    for(unsigned pass=0;ok && pass<32;pass++) {
        if(pass) {modulation=127;ok=render3ds_texture_update_rows(texture,row,NULL);}
        ok=ok && render3ds_begin_psx_frame(400,240);
        ok=ok && render3ds_draw_psx_triangles(quad,6,texture,0);
        render3ds_end_frame();
        ok=ok && render3ds_read_psx(0,0,400,240,pixels,400);
        if(ok)for(unsigned y=0;y<240;y++)for(unsigned x=0;x<400;x++) {
            uint16_t want=pattern(x,y);
            for(unsigned n=0;n<pass;n++)want=game_feedback_modulate(want,127,127,127);
            if((pixels[y*400+x]&32767)!=want) {
                if(!bad) {first_x=x;first_y=y;actual=pixels[y*400+x];expected=want;}
                bad++;
            }
        }
        passes++;
        if(bad)ok=false;
    }
    FILE *out=fopen("sdmc:/3ds/silenthill/stage10_feedback_surface_probe.txt","wb");
    if(out) {fprintf(out,"result=%s\npasses=%u\nbad_samples=%u\nfirst=%u,%u,%04x,%04x\n",ok?"PASS":"FAIL",passes,bad,first_x,first_y,actual,expected);fclose(out);}
    free(pixels);render3ds_shutdown();gfxExit();return ok?0:1;
}
