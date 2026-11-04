#include "game_texture_cache.h"
#include "game_pad.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>

static int acquire(GameTextureCache *c, unsigned page, unsigned clut, bool expected_upload)
{
    bool upload=false;
    int slot=game_texture_acquire(c,page,clut,&upload);
    assert(slot>=0 && upload==expected_upload);
    if (upload) { c->entries[slot].dirty=false; c->uploads++; }
    return slot;
}
int main(void)
{
    const unsigned hid[]={2,3,6,4,7,5,14,15,9,8,10,0,1,11};
    const unsigned psx[]={0,3,4,5,6,7,8,9,10,11,12,13,14,15};
    for (unsigned i=0;i<sizeof(hid)/sizeof(hid[0]);i++)
        assert(game_pad_buttons(1u<<hid[i])==(1u<<psx[i]));
    assert(game_pad_buttons(1u<<30)==(1u<<4));
    assert(game_pad_buttons(1u<<31)==(1u<<6));
    assert(game_pad_buttons(1u<<28)==(1u<<5));
    assert(game_pad_buttons(1u<<29)==(1u<<7));
    assert(game_pad_buttons((1u<<6)|(1u<<1))==((1u<<4)|(1u<<14)));
    GameTextureCache c={0};
    game_texture_begin(&c);
    for (unsigned i=0;i<GAME_TEXTURE_LIMIT;i++) acquire(&c,0,i,true);
    bool upload;
    assert(game_texture_acquire(&c,0,GAME_TEXTURE_LIMIT,&upload)==-1); /* No live-slot overwrite. */
    game_texture_begin(&c);
    /* Protect a hit that appears AFTER a miss in painter order. */
    game_texture_pin(&c,0,0);
    acquire(&c,0,GAME_TEXTURE_LIMIT,true);
    acquire(&c,0,0,false);
    assert(c.evictions==1 && c.active==GAME_TEXTURE_LIMIT);
    for (unsigned frame=0;frame<100000;frame++) {
        game_texture_begin(&c);
        unsigned key=frame%1000;
        int slot=game_texture_acquire(&c,0,key,&upload);
        assert(slot>=0);
        c.entries[slot].dirty=false;
    }
    assert(c.active==GAME_TEXTURE_LIMIT && c.peak==GAME_TEXTURE_LIMIT && c.evictions>90000);

    c=(GameTextureCache){0};game_texture_begin(&c);
    int keep=acquire(&c,1,1,true),old=acquire(&c,2,2,true);
    assert(!game_texture_discard(&c,keep));
    game_texture_begin(&c);game_texture_pin(&c,1,1);
    assert(game_texture_discard(&c,old) && c.active==1 && c.evictions==1);
    assert(!game_texture_discard(&c,keep) && !game_texture_discard(&c,old));
    acquire(&c,1,1,false);acquire(&c,2,2,true);

    c=(GameTextureCache){0}; game_texture_begin(&c);
    int four=acquire(&c,0,64*300+16,true); /* image x0..63/y0..255; CLUT x256/y300 */
    int eight=acquire(&c,0x80|15,64*400+63,true); /* both image/palette wrap */
    int direct=acquire(&c,0x100|16|15,0,true); /* image x960..191/y256..511 */
    game_texture_invalidate(&c,(PsxRect){500,350,10,1});
    assert(c.invalidations==0);
    game_texture_invalidate(&c,(PsxRect){256,300,1,1});
    assert(c.entries[four].dirty && !c.entries[eight].dirty && !c.entries[direct].dirty);
    game_texture_invalidate(&c,(PsxRect){256,300,1,1});
    assert(c.invalidations==1); /* Already dirty: no duplicate invalidation. */
    acquire(&c,0,64*300+16,true);
    game_texture_invalidate(&c,(PsxRect){63,255,1,1}); assert(c.entries[four].dirty);
    game_texture_invalidate(&c,(PsxRect){0,400,1,1});
    assert(c.entries[eight].dirty && c.entries[direct].dirty);
    assert(c.invalidations==4);
    c.clock=UINT32_MAX; game_texture_begin(&c);
    assert(c.clock==1);
    for (unsigned i=0;i<GAME_TEXTURE_LIMIT;i++) assert(!c.entries[i].pinned);
    puts("PASS: bounded churn, frame pins, LRU, image/CLUT wrap, partial invalidation, clock wrap");
    return 0;
}
