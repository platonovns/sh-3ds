/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "fmv_stream.h"
#include <string.h>
/* Reuse Stage 9's exact XA decoder, including its predictor history. */
int game_xa_decode(const uint8_t *,int16_t *,int32_t [2][2]);
static const char *const names[]={"C1_20670","C2_20670","M1_03500","M2_01190",
 "M3_02570","M4_02490","M5_03140","M6_02112","M7_01536","M8_03039",
 "M9_01730","MA_03590","MB_04850","MC_01930","MD_03780","ME_03300",
 "Z1_16180","Z3_02340","Z4_01590","ZC_14392","ZZ_14239"};
static uint16_t le16(const uint8_t *p){return p[0]|(uint16_t)p[1]<<8;}
static uint32_t le32(const uint8_t *p){return le16(p)|(uint32_t)le16(p+2)<<16;}
uint32_t fmv_frame_sample(uint32_t n){return (n-1u)*(FMV_RATE/FMV_FPS);}
uint32_t fmv_duration_samples(const FmvEntry *e){return e->frame_limit*(FMV_RATE/FMV_FPS);}
int fmv_entry(ShDisc *sh,uint32_t id,uint32_t requested,FmvEntry *e)
{
    if(!sh || !e || id<2053 || id>2073)return PD_RANGE;
    ShDiscFile f;int r=ShDisc_Resolve(sh,id,&f);if(r)return r;
    const char *name=names[id-2053];uint32_t sectors=0;
    for(unsigned i=3;i<8;i++)sectors=sectors*10u+(unsigned)(name[i]-'0');
    uint32_t blocks=f.bytes/256u;
    uint32_t limit=requested?requested:(blocks>7?blocks-7:0);
    if(!limit || limit>sectors || sectors>sh->disc->sectors-f.lba)return PD_RANGE;
    *e=(FmvEntry){id,f.lba,sectors,limit,name};return 0;
}
void fmv_stream_init(FmvStream *s,PsxDisc *d,const FmvEntry *e)
{memset(s,0,sizeof(*s));s->disc=d;s->entry=*e;}
static int audio_slot(FmvStream *s,FmvAudioSink sink,void *user,uint32_t rel)
{
    const uint8_t *raw=s->raw;int audio=(raw[18]&4)!=0;
    if(audio && rel%8u!=7)return PD_FORMAT;
    if(rel%8u!=7)return 1;
    uint32_t pts=(rel/8u)*FMV_AUDIO_FRAMES;
    uint32_t total=fmv_duration_samples(&s->entry);
    if(pts>=total)return 1;
    uint32_t count=total-pts;if(count>FMV_AUDIO_FRAMES)count=FMV_AUDIO_FRAMES;
    if(audio) {
        if(raw[16]!=1 || raw[17]!=1 || raw[19]!=1 || (raw[18]&0x64)!=0x64)return PD_FORMAT;
        if(game_xa_decode(raw+16,s->pcm,s->history)!=FMV_AUDIO_FRAMES*2)return PD_FORMAT;
        ++s->audio_sectors;s->decoded_audio+=FMV_AUDIO_FRAMES;
    } else {memset(s->pcm,0,sizeof(s->pcm));++s->silent_sectors;}
    s->emitted_audio+=count;
    return !sink || sink(user,s->pcm,count,pts)>0?1:PD_IO;
}
static int read_sector(FmvStream *s)
{
    uint32_t rel=s->cursor,lba=s->entry.lba+rel;
    if(rel>=s->entry.sectors)return 0;
    if(rel%32u==0) {
        uint32_t n=s->entry.sectors-rel;if(n>32)n=32;
        int r=PsxDisc_CacheRange(s->disc,lba,n);if(r)return r;
    }
    int r=PsxDisc_ReadRawSector(s->disc,lba,s->raw);if(r)return r;
    ++s->cursor;++s->raw_sectors;return 1;
}
int fmv_finish_audio(FmvStream *s,FmvAudioSink sink,void *user)
{
    uint32_t total=fmv_duration_samples(&s->entry);
    while(s->emitted_audio<total && s->cursor<s->entry.sectors) {
        uint32_t rel=s->cursor;int r=read_sector(s);if(r<0)return r;
        r=audio_slot(s,sink,user,rel);if(r<0)return r;
    }
    memset(s->pcm,0,sizeof(s->pcm));
    while(s->emitted_audio<total) {
        uint32_t n=total-s->emitted_audio;if(n>FMV_AUDIO_FRAMES)n=FMV_AUDIO_FRAMES;
        if(sink && sink(user,s->pcm,n,s->emitted_audio)<=0)return PD_IO;
        s->emitted_audio+=n;
    }
    return 0;
}
int fmv_next_frame(FmvStream *s,FmvAudioSink sink,void *user,uint32_t *number,uint32_t *bytes)
{
    if(!s || !s->disc || !number || !bytes)return PD_RANGE;
    if(s->frame>=s->entry.frame_limit)return 0;
    uint32_t chunks=0,wanted=0,size=0,frame=0;
    while(s->cursor<s->entry.sectors) {
        uint32_t rel=s->cursor;
        int r=read_sector(s);if(r<0)return r;
        r=audio_slot(s,sink,user,rel);if(r<0)return r;
        if(s->raw[18]&4)continue;
        const uint8_t *h=s->raw+24;
        if(le16(h)!=0x160 || le16(h+2)!=0x8001) {
            /* Audio-grid gaps and movie tail sectors contain a zero header. */
            static const uint8_t zero[32]={0};
            if(memcmp(h,zero,32))return PD_FORMAT;
            continue;
        }
        uint32_t index=le16(h+4),n=le16(h+6),no=le32(h+8),sz=le32(h+12);
        if(!chunks) {
            if(index || no!=s->frame+1 || n<1 || n>9 || sz<8 || sz>n*2016u || sz%2u)return PD_FORMAT;
            if(rel!=(no-1u)*10u)return PD_FORMAT;
            wanted=n;size=sz;frame=no;s->first_lba=rel;
        }
        if(index!=chunks || n!=wanted || no!=frame || sz!=size ||
           le16(h+16)!=FMV_WIDTH || le16(h+18)!=FMV_HEIGHT)return PD_FORMAT;
        memcpy(s->bits+chunks*2016u,h+32,2016u);++chunks;++s->video_sectors;
        if(chunks==wanted) {
            s->frame=frame;*number=frame;*bytes=size;return 1;
        }
    }
    return chunks?PD_FORMAT:0;
}
