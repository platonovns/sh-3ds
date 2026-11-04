#include "game_texture_decode.h"
#include "texture_layout.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint32_t random_word(void){static uint32_t s=0xa51c6;s^=s<<13;s^=s>>17;s^=s<<5;return s;}
int main(void)
{
    PsxVram *v=malloc(sizeof(*v));uint32_t *old=malloc(256*256*4),*guard=malloc(256*256*4+8);
    assert(v&&old&&guard);uint32_t row[256];unsigned cases=0;
    for(unsigned i=0;i<1024*512;i++)v->words[i]=(uint16_t)random_word();
    for(unsigned mode=0;mode<3;mode++)for(unsigned py=0;py<2;py++)for(unsigned px=0;px<16;px++) {
        GameTextureDecode d;unsigned clut=(511<<6)|63;
        assert(game_texture_decode_init(&d,v,(mode<<7)|(py<<4)|px,clut));
        for(unsigned y=0;y<256;y++){assert(game_texture_decode_row(&d,y,(uint8_t*)row,256));texture3ds_write_row(old,256,y,row,256);}
        guard[0]=guard[256*256+1]=0x1234a55a;
        assert(game_texture_decode_tiled(&d,guard+1));
        assert(!memcmp(old,guard+1,256*256*4));assert(guard[0]==0x1234a55a&&guard[256*256+1]==0x1234a55a);cases++;
    }
    for(unsigned i=0;i<1024*512;i++)v->words[i]=(uint16_t)(i%3==0?0:i%3==1?0x8000:0x7fff);
    for(unsigned mode=0;mode<3;mode++) {
        GameTextureDecode d;assert(game_texture_decode_init(&d,v,(mode<<7)|31,(511<<6)|63));
        for(unsigned y=0;y<256;y++){assert(game_texture_decode_row(&d,y,(uint8_t*)row,256));texture3ds_write_row(old,256,y,row,256);}
        assert(game_texture_decode_tiled(&d,guard+1));assert(!memcmp(old,guard+1,256*256*4));cases++;
    }
    free(v);free(old);free(guard);printf("PASS: %u exact full texture pages, 4/8/16-bit, wrap, CLUT, zero and STP\n",cases);
}
