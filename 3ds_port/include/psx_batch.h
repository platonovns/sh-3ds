#ifndef SH_PSX_BATCH_H
#define SH_PSX_BATCH_H
#include "render_3ds.h"
typedef struct { float x0,y0,x1,y1; } PsxBatchBounds;
static inline PsxBatchBounds psx_batch_bounds(const Render3dsVertex *v,unsigned n)
{
    PsxBatchBounds b={v->x,v->y,v->x,v->y};
    for(unsigned i=1;i<n;i++) {
        if(v[i].x<b.x0)b.x0=v[i].x;
        if(v[i].x>b.x1)b.x1=v[i].x;
        if(v[i].y<b.y0)b.y0=v[i].y;
        if(v[i].y>b.y1)b.y1=v[i].y;
    }
    return b;
}
static inline int psx_batch_disjoint(PsxBatchBounds a,PsxBatchBounds b)
{ return a.x1<=b.x0 || b.x1<=a.x0 || a.y1<=b.y0 || b.y1<=a.y0; }
static inline PsxBatchBounds psx_batch_union(PsxBatchBounds a,PsxBatchBounds b)
{
    if(b.x0<a.x0)a.x0=b.x0;
    if(b.y0<a.y0)a.y0=b.y0;
    if(b.x1>a.x1)a.x1=b.x1;
    if(b.y1>a.y1)a.y1=b.y1;
    return a;
}
static inline float psx_cross(const Render3dsVertex *a,const Render3dsVertex *b,const Render3dsVertex *p)
{ return (b->x-a->x)*(p->y-a->y)-(b->y-a->y)*(p->x-a->x); }
/* Strict interior overlap; shared edges are disjoint under the raster top-left rule. */
static inline int psx_triangles_overlap(const Render3dsVertex *a,const Render3dsVertex *b)
{
    if(!psx_cross(a,a+1,a+2) || !psx_cross(b,b+1,b+2))return 0;
    if(psx_batch_disjoint(psx_batch_bounds(a,3),psx_batch_bounds(b,3)))return 0;
    for(unsigned shape=0;shape<2;shape++) {
        const Render3dsVertex *t=shape?b:a,*other=shape?a:b;
        for(unsigned i=0;i<3;i++) {
            const Render3dsVertex *p=t+i,*q=t+(i+1)%3;
            float inside=psx_cross(p,q,t+(i+2)%3);
            float x=psx_cross(p,q,other),y=psx_cross(p,q,other+1),z=psx_cross(p,q,other+2);
            if((inside>0 && x<=0 && y<=0 && z<=0)||(inside<0 && x>=0 && y>=0 && z>=0))return 0;
        }
    }
    return 1;
}
#endif
