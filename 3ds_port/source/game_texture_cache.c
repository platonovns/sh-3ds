#include "game_texture_cache.h"
#include <limits.h>
#include <string.h>
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
static uint32_t lt_invalidations,lt_image,lt_clut,lt_both;
void stage11a_lifetime_cache(uint32_t out[LT_CACHE_WORDS])
{out[0]=lt_invalidations;out[1]=lt_image;out[2]=lt_clut;out[3]=lt_both;}
#endif
_Static_assert(GAME_TEXTURE_LIMIT<256,"Texture slot index fits one byte");
static unsigned key_hash(uint32_t page,uint32_t clut)
{
    uint32_t h=page*0x9e3779b9u ^ clut*0x85ebca6bu;
    return (h^(h>>16))&255;
}
static int lookup(GameTextureCache *c,uint32_t page,uint32_t clut)
{
    unsigned h=key_hash(page,clut);
    for(unsigned n=0;n<256;n++,h=(h+1)&255) {
        c->comparisons++;
        unsigned slot=c->index[h];if(!slot)return -1;
        const GameTextureEntry *e=&c->entries[slot-1];
        if(e->page==page && e->clut==clut)return slot-1;
    }
    return -1;
}
static void reindex(GameTextureCache *c)
{
    memset(c->index,0,sizeof(c->index));
    for(unsigned i=0;i<GAME_TEXTURE_LIMIT;i++)if(c->entries[i].occupied) {
        unsigned h=key_hash(c->entries[i].page,c->entries[i].clut);
        while(c->index[h])h=(h+1)&255;
        c->index[h]=i+1;
    }
}

void game_texture_begin(GameTextureCache *c)
{
    /* Saturation is many months of submissions; preserve bounded LRU ordering. */
    if (c->clock == UINT32_MAX) {
        for (unsigned i=0; i<GAME_TEXTURE_LIMIT; i++) c->entries[i].age = 0;
        c->clock = 0;
    }
    c->clock++;
    c->pinned=0;
    for (unsigned i=0; i<GAME_TEXTURE_LIMIT; i++) c->entries[i].pinned = false;
}
void game_texture_pin(GameTextureCache *c, uint32_t page, uint32_t clut)
{
    int slot=lookup(c,page,clut);
    if(slot>=0) {
        GameTextureEntry *e=&c->entries[slot];
        if(!e->pinned) {
            e->pinned=true;c->pinned++;
            if(c->pinned>c->peak_pinned)c->peak_pinned=c->pinned;
        }
    }
}
int game_texture_acquire(GameTextureCache *c, uint32_t page, uint32_t clut, bool *upload)
{
    int slot=-1;
    int hit=lookup(c,page,clut);
    if(hit>=0) {
        GameTextureEntry *e=&c->entries[hit];
        c->hits++; e->age=c->clock;
        if (!e->pinned) { e->pinned=true; c->pinned++; }
        if (c->pinned>c->peak_pinned) c->peak_pinned=c->pinned;
        *upload=e->dirty;
        return hit;
    }
    for (unsigned i=0; i<GAME_TEXTURE_LIMIT; i++) {
        GameTextureEntry *e=&c->entries[i];
        c->comparisons++;
        if (!e->pinned && (slot<0 || !e->occupied ||
            (c->entries[slot].occupied && e->age<c->entries[slot].age))) slot=(int)i;
    }
    c->misses++;
    if (slot<0) return -1;
    GameTextureEntry *e=&c->entries[slot];
    if (e->occupied) c->evictions++;
    else { c->active++; if (c->active>c->peak) c->peak=c->active; }
    *e=(GameTextureEntry){.page=page,.clut=clut,.age=c->clock,
                          .occupied=true,.dirty=true,.pinned=true,.tx1=32,.ty1=32};
    reindex(c);
    c->pinned++; if (c->pinned>c->peak_pinned) c->peak_pinned=c->pinned;
    *upload=true;
    return slot;
}
bool game_texture_discard(GameTextureCache *c, unsigned slot)
{
    if(slot>=GAME_TEXTURE_LIMIT || !c->entries[slot].occupied || c->entries[slot].pinned)return false;
    memset(&c->entries[slot],0,sizeof(c->entries[slot]));
    c->active--;c->evictions++;reindex(c);return true;
}
static bool overlap(unsigned start, unsigned length, unsigned x, unsigned w)
{
    unsigned end=start+length;
    return (start<x+w && x<(end>1024?1024:end)) || (end>1024 && x<end-1024);
}
void game_texture_invalidate(GameTextureCache *c, PsxRect r)
{
#if defined(SH_STAGE11A_LIFETIME)
    lt_invalidations++;
#endif
    for (unsigned i=0; i<GAME_TEXTURE_LIMIT; i++) {
        GameTextureEntry *e=&c->entries[i];
        if (!e->occupied) continue;
        unsigned mode=(e->page>>7)&3, y=(e->page&16)*16;
        bool image=r.y<y+256 && y<r.y+r.h &&
                   overlap((e->page&15)*64,64u<<mode,r.x,r.w);
        unsigned cy=(e->clut>>6)&511;
        bool palette=mode<2 && r.y<=cy && cy<r.y+r.h &&
                     overlap((e->clut&63)*16,mode?256:16,r.x,r.w);
        if (image || palette) {
            bool was_dirty=e->dirty;
            if(!was_dirty){e->tx0=e->ty0=32;e->tx1=e->ty1=0;}
#if defined(SH_STAGE11A_LIFETIME)
            if(!was_dirty){lt_image+=image;lt_clut+=palette;lt_both+=image&&palette;}
#endif
            if(palette || mode>2){e->tx0=e->ty0=0;e->tx1=e->ty1=32;}
            else {
                unsigned top=r.y>y?r.y-y:0,bottom=r.y+r.h-y;
                if(bottom>256)bottom=256;
                unsigned ty0=top/8,ty1=(bottom+7)/8;
                if(ty0<e->ty0)e->ty0=ty0;
                if(ty1>e->ty1)e->ty1=ty1;
                unsigned px=(e->page&15)*64,words=64u<<mode;
                /* A wrapped image intersects at most two canonical segments.
                 * Translate word coordinates back to decoded texels. */
                for(unsigned segment=0;segment<2;segment++) {
                    unsigned base=segment?0:px,offset=segment?1024-px:0;
                    if(offset>=words)continue;
                    unsigned end=base+words-offset;if(end>1024)end=1024;
                    unsigned lo=r.x>base?r.x:base,hi=r.x+r.w<end?r.x+r.w:end;
                    if(lo>=hi)continue;
                    unsigned tx0=((offset+lo-base)<<(2-mode))/8;
                    unsigned tx1=(((offset+hi-base)<<(2-mode))+7)/8;
                    if(tx0<e->tx0)e->tx0=tx0;
                    if(tx1>e->tx1)e->tx1=tx1;
                }
            }
            e->dirty=true;if(!was_dirty)c->invalidations++;
        }
    }
}
