#include "game_texture_cache.h"
#include "game_texture_decode.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static PsxVram vram;
static GameTextureCache cache;
static uint32_t actual[65536],expected[65536],seed=0x11a;
static unsigned rng(void){return seed=seed*1664525u+1013904223u;}
int main(void)
{
    unsigned cases=0,partial=0;
    for(unsigned i=0;i<1024*512;i++)vram.words[i]=rng()>>16;
    for(unsigned mode=0;mode<3;mode++)for(unsigned page=0;page<32;page++) {
        memset(&cache,0,sizeof(cache));game_texture_begin(&cache);
        uint32_t key=(mode<<7)|page,clut=(490<<6)|63;
        bool upload=false;int slot=game_texture_acquire(&cache,key,clut,&upload);assert(slot>=0 && upload);
        GameTextureDecode decode;assert(game_texture_decode_init(&decode,&vram,key,clut));
        assert(game_texture_decode_tiled(&decode,actual));cache.entries[slot].dirty=false;
        for(unsigned step=0;step<80;step++) {
            for(unsigned write=0;write<3;write++) {
                PsxRect r;
                if(step%9==0 && write==2)r=(PsxRect){1008,490,16,1}; /* CLUT AFTER pending image dirt. */
                else if(step%3==0)r=(PsxRect){(page&15)*64,(page&16)*16,17+step,1+step};
                else {r.w=1+rng()%320;r.h=1+rng()%128;r.x=rng()%(1025-r.w);r.y=rng()%(513-r.h);}
                if(r.w>1024-r.x)r.w=1024-r.x;
                for(unsigned y=r.y;y<r.y+r.h;y++)for(unsigned x=r.x;x<r.x+r.w;x++)vram.words[y*1024+x]=rng()>>16;
                game_texture_invalidate(&cache,r);
            }
            GameTextureEntry *e=&cache.entries[slot];
            assert(game_texture_decode_init(&decode,&vram,key,clut));
            if(e->dirty){assert(game_texture_decode_tiles(&decode,actual,e->tx0,e->ty0,e->tx1,e->ty1));
                partial+=(e->tx1-e->tx0)*(e->ty1-e->ty0)<1024;e->dirty=false;}
            assert(game_texture_decode_tiled(&decode,expected));
            assert(!memcmp(actual,expected,sizeof(actual)));cases++;
        }
    }
    /* A canonical 320x224 framebuffer write touches 896 + 224 tiles. */
    memset(&cache,0,sizeof(cache));game_texture_begin(&cache);
    bool upload;int a=game_texture_acquire(&cache,256,0,&upload),b=game_texture_acquire(&cache,260,0,&upload);
    cache.entries[a].dirty=cache.entries[b].dirty=false;game_texture_invalidate(&cache,(PsxRect){0,0,320,224});
    assert(cache.entries[a].tx1==32 && cache.entries[a].ty1==28);
    assert(cache.entries[b].tx1==8 && cache.entries[b].ty1==28);
    printf("PASS: %u transactions, %u partial uploads, all modes/pages/wrap/CLUT union; capture tiles 1120/2048\n",cases,partial);
}
