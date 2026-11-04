/* Independent R5 per-pixel oracle versus the factored crop-preserving kernel. */
#include "psx_readback_region.h"
#include "texture_layout.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t random_word(void) {static uint32_t s=0x91026;s^=s<<13;s^=s>>17;s^=s<<5;return s;}
int main(void)
{
    uint32_t *color=malloc(1024*512*4),*mask=malloc(1024*512*4);
    uint16_t *reference=malloc(1024*512*2),*actual=malloc(1024*512*2);
    assert(color&&mask&&reference&&actual);
    for(unsigned i=0;i<1024*512;i++){color[i]=random_word();mask[i]=(random_word()%7==0)?random_word():0;}
    const unsigned sizes[][6]={{0,0,400,240,320,224},{0,0,384,448,384,448},
        {0,0,640,480,320,240},{0,0,320,240,320,240},{17,9,301,211,337,227},
        {0,0,1024,512,1024,512},{0,16,400,224,320,224}};
    unsigned cases=0;
    for(unsigned w=512;w<=1024;w*=2)for(unsigned s=0;s<sizeof(sizes)/sizeof(sizes[0]);s++) {
        const unsigned *v=sizes[s];if(v[0]+v[2]>w)continue;
        for(unsigned y=0;y<v[5];y++)for(unsigned x=0;x<v[4];x++) {
            unsigned sx=v[0]+x*v[2]/v[4],sy=v[1]+y*v[3]/v[5];
            uint32_t c=color[(511-sy)*w+sx],m=mask[texture3ds_offset(w,512,sx,511-sy)/4];
            reference[y*1024+x]=((c>>27)&31)|(((c>>19)&31)<<5)|(((c>>11)&31)<<10)|(m?0x8000:0);
        }
        for(unsigned k=0;k<150;k++) {
            PsxResolveRegion r={v[0],v[1],v[2],v[3],v[4],v[5],0,0,v[4],v[5]};
            if(k) {
                r.crop_x=random_word()%v[4];r.crop_y=random_word()%v[5];
                r.crop_width=1+random_word()%(v[4]-r.crop_x);r.crop_height=1+random_word()%(v[5]-r.crop_y);
            }
            memset(actual,0xa5,1024*512*2);psx_resolve_region(color,mask,w,&r,actual,1024);
            for(unsigned y=0;y<512;y++)for(unsigned x=0;x<1024;x++) {
                uint16_t wanted=x<r.crop_width&&y<r.crop_height?reference[(y+r.crop_y)*1024+x+r.crop_x]:0xa5a5;
                assert(actual[y*1024+x]==wanted);
            }
            cases++;
        }
    }
    free(color);free(mask);free(reference);free(actual);
    printf("PASS: %u full/cropped resolves, all RGB5/stencil pixels and untouched guards exact to R5\n",cases);
}
