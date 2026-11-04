#include "game_texture_decode.h"
#include "psx_game_pixel.h"
#include <string.h>
bool game_texture_decode_init(GameTextureDecode *d,const PsxVram *vram,uint32_t page,uint32_t clut)
{
    unsigned mode=(page>>7)&3;
    if(!d || !vram || mode>2 || (mode<2 && (clut>>6)>=512))return false;
    d->vram=vram;d->mode=mode;d->px=(page&15)*64;d->py=(page&16)*16;
    d->coverage=mode==2?3:0;
    if(mode<2) {
        unsigned size=mode?256:16,cx=(clut&63)*16,cy=clut>>6;
        for(unsigned i=0;i<size;i++) {
            uint8_t rgba[4];psx_game_pixel(vram->words[cy*1024+((cx+i)&1023)],rgba);
            if(rgba[3])d->coverage|=rgba[3]==255?1:2;
            memcpy(&d->palette[i],rgba,4);
        }
    }
    return true;
}
bool game_texture_decode_row(void *context,unsigned y,uint8_t *rgba,unsigned width)
{
    const GameTextureDecode *d=context;
    if(!d || !rgba || width!=256 || y>=256)return false;
    const uint16_t *row=d->vram->words+(((d->py+y)&511)*1024);
    /* Renderer rows are word-aligned; retain alias-safe copies and an unaligned fallback. */
    if(!((uintptr_t)rgba&3))rgba=__builtin_assume_aligned(rgba,4);
    if(d->mode==0) {
        for(unsigned i=0;i<64;i++) {
            unsigned word=row[(d->px+i)&1023];
            for(unsigned j=0;j<4;j++)memcpy(rgba+(i*4+j)*4,&d->palette[(word>>(j*4))&15],4);
        }
    } else if(d->mode==1) {
        for(unsigned i=0;i<128;i++) {
            unsigned word=row[(d->px+i)&1023];
            memcpy(rgba+i*8,&d->palette[word&255],4);memcpy(rgba+i*8+4,&d->palette[word>>8],4);
        }
    } else {
        for(unsigned x=0;x<256;x++)psx_game_pixel(row[(d->px+x)&1023],rgba+x*4);
    }
    return true;
}
bool game_texture_decode_tiled(const GameTextureDecode *d,uint32_t *tiled)
{return game_texture_decode_tiles(d,tiled,0,0,32,32);}
bool game_texture_decode_tiles(const GameTextureDecode *d,uint32_t *tiled,
                              unsigned x0,unsigned y0,unsigned x1,unsigned y1)
{
    if(!d || !tiled || d->mode>2 || ((uintptr_t)tiled&3) || x0>=x1 || y0>=y1 || x1>32 || y1>32)return false;
    static const unsigned spread[8]={0,1,4,5,16,17,20,21};
    uint32_t palette[256];
    if(d->mode<2)for(unsigned i=0;i<(d->mode?256u:16u);i++)palette[i]=__builtin_bswap32(d->palette[i]);
    /* Write each 256-byte tile once in a compact working set. The previous
     * row callback and second swizzle pass remain the independent oracle. */
    for(unsigned ty=y0;ty<y1;ty++)for(unsigned tx=x0;tx<x1;tx++) {
        uint32_t *tile=tiled+(ty*32+tx)*64;
        for(unsigned dy=0;dy<8;dy++) {
            const uint16_t *row=d->vram->words+(((d->py+ty*8+dy)&511)*1024);
            unsigned dest=2*spread[dy];
            if(d->mode==0) {
                unsigned a=row[d->px+tx*2],b=row[d->px+tx*2+1];
                tile[dest]=palette[a&15];tile[dest+1]=palette[(a>>4)&15];
                tile[dest+4]=palette[(a>>8)&15];tile[dest+5]=palette[a>>12];
                tile[dest+16]=palette[b&15];tile[dest+17]=palette[(b>>4)&15];
                tile[dest+20]=palette[(b>>8)&15];tile[dest+21]=palette[b>>12];
            } else if(d->mode==1) {
                for(unsigned j=0;j<4;j++) {
                    unsigned w=row[(d->px+tx*4+j)&1023],at=dest+spread[j*2];
                    tile[at]=palette[w&255];tile[at+1]=palette[w>>8];
                }
            } else {
                for(unsigned dx=0;dx<8;dx++) {
                    unsigned w=row[(d->px+tx*8+dx)&1023];
                    unsigned r=w&31,g=(w>>5)&31,b=(w>>10)&31;
                    uint32_t pixel=(((r<<3)|(r>>2))<<24)|(((g<<3)|(g>>2))<<16)|
                        (((b<<3)|(b>>2))<<8)|(!w?0:(w&0x8000)?128:255);
                    tile[dest+spread[dx]]=pixel;
                }
            }
        }
    }
    return true;
}
