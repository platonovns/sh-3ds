/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "fmv_stream.h"
#include "fmv_mdec.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
FILE *g_ShDebugLog;
void oracle_init(mdec_ctx_t *,int,int);
int oracle_decode(mdec_ctx_t *,const uint8_t *,size_t,uint8_t *);
int oracle_xa_decode(const uint8_t *,int16_t *);
void oracle_xa_reset(void);
static uint32_t audio_pts,audio_crc,expected_pts;
static int audio(void *unused,const int16_t *pcm,uint32_t n,uint32_t pts)
{
    FmvStream *stream=unused;assert(pts==expected_pts);expected_pts+=n;audio_pts+=n;
    if(stream && stream->cursor && (stream->raw[18]&4) &&
       (stream->cursor-1)%8==7 && pts==(stream->cursor-1)/8*FMV_AUDIO_FRAMES) {
        int16_t ref[4032];assert(oracle_xa_decode(stream->raw+16,ref)==4032);
        assert(!memcmp(ref,pcm,n*4));
    }
    audio_crc=PsxDisc_Crc32(audio_crc,pcm,n*4);return 1;
}
static double secs(void){return (double)clock()/CLOCKS_PER_SEC;}
int main(int argc,char **argv)
{
    assert(argc==3);
    PsxDisc disc;ShDisc sh;
    assert(PsxDisc_Open(&disc,argv[1],argv[2])==0);assert(ShDisc_Init(&sh,&disc)==0);
    FmvStream *s=malloc(sizeof(*s));uint8_t *rgb=malloc(FMV_RGB_BYTES+16),*ref=malloc(FMV_RGB_BYTES);
    assert(s && rgb && ref);
    /* Measured from the disc inventory, including padded-file variants. */
    static const uint32_t lengths[]={2067,2067,350,119,257,249,314,209,150,304,173,
        359,485,193,378,330,1618,234,159,1421,1424};
    for(unsigned id=2053;id<=2073;id++) {
        FmvEntry e;assert(fmv_entry(&sh,id,0,&e)==0);
        uint32_t logical_limit=e.frame_limit;
        e.frame_limit=lengths[id-2053];fmv_stream_init(s,&disc,&e);
        audio_pts=audio_crc=expected_pts=0;
        oracle_xa_reset();
        uint32_t no,bytes,count=0,compared=0,crc=0;int r;
        double time=0;
        while((r=fmv_next_frame(s,audio,s,&no,&bytes))>0) {
            ++count;
            /* Three samples per movie; never export copyrighted imagery. */
            uint32_t actual=lengths[id-2053];
            if(no!=1 && no!=actual/2 && no!=actual)continue;
            mdec_ctx_t ctx,oracle;memset(rgb+FMV_RGB_BYTES,0xa5,16);
            mdec_init(&ctx,320,208);oracle_init(&oracle,320,208);
            double t=secs();int n=mdec_decode_frame(&ctx,s->bits,bytes,rgb);time+=secs()-t;
            if(n!=260){fprintf(stderr,"DECODE %s frame=%u bytes=%u result=%d\n",e.name,no,bytes,n);return 2;}
            assert(oracle_decode(&oracle,s->bits,bytes,ref)==260);
            assert(!memcmp(rgb,ref,FMV_RGB_BYTES));
            for(unsigned k=0;k<16;k++)assert(rgb[FMV_RGB_BYTES+k]==0xa5);
            assert(mdec_decode_frame(&ctx,s->bits,8,rgb)<0);
            crc=PsxDisc_Crc32(crc,rgb,FMV_RGB_BYTES);++compared;
        }
        if(r<0){fprintf(stderr,"DEMUX %s cursor=%u frame=%u result=%d\n",e.name,s->cursor,s->frame,r);return 3;}
        assert(count==e.frame_limit && compared==3);
        assert(fmv_finish_audio(s,audio,s)==0);
        assert(audio_pts==fmv_duration_samples(&e));
        printf("%s frames=%u default_limit=%u compared=%u decode_ms=%.4f fps=%.2f rgb_crc=%08x pcm_crc=%08x pcm_frames=%u audio=%u silent=%u\n",
            e.name,count,logical_limit,compared,time*1000/compared,compared/time,crc,audio_crc,audio_pts,s->audio_sectors,s->silent_sectors);
    }
    /* Random malformed VLC, including short lookahead at EOF. */
    uint32_t seed=1;
    for(unsigned trial=0;trial<1000;trial++) {
        uint32_t n=8+(trial*18u)%2000u;
        for(unsigned i=0;i<n;i++){seed=seed*1664525u+1013904223u;s->bits[i]=seed>>24;}
        s->bits[2]=0;s->bits[3]=0x38;s->bits[4]=1;s->bits[5]=0;s->bits[6]=2;s->bits[7]=0;
        mdec_ctx_t ctx;mdec_init(&ctx,320,208);
        assert(mdec_decode_frame(&ctx,s->bits,n,rgb)<0);
    }
    puts("malformed_vlc=1000 PASS");
    free(ref);free(rgb);free(s);PsxDisc_Close(&disc);return 0;
}
