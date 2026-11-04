/* Synthetic data only: real PICA transparent/STP/ABR conformance grid. */
#include <3ds.h>
#include <stdio.h>
#include "render_3ds.h"
#include "psx_game_pixel.h"
static bool precision;
static bool order_page;
static bool surface_page;
static bool pixel_report_written;
uint64_t game3ds_ticks(void) { return svcGetSystemTick(); }
static bool row(void *context,unsigned y,uint8_t *rgba,unsigned width)
{
    (void)context;(void)y;
    const uint16_t regular[]={0x0000,0x8000,0x001f,0x83e0};
    const uint16_t stressed[]={0x0000,0x8000,0x83e0,0x801f};
    const uint16_t ordered[]={0x0000,0x8000,0x4210,0xffff};
    for(unsigned x=0;x<width;x++) {
        unsigned column=x/64;psx_game_pixel((order_page?ordered:precision?stressed:regular)[column],rgba+4*x);
        if(precision && column)rgba[4*x+3]=126+column;
    }
    return true;
}
static bool quad(float x,float y,float width,float height,float u0,float u1,
                 float r,float g,float b,Render3dsTexture *texture,unsigned blend)
{
    float alpha=blend==1?0.5f:blend==4?0.25f:1.0f;
    if(surface_page){x+=.5f;y+=.5f;}
    Render3dsVertex v[6]={
        {x,y,0,u0,1,r,g,b,alpha},{x+width,y,0,u1,1,r,g,b,alpha},{x,y+height,0,u0,0,r,g,b,alpha},
        {x+width,y,0,u1,1,r,g,b,alpha},{x+width,y+height,0,u1,0,r,g,b,alpha},{x,y+height,0,u0,0,r,g,b,alpha}};
    return render3ds_draw_psx_triangles(v,6,texture,blend);
}
static bool report_pixels(bool mask_page)
{
    const char *kind=order_page?"order":mask_page?"mask":precision?"precision":"regular";
    char path[128];snprintf(path,sizeof(path),"sdmc:/3ds/silenthill/stage7-pixel-%s.txt",kind);
    FILE *f=fopen(path,"wb");if(!f)return false;
    bool ok=true;fprintf(f,"kind=%s\n",kind);
    unsigned rows=mask_page?1:5,columns=order_page?1:4;
    for(unsigned r=0;r<rows;r++)for(unsigned c=0;c<columns;c++) {
        unsigned x=order_page?190:mask_page?80+c*80:52+c*96;
        unsigned y=mask_page?120:27+r*46;uint16_t word=0;
        bool read=render3ds_read_psx(x,y,1,1,&word,1);ok=ok&&read;
        fprintf(f,"sample=%u,%u,%04x\n",r,c,word);
    }
    fprintf(f,"readback=%s\n",ok?"PASS":"FAIL");fclose(f);return ok;
}
int main(void)
{
    gfxInitDefault(); consoleInit(GFX_BOTTOM,NULL);
    FILE *surface=fopen("sdmc:/3ds/silenthill/stage5_probe_surface.txt","rb");surface_page=surface!=NULL;
    if(surface){fclose(surface);remove("sdmc:/3ds/silenthill/stage5_probe_surface.txt");}
    FILE *stress=fopen("sdmc:/3ds/silenthill/stage5_probe_precision.txt","rb");
    precision=stress!=NULL;
    if(stress) {fclose(stress);remove("sdmc:/3ds/silenthill/stage5_probe_precision.txt");}
    FILE *order=fopen("sdmc:/3ds/silenthill/stage5_probe_order.txt","rb");order_page=order!=NULL;
    if(order){fclose(order);remove("sdmc:/3ds/silenthill/stage5_probe_order.txt");}
    bool ok=render3ds_init();
    Render3dsTexture *texture=ok?render3ds_texture_create_rows(256,8,row,NULL,NULL,NULL):NULL;
    printf("PSX pixel semantics probe\nColumns: 0000 / 8000 / 001F / 83E0\nRows: opaque, ABR 0,1,2,3\nBlue background: (64,128,192)\nA: mask test page / START exits\n");
    FILE *fixture=fopen("sdmc:/3ds/silenthill/stage5_probe_mask.txt","rb");
    bool mask_page=fixture!=NULL;
    if(fixture) { fclose(fixture); remove("sdmc:/3ds/silenthill/stage5_probe_mask.txt"); }
    while (aptMainLoop()) {
        hidScanInput(); if(hidKeysDown()&KEY_START) break;
        if(hidKeysDown()&KEY_A) mask_page=!mask_page;
        if(!texture || !(surface_page?render3ds_begin_psx_frame(400,240):render3ds_begin_frame())) break;
        render3ds_set_psx_mask(mask_page?1:0);
        ok=quad(0,0,400,240,0,0,64/255.0f,128/255.0f,192/255.0f,NULL,0);
        render3ds_set_psx_mask(0);
        if(order_page) {
            for(unsigned mode=0;mode<5;mode++) {
                Render3dsVertex vertices[12];
                for(unsigned q=0;q<2;q++) {
                    float x=(q?160:40)+(surface_page?.5f:0),y=8+mode*46+(surface_page?.5f:0),u=q?.625f:.875f;
                    const Render3dsVertex v[6]={
                        {x,y,0,u,1,1,1,1,1},{x+180,y,0,u,1,1,1,1,1},{x,y+38,0,u,0,1,1,1,1},
                        {x+180,y,0,u,1,1,1,1,1},{x+180,y+38,0,u,0,1,1,1,1},{x,y+38,0,u,0,1,1,1,1}};
                    memcpy(vertices+q*6,v,sizeof(v));
                }
                const uint16_t sizes[2]={6,6};
                ok=render3ds_draw_psx_ordered(vertices,12,sizes,2,texture,mode)&&ok;
            }
        } else if(!mask_page) {
            for(unsigned mode=0;mode<5;mode++) for(unsigned column=0;column<4;column++)
                ok=quad(8+column*96,8+mode*46,88,38,column/4.0f,(column+1)/4.0f,1,1,1,texture,mode)&&ok;
        } else {
            ok=quad(40,60,320,120,0,1,1,1,1,texture,0)&&ok;
            render3ds_set_psx_mask(3);
            ok=quad(40,60,320,120,0,0,64/255.0f,64/255.0f,64/255.0f,NULL,2)&&ok;
            /* Everything is now masked; this subsequent pass must do nothing. */
            ok=quad(40,60,320,120,0,0,0,1,0,NULL,2)&&ok;
        }
        render3ds_end_frame();
        if(surface_page && !pixel_report_written){ok=report_pixels(mask_page)&&ok;pixel_report_written=true;}
        if(!ok)break;
        gspWaitForVBlank();
    }
    render3ds_shutdown(); gfxExit(); return 0;
}
