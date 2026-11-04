/* Missing PsyQ helpers with real arithmetic/register effects, never no-ops. */
#include "game.h"
#include "gpu_gte_pc.h"
#include <limits.h>

MATRIX *TransposeMatrix(MATRIX *in,MATRIX *out)
{
    MATRIX copy=*in;
    for(unsigned row=0;row<3;row++)
        for(unsigned col=0;col<3;col++) out->m[row][col]=copy.m[col][row];
    return out;
}
VECTOR *Square0(VECTOR *in,VECTOR *out)
{
    int32_t x=(uint32_t)in->vx*in->vx, y=(uint32_t)in->vy*in->vy, z=(uint32_t)in->vz*in->vz;
    out->vx=x;out->vy=y;out->vz=z;
    return out;
}

void ReadLightMatrix(MATRIX *m)
{
    for (unsigned i=0;i<9;i++) {
        uint32_t r=CFC2(8+i/2);
        m->m[i/3][i%3]=(int16_t)(r>>((i&1)*16));
    }
}
long Lzc(long value)
{
    uint32_t v=(uint32_t)value;
    if ((int32_t)v<0) v=~v;
    return v ? __builtin_clz(v) : 32;
}
void LoadAverageCol(const unsigned char *a,const unsigned char *b,long wa,long wb,unsigned char *out)
{
    for(unsigned i=0;i<3;i++) {
        int32_t v=((int32_t)a[i]*wa+(int32_t)b[i]*wb)>>12;
        out[i]=CLAMP(v,0,255);
    }
}
void OuterProduct12(VECTOR *a,VECTOR *b,VECTOR *out)
{
    int32_t x=((int64_t)a->vy*b->vz-(int64_t)a->vz*b->vy)>>12;
    int32_t y=((int64_t)a->vz*b->vx-(int64_t)a->vx*b->vz)>>12;
    int32_t z=((int64_t)a->vx*b->vy-(int64_t)a->vy*b->vx)>>12;
    out->vx=x;out->vy=y;out->vz=z;
}
long VectorNormal(const VECTOR *a,VECTOR *out)
{
    uint32_t square=(uint32_t)((int64_t)a->vx*a->vx+(int64_t)a->vy*a->vy+(int64_t)a->vz*a->vz);
    uint32_t magnitude=SquareRoot0(square);
    int32_t x=magnitude ? (int64_t)a->vx*4096/magnitude : 0;
    int32_t y=magnitude ? (int64_t)a->vy*4096/magnitude : 0;
    int32_t z=magnitude ? (int64_t)a->vz*4096/magnitude : 0;
    out->vx=x;out->vy=y;out->vz=z;out->pad=0;
    return square;
}
