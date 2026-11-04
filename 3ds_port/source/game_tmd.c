/* Native ARM TMD linkage and the existing PC packet producers. No model cache,
 * no linear allocations: original FS buffers own model lifetime. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "psx_memory.h"
#include <psyq/libgs.h>
#include <string.h>
extern _GsFCALL GsFCALL4;
static int light_mode;
static GsF_LIGHT lights[3];
static int ram_span(const void *ptr,unsigned bytes)
{
    uintptr_t a=(uintptr_t)ptr,base=(uintptr_t)g_PsxRam;
    return a>=base && a-base<=PSX_RAM_SIZE && bytes<=PSX_RAM_SIZE-(a-base);
}
static void game_tmd_packet_check(unsigned bytes)
{
    unsigned capacity;uintptr_t base,a=(uintptr_t)GsOUT_PACKET_P;
    Game3ds_PacketBounds(&base,&capacity);
    if(a<base || a-base>capacity || bytes>capacity-(a-base))game3ds_halt(443,"TMD packet arena bounds",bytes);
}
#include "../build-game/tmd_emit.inc"

void GsMapModelingData(unsigned long *header)
{
    _Static_assert(sizeof(TMD_STRUCT)==28,"ARM TMD table must match PSX disk layout");
    if(!ram_span(header,8) || header[1]>64 || !header[1])game3ds_halt(443,"TMD object count",0);
    TMD_STRUCT *objects=(TMD_STRUCT*)(header+2);
    if(!ram_span(objects,header[1]*sizeof(*objects)))game3ds_halt(443,"TMD table bounds",header[1]);
    if(header[0]&1)return;
    if(header[0])game3ds_halt(443,"TMD flags",header[0]);
    for(unsigned i=0;i<header[1];i++) {
        TMD_STRUCT *t=&objects[i];uintptr_t base=(uintptr_t)objects;
        if(t->vern>8192 || t->norn>8192 || t->primn>8192 ||
            !ram_span((void*)(base+(uintptr_t)t->vertop),t->vern*8) ||
            !ram_span((void*)(base+(uintptr_t)t->nortop),t->norn*8) ||
            !ram_span((void*)(base+(uintptr_t)t->primtop),t->primn*4))game3ds_halt(443,"TMD data bounds",i);
        t->vertop=(void*)(base+(uintptr_t)t->vertop);t->nortop=(void*)(base+(uintptr_t)t->nortop);t->primtop=(void*)(base+(uintptr_t)t->primtop);
    }
    header[0]=1;
}
struct TMD_STRUCT *GsGetTMDObject(unsigned long *header,int index)
{return header && index>=0 && (unsigned)index<header[1]?(TMD_STRUCT*)(header+2)+index:NULL;}
void GsLinkObject4(unsigned long address,GsDOBJ2 *obj,int index)
{
    if(!obj || index<0 || !ram_span((TMD_STRUCT*)address+index,sizeof(TMD_STRUCT)))game3ds_halt(443,"TMD link bounds",index);
    obj->tmd=(void*)((TMD_STRUCT*)address+index);
}
void GsLinkObject4_PC(struct TMD_STRUCT *tmd,GsDOBJ2 *obj) {obj->tmd=(void*)tmd;}
void GsSetLightMatrix(MATRIX *m)
{
    MATRIX directions={0},colors={0},combined;
    for(unsigned i=0;i<3;i++) {
        VECTOR v={lights[i].vx,lights[i].vy,lights[i].vz,0},normal;
        VectorNormal(&v,&normal);
        directions.m[i][0]=normal.vx;directions.m[i][1]=normal.vy;directions.m[i][2]=normal.vz;
        colors.m[0][i]=lights[i].r<<4;colors.m[1][i]=lights[i].g<<4;colors.m[2][i]=lights[i].b<<4;
    }
    MulMatrix0(&directions,m,&combined);SetLightMatrix(&combined);SetColorMatrix(&colors);
}
void GsSetAmbient(long r,long g,long b) {SetBackColor(r>>4,g>>4,b>>4);}
void GsSetFlatLight(int id,GsF_LIGHT *light)
{
    if(id<0 || id>=3 || !light)game3ds_halt(443,"GS light bounds",id);
    lights[id]=*light;
}
void GsSetLightMode(int mode) {light_mode=mode;}
void GsSetProjection(long h) {SetGeomScreen(h);}
void GsSortOt(GsOT *src,GsOT *dst)
{
    if(!src || !dst || !src->tag || !src->org || !dst->org)game3ds_halt(443,"GS sub-OT",0);
    setaddr(&src->org[0],getaddr(&dst->org[0]));setaddr(&dst->org[0],src->tag);
}
void GsSortObject4J(GsDOBJ2 *obj,GsOT *ot,int shift,unsigned long *scratch)
{
    if(!obj || !obj->tmd)return;
    TMD_STRUCT *t=(TMD_STRUCT*)obj->tmd;
    if(!ram_span(t,sizeof(*t)) || !ram_span(t->vertop,t->vern*8) || !ram_span(t->nortop,t->norn*8) || t->primn>8192 || shift<0 || shift>15 || !ot || ot->length>11)
        game3ds_halt(443,"TMD render bounds",0);
    SetDQA(1024);SetDQB(1988608);
    u8 *p=(u8*)t->primtop;
    for(unsigned i=0;i<t->primn;i++) {
        if(!ram_span(p,4) || !p[1] || p[1]>15 || !ram_span(p,4u*(p[1]+1)))game3ds_halt(443,"TMD primitive extent",i);
        unsigned mode=p[3]&0xfc,lit=p[2]&1;
        if((mode&0xe0)!=0x20)game3ds_halt(443,"TMD primitive mode",p[3]);
        /* Validate every u16 index consumed by the reused producers. SH's
         * no-light G3/TG3 uses normal/vertex pairs (ilen=4/6 respectively). */
        unsigned n=(mode&8)?4:3,tex=(mode&4)!=0,gouraud=(mode&16)!=0;
        unsigned pair=lit && gouraud;
        unsigned start=tex?(n==4?20:16):8;
        if(!lit && tex && gouraud && n==3)pair=1;
        if(!lit && !tex && gouraud && n==3 && p[1]==4)pair=1;
        if(!lit && !pair)start+=gouraud?4*(n-1):(tex?4:0);
        if(lit && !gouraud)start+=2;
        unsigned stride=pair?4:2;
        unsigned required=start+(n-1)*stride+2;
        if(required>4u*(p[1]+1))game3ds_halt(443,"TMD index layout",(mode<<16)|p[1]);
        for(unsigned v=0;v<n;v++) {
            unsigned offset=start+v*stride+(pair?2:0);
            if(offset+2>4u*(p[1]+1))game3ds_halt(443,"TMD index extent",offset);
            unsigned idx=p[offset]|p[offset+1]<<8;
            if(idx>=t->vern)game3ds_halt(443,"TMD vertex index",idx);
            if(lit && (pair || !v)) {unsigned no=pair?start+v*4:start-2;unsigned ni=p[no]|p[no+1]<<8;if(ni>=t->norn)game3ds_halt(443,"TMD normal index",ni);}
        }
        typedef void (*Lit)(void*,VERT*,VERT*,PACKET*,int,int,GsOT*,u_long*);
        typedef void (*Unlit)(void*,VERT*,PACKET*,int,int,GsOT*,u_long*);
        static const Lit ls[8]={GsTMDfastF3LFG,GsTMDfastTF3LFG,GsTMDfastF4LFG,GsTMDfastTF4LFG,GsTMDfastG3LFG,GsTMDfastTG3LFG,GsTMDfastG4LFG,GsTMDfastTG4LFG};
        static const Unlit us[8]={GsTMDfastNF3,GsTMDfastNTF3,GsTMDfastNF4,GsTMDfastNTF4,GsTMDfastNG3,GsTMDfastNTG3,GsTMDfastNG4,GsTMDfastNTG4};
        unsigned kind=(mode>>2)&7;
        if(lit)ls[kind](p,(VERT*)t->vertop,(VERT*)t->nortop,GsOUT_PACKET_P,1,shift,ot,scratch);
        else us[kind](p,(VERT*)t->vertop,GsOUT_PACKET_P,1,shift,ot,scratch);
        p+=4u*(p[1]+1);
    }
    (void)light_mode;
}
