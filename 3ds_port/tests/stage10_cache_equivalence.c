#include "game_texture_cache.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
void ref_begin(GameTextureCache*);
void ref_pin(GameTextureCache*,uint32_t,uint32_t);
int ref_acquire(GameTextureCache*,uint32_t,uint32_t,bool*);
void ref_invalidate(GameTextureCache*,PsxRect);
static void equal(const GameTextureCache *a,const GameTextureCache *b)
{
    assert(!memcmp(a->entries,b->entries,sizeof(a->entries)));
    assert(a->hits==b->hits && a->misses==b->misses && a->evictions==b->evictions);
    assert(a->pinned==b->pinned && a->peak_pinned==b->peak_pinned && a->active==b->active);
    assert(a->invalidations==b->invalidations);
}
int main(void)
{
    GameTextureCache a={0},b={0};unsigned operations=0;
    for(unsigned frame=0;frame<2000;frame++) {
        unsigned keys[75];
        game_texture_begin(&a);ref_begin(&b);
        for(unsigned j=0;j<75;j++) {
            keys[j]=j<70?j:70+(frame/17+j)%120;
            game_texture_pin(&a,0,keys[j]);ref_pin(&b,0,keys[j]);
        }
        for(unsigned j=0;j<75;j++) {
            bool ua=false,ub=false;
            int sa=game_texture_acquire(&a,0,keys[j],&ua),sb=ref_acquire(&b,0,keys[j],&ub);
            assert(sa==sb && ua==ub && sa>=0);operations++;
            a.entries[sa].dirty=b.entries[sb].dirty=false;
            equal(&a,&b);
        }
        if(frame%13==0) {
            PsxRect r={frame%1024,frame%512,1,1};
            game_texture_invalidate(&a,r);ref_invalidate(&b,r);equal(&a,&b);
        }
    }
    assert(a.comparisons<b.comparisons/8);
    printf("{\"status\":\"PASS\",\"equivalent_acquires\":%u,\"reference_comparisons\":%u,\"indexed_probes\":%u}\n",
        operations,b.comparisons,a.comparisons);
}
