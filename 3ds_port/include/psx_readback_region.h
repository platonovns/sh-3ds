#ifndef SH_PSX_READBACK_REGION_H
#define SH_PSX_READBACK_REGION_H
#include <stdint.h>
#include <stddef.h>
/* Exactly the R5 nearest RGB5/stencil resolve, factored by row/column. Crops
 * retain the full logical sample phase; scaling a rounded crop independently
 * would choose different pixels at 400 -> 320 and interlaced field ratios. */
typedef struct {unsigned x,y,width,height,logical_width,logical_height;
    unsigned crop_x,crop_y,crop_width,crop_height;} PsxResolveRegion;
static inline void psx_resolve_region(const uint32_t *color,const uint32_t *mask,
    unsigned physical_width,const PsxResolveRegion *r,uint16_t *out,unsigned stride)
{
    static const unsigned spread[8]={0,1,4,5,16,17,20,21};
    struct {uint16_t x,column;} columns[1024];
    for(unsigned i=0;i<r->crop_width;i++) {
        unsigned x=r->x+(r->crop_x+i)*r->width/r->logical_width;
        columns[i].x=x;columns[i].column=(x>>3)*64+spread[x&7];
    }
    for(unsigned j=0;j<r->crop_height;j++) {
        unsigned y=511-(r->y+(r->crop_y+j)*r->height/r->logical_height);
        unsigned row=(y>>3)*(physical_width>>3)*64+2*spread[y&7];
        const uint32_t *colors=color+y*physical_width;
        for(unsigned i=0;i<r->crop_width;i++) {
            uint32_t c=colors[columns[i].x],stencil=mask[row+columns[i].column];
            out[j*stride+i]=((c>>27)&31)|(((c>>19)&31)<<5)|(((c>>11)&31)<<10)|(stencil?0x8000:0);
        }
    }
}
#endif
