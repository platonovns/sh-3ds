#include "game_texture_decode.h"
#include "psx_game_pixel.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
static PsxVram vram;
int main(void)
{
    for(unsigned w=0;w<65536;w++) {
        uint8_t rgba[4];PsxTexel ref;psx_game_pixel(w,rgba);psx_color_decode(w,&ref);
        assert(!memcmp(rgba,ref.rgba,3));assert(rgba[3]==(!w?0:(w&32768)?128:255));
    }
    uint32_t seed=1;
    for(unsigned i=0;i<1024*512;i++){seed=seed*1664525+1013904223;vram.words[i]=seed>>16;}
    /* CLUT entries, not palette indices, control transparency. */
    vram.words[511*1024+1008]=0x8000;vram.words[511*1024+1009]=0;
    for(unsigned mode=0;mode<3;mode++)for(unsigned page=0;page<32;page++) {
        GameTextureDecode d;uint32_t storage[257];uint8_t *rgba=(uint8_t*)storage+(page&1);
        unsigned tp=page|(mode<<7),clut=511*64+63;
        assert(game_texture_decode_init(&d,&vram,tp,clut));
        for(unsigned y=0;y<256;y++) {
            assert(game_texture_decode_row(&d,y,rgba,256));
            for(unsigned x=0;x<256;x++) {
                unsigned word=vram.words[(((page&16)*16+y)&511)*1024+(((page&15)*64+(x>>(2-mode)))&1023)];
                if(mode<2){unsigned index=mode?(word>>((x&1)*8))&255:(word>>((x&3)*4))&15;
                    word=vram.words[511*1024+((1008+index)&1023)];}
                uint8_t expected[4];psx_game_pixel(word,expected);assert(!memcmp(rgba+x*4,expected,4));
                assert(!word || (d.coverage & ((word&32768)?2:1)));
            }
        }
    }
    GameTextureDecode d;
    for(unsigned mode=0;mode<2;mode++)for(unsigned classes=0;classes<4;classes++) {
        memset(&vram,0,sizeof(vram));
        if(classes&1)vram.words[1]=0x001f;
        if(classes&2)vram.words[2]=0x8000;
        assert(game_texture_decode_init(&d,&vram,mode<<7,0));
        assert(d.coverage==classes);
    }
    assert(game_texture_decode_init(&d,&vram,2<<7,0));assert(d.coverage==3);
    assert(!game_texture_decode_init(&d,&vram,0x180,0));
    assert(!game_texture_decode_init(&d,&vram,0,512*64));
    puts("PASS: all word colors, 4/8/16-bit pages, image/CLUT wrap and alpha classes");
}
