/* Host CPU-time comparison; never evidence of New 3DS performance. */
#include "fmv_stream.h"
#include "fmv_mdec.h"
#include <assert.h>
#include <stdlib.h>
#include <time.h>
FILE *g_ShDebugLog;
void oracle_init(mdec_ctx_t *,int,int);
int oracle_decode(mdec_ctx_t *,const uint8_t *,size_t,uint8_t *);
int main(int argc,char **argv)
{
    assert(argc==3);PsxDisc d;ShDisc sh;
    assert(!PsxDisc_Open(&d,argv[1],argv[2]) && !ShDisc_Init(&sh,&d));
    FmvStream *s=malloc(sizeof(*s));uint8_t *rgb=malloc(FMV_RGB_BYTES);assert(s && rgb);
    const unsigned ids[]={2053,2056,2061,2067,2073},lengths[]={2067,119,150,378,1424};
    for(unsigned i=0;i<5;i++)for(unsigned j=0;j<3;j++) {
        uint32_t wanted=j==0?1:j==1?lengths[i]/2:lengths[i];FmvEntry e;
        assert(!fmv_entry(&sh,ids[i],lengths[i],&e));fmv_stream_init(s,&d,&e);
        s->frame=wanted-1;s->cursor=(wanted-1)*10u;
        uint32_t no,bytes;assert(fmv_next_frame(s,NULL,NULL,&no,&bytes)==1 && no==wanted);
        mdec_ctx_t a,b;mdec_init(&a,320,208);oracle_init(&b,320,208);
        double ms[2];
        for(unsigned mode=0;mode<2;mode++) {
            clock_t start=clock();
            for(unsigned repeat=0;repeat<20;repeat++)
                assert((mode?oracle_decode(&b,s->bits,bytes,rgb):mdec_decode_frame(&a,s->bits,bytes,rgb))==260);
            ms[mode]=(double)(clock()-start)*1000/CLOCKS_PER_SEC/20;
        }
        printf("%s frame=%u repeats=20 native_ms=%.6f pc_ms=%.6f native_fps=%.2f speedup=%.3f\n",e.name,wanted,ms[0],ms[1],1000/ms[0],ms[1]/ms[0]);
    }
    free(rgb);free(s);PsxDisc_Close(&d);return 0;
}
