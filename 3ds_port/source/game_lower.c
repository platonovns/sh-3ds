/* Lower LCD presentation of original paper maps. No writes to game VRAM or saves. */
#include "game.h"
#include "game3ds.h"
#include "game_map_color.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/item_screens.h"
#include "bodyprog/items.h"
#include "bodyprog/player.h"
#include "bodyprog/events/bodyprog_data_800A99B4.h"
#include "bodyprog/math/math.h"
#include "main/fsqueue.h"
#include "psx_tim.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

extern s_800AEDBC D_800AEDBC[];
int g_PcMapQueryOnly;
int g_3dsMapQueryValid;
int g_3dsMapQueryX,g_3dsMapQueryZ;
q3_12 g_PcMapQueryAngle;

typedef struct { unsigned w,h; unsigned char *p; } LowerImage;
static LowerImage map_img,mark_img;
static uint16_t base[320*240], composite[320*240];
static int loaded=-1, mark_loaded=-2, idle;
extern unsigned game_text_style,game_lower_brightness,game_map_invert;
extern unsigned game_hp_indicator,game_ammo_display;
extern unsigned game_map_enabled;
static unsigned composite_brightness,composite_invert;
static unsigned char mark_bits[208];
static int marks_valid;
static int read_memory(void *ctx,uint32_t offset,void *out,uint32_t bytes)
{ memcpy(out,(const unsigned char*)ctx+offset,bytes);return 0; }
static void image_free(LowerImage *i) {free(i->p);memset(i,0,sizeof(*i));}
static int image_load(int file,LowerImage *out)
{
    void *raw=NULL;uint32_t bytes=0;
    int rc=stage4_fs_presentation_read(file,&raw,&bytes);
    if(rc) {game3ds_recoverable("map read",rc);return 0;}
    PsxSource src={read_memory,raw,bytes};PsxTim tim;PsxTextureRegion region;
    PsxVram *v=NULL;unsigned char *rgba=NULL;
    rc=psx_tim_parse(src,&tim);
    if(!rc && (tim.width>1024 || tim.height>512))rc=PV_BOUNDS;
    if(!rc) {v=calloc(1,sizeof(*v));if(!v)rc=PV_IO;}
    /* Original TIM headers put both blocks at (0,0); the modal loader
     * relocates them. Keep the private copy's palette off the image too. */
    PsxRect clut=tim.clut;
    if(!rc && tim.has_clut) {clut.x=0;clut.y=511;}
    if(!rc)rc=psx_tim_upload(v,src,&tim,NULL,tim.has_clut?&clut:NULL);
    if(!rc)rc=psx_tim_region(&tim,tim.image,clut,0,&region);
    if(!rc) {rgba=malloc((size_t)tim.width*tim.height*4);if(!rgba)rc=PV_IO;}
    if(!rc)rc=psx_vram_decode(v,region,rgba,(size_t)tim.width*tim.height*4);
    free(v);free(raw);
    if(rc) {free(rgba);game3ds_recoverable("map TIM",rc);return 0;}
    image_free(out);out->w=tim.width;out->h=tim.height;out->p=rgba;return 1;
}
static uint16_t rgb(unsigned r,unsigned g,unsigned b)
{return (uint16_t)(((r>>3)<<11)|((g>>2)<<5)|(b>>3));}
static uint16_t map_color(uint16_t p)
{
    unsigned v=game_lower_brightness;
    return (uint16_t)((((p>>11)*v/10)<<11)|((((p>>5)&63)*v/10)<<5)|((p&31)*v/10));
}
/* LCD is rotated in memory: x columns, each running from bottom to top. */
static void put(uint16_t *p,int x,int y,uint16_t color)
{if((unsigned)x<320 && (unsigned)y<240)p[x*240+239-y]=color;}
static void map_load(int idx)
{
    if(loaded==idx)return;
    if(Fs_QueueGetLength()>0) {idle=0;return;}
    if(++idle<2)return;
    idle=0;
    if(!image_load(FILE_TIM_MP_0TOWN_TIM+g_PaperMapFileIdxs[idx],&map_img))return;
    int m=g_PaperMapMarkingFileIdxs[idx];
    if(m!=mark_loaded) {
        image_free(&mark_img);mark_loaded=-2;
        if(m!=NO_VALUE && !image_load(FILE_TIM_MR_0TOWN_TIM+m,&mark_img))return;
        mark_loaded=m;
    }
    for(unsigned y=0;y<240;y++)for(unsigned x=0;x<320;x++) {
        const unsigned char *p=map_img.p+4*((y*map_img.h/240)*map_img.w+x*map_img.w/320);
        put(base,x,y,rgb(p[0],p[1],p[2]));
    }
    loaded=idx;marks_valid=0;
}
static int marks_changed(int idx)
{
    const s_800AEDBC *t=&D_800AEDBC[idx];unsigned char bits[sizeof(mark_bits)]={0};
    int n=(t->ptr_0 && t->ptr_4)?t->field_A-t->field_8:0;
    if(n<0 || n>(int)(sizeof(bits)*8))n=0;
    for(int i=0;i<n;i++)if(Savegame_EventFlagGet(t->field_8+i+1))bits[i/8]|=1u<<(i%8);
    if(marks_valid && !memcmp(bits,mark_bits,sizeof(bits)))return 0;
    memcpy(mark_bits,bits,sizeof(bits));marks_valid=1;return 1;
}
static void marks_build(int idx)
{
    memcpy(composite,base,sizeof(base));
    const s_800AEDBC *t=&D_800AEDBC[idx];
    if(mark_img.p && t->ptr_0 && t->ptr_4) {
        int n=(t->field_A-t->field_8)>>1;
        for(int i=0;i<n;i++) {
            s_800AE8A0_4 place=*(s_800AE8A0_4*)&t->ptr_4[i];
            for(int j=0;j<2;j++) {
                int s=j?place.field_3:place.field_2;
                if(!s || !Savegame_EventFlagGet(t->field_8+i*2+j+1))continue;
                s_800AE8A0_0 cell=*(s_800AE8A0_0*)&t->ptr_0[s];
                for(unsigned dy=0;dy<cell.field_3;dy+=2)for(unsigned dx=0;dx<cell.field_2;dx++) {
                    unsigned u=cell.field_0+dx,v=cell.field_1+dy;
                    int x=160+place.field_0*2+dx,y=120+place.field_1+dy/2;
                    if(u>=mark_img.w || v>=mark_img.h || (unsigned)x>=320 || (unsigned)y>=240)continue;
                    const unsigned char *q=mark_img.p+4*(v*mark_img.w+u);
                    if(!q[3])continue;
                    uint16_t *dst=&composite[x*240+239-y];unsigned p=*dst;
                    int r=(int)((p>>11)&31)-(q[0]>>3),g=(int)((p>>5)&63)-(q[1]>>2),b=(int)(p&31)-(q[2]>>3);
                    *dst=(uint16_t)(((r>0?r:0)<<11)|((g>0?g:0)<<5)|(b>0?b:0));
                }
            }
        }
    }
    game_map_convert(composite,320*240,game_lower_brightness,game_map_invert);
    composite_brightness=game_lower_brightness;composite_invert=game_map_invert;
}
static void line(uint16_t *p,int x0,int y0,int x1,int y1,uint16_t c)
{
    int dx=abs(x1-x0),sx=x0<x1?1:-1,dy=-abs(y1-y0),sy=y0<y1?1:-1,e=dx+dy;
    for(;;) {put(p,x0,y0,c);if(x0==x1 && y0==y1)break;int e2=2*e;if(e2>=dy){e+=dy;x0+=sx;}if(e2<=dx){e+=dx;y0+=sy;}}
}
static void marker(uint16_t *p)
{
    int x=160+g_3dsMapQueryX,y=120+g_3dsMapQueryZ;
    int a=Math_AngleNormalizeSigned(g_PcMapQueryAngle);
    int sn=Math_Sin(a),cs=Math_Cos(a);
    int x0=x+((sn*6)>>12),y0=y-((cs*6)>>12);
    int x1=x+((cs*4-sn*6)>>12),y1=y+((sn*4+cs*6)>>12);
    int x2=x+((-cs*4-sn*6)>>12),y2=y+((-sn*4+cs*6)>>12);
    uint16_t color=map_color(game_map_invert?(uint16_t)(0xf800u^0xffffu):0xf800);
    line(p,x0,y0,x1,y1,color);line(p,x1,y1,x2,y2,color);line(p,x2,y2,x0,y0,color);
}
static const unsigned char digits[11][5]={
 {7,5,5,5,7},{2,6,2,2,7},{7,1,7,4,7},{7,1,7,1,7},{5,5,7,1,1},
 {7,4,7,1,7},{7,4,7,5,7},{7,1,1,1,1},{7,5,7,5,7},{7,5,7,1,7},{1,1,2,4,4}};
static void text_pixel(uint16_t *p,int x,int y)
{
    if((unsigned)x>=320 || (unsigned)y>=240)return;
    if(game_text_style==3) {
        uint16_t v=p[x*240+239-y];
        put(p,x,y,(uint16_t)((((v>>11)*3/10)<<11)|((((v>>5)&63)*3/10)<<5)|((v&31)*3/10)));
    } else put(p,x,y,game_text_style==1?0:map_color(0xffff));
}
void Game3ds_LowerCounter(uint16_t *p,const char *text)
{
    static const unsigned glyphs[]={0x7b6f,0x2c97,0x73e7,0x73cf,0x5bc9,0x79cf,0x79ef,0x7249,0x7bef,0x7bcf};
    if(!p || !text)return;
    for(unsigned i=0;text[i] && i<30;i++) {
        char c=text[i];unsigned bits=0;
        if(c>='0' && c<='9')bits=glyphs[c-'0'];
        else switch(c) {case 'F':bits=0x79e4;break;case 'P':bits=0x7be4;break;
            case 'S':bits=0x79cf;break;case 'M':bits=0x5fed;break;
            case '.':bits=0x0002;break;case ':':bits=0x0410;break;}
        for(unsigned pass=0;pass<(game_text_style==2?2u:1u);pass++)
            for(unsigned y=0;y<5;y++)for(unsigned x=0;x<3;x++)if(bits&(1u<<(14-y*3-x)))
                for(unsigned sy=0;sy<2;sy++)for(unsigned sx=0;sx<2;sx++) {
                    int px=4+i*8+x*2+sx,py=4+y*2+sy;
                    if(game_text_style==2 && !pass)put(p,px+1,py+1,0);
                    else text_pixel(p,px,py);
                }
    }
}
static void hud(uint16_t *p)
{
    if(game_ammo_display==2)return;
    if (!Game3ds_CanPause() || g_Player_DisableControl ||
        g_SysWork.playerWork.player.model.charaId != Chara_Harry ||
        !g_WorldGfxWork.registeredCharaModels[Chara_Harry] ||
        g_SysWork.playerWork.player.health <= 0) return;
    if(game_hp_indicator==2) {
        int hp=g_SysWork.playerWork.player.health;
        unsigned color=map_color(hp<Q12(10.0f)?0xf800:hp<Q12(50.0f)?0xfd20:0x07e0);
        int weapon0=g_Inventory_EquippedItem;
        int gun0=INV_ITEM_GROUP(weapon0)==InvItemGroup_GunWeapons && weapon0!=InvItemId_HyperBlaster;
        char old[24];
        if(gun0)snprintf(old,sizeof(old),"%d/%d",g_SysWork.playerCombat.currentWeaponAmmo,g_SysWork.playerCombat.totalWeaponAmmo);
        else old[0]=0;
        int x0=315-(old[0]?(int)strlen(old)*7+3:0)-8;
        for(int y=4;y<12;y++)for(int i=0;i<8;i++)put(p,x0+i,y,(uint16_t)color);
    }
    int weapon=g_Inventory_EquippedItem;
    int gun=INV_ITEM_GROUP(weapon)==InvItemGroup_GunWeapons && weapon!=InvItemId_HyperBlaster;
    char text[24];
    int ammo=g_SysWork.playerCombat.currentWeaponAmmo,reserve=g_SysWork.playerCombat.totalWeaponAmmo;
    if (!gun) return;
    if(game_ammo_display==1)snprintf(text,sizeof(text),"%d/%d",ammo,reserve);
    else snprintf(text,sizeof(text),"%d",ammo);
    int len=(int)strlen(text),x=315-len*7;
    if(game_text_style==2)for(int i=0;i<len;i++) {int d=text[i]=='/'?10:text[i]-'0';if(d<0 || d>10)continue;
        for(int yy=0;yy<5;yy++)for(int xx=0;xx<3;xx++)if(digits[d][yy]&(4>>xx))
            for(int sy=-1;sy<=2;sy++)for(int sx=-1;sx<=2;sx++)put(p,x+i*7+xx*2+sx,3+yy*2+sy,0);
    }
    for(int i=0;i<len;i++) {int d=text[i]=='/'?10:text[i]-'0';if(d<0 || d>10)continue;
        for(int yy=0;yy<5;yy++)for(int xx=0;xx<3;xx++)if(digits[d][yy]&(4>>xx))
            for(int sy=0;sy<2;sy++)for(int sx=0;sx<2;sx++)text_pixel(p,x+i*7+xx*2+sx,3+yy*2+sy);
    }
}
int Game3ds_LowerDraw(uint16_t *pixels)
{
    if(!pixels)return 0;
    if(!game_map_enabled) {memset(pixels,0,sizeof(base));hud(pixels);return 1;}
    int idx=g_SavegamePtr->paperMapIdx;
    int owned=idx>0 && idx<24 && HAS_MAP(idx);
    if(owned)map_load(idx);else {idle=0;}
    if(owned && loaded==idx) {
        if(marks_changed(idx) || (composite_brightness!=game_lower_brightness || composite_invert!=game_map_invert))marks_build(idx);
        memcpy(pixels,composite,sizeof(composite));
        g_PcMapQueryOnly=1;g_PcMapQueryAngle=g_SysWork.playerWork.player.rotation.vy;
        func_80067914(idx,0,0,Q12(1.0f));g_PcMapQueryOnly=0;
        if(g_3dsMapQueryValid)marker(pixels);
    } else if(owned && loaded>=0) {
        if((composite_brightness!=game_lower_brightness || composite_invert!=game_map_invert))marks_build(loaded);
        memcpy(pixels,composite,sizeof(composite));
    }
    else memset(pixels,0,sizeof(base));
    hud(pixels);return 1;
}
