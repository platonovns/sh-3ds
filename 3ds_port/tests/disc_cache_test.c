#include "psx_disc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static unsigned reads,short_next;
size_t __real_fread(void *,size_t,size_t,FILE *);
size_t __wrap_fread(void *p,size_t size,size_t count,FILE *f)
{
    reads++;size_t got=__real_fread(p,size,count,f);
    if(short_next && got){short_next=0;return got-1;}return got;
}
size_t __wrap___fread_chk(void *p,size_t capacity,size_t size,size_t count,FILE *f)
{assert(!size || count<=capacity/size);return __wrap_fread(p,size,count,f);}
int main(int argc,char **argv)
{
    assert(argc>=3);PsxDisc a,b;
    assert(!PsxDisc_Open(&a,argv[1],argv[2]));assert(!PsxDisc_Open(&b,argv[1],argv[2]));
    unsigned lba=argc>3?strtoul(argv[3],0,0):16,n=argc>4?strtoul(argv[4],0,0):64;
    assert(!PsxDisc_CacheRange(&a,lba,n));assert(a.cache_bytes==n*2352 && a.cache_bytes<=16*1024*1024);
    assert(a.preload_reads==(n+31)/32 && a.preload_seeks==1);
    uint8_t left[2352],right[2352];unsigned previous=reads;
    for(unsigned j=0;j<n;j++){unsigned i=n-j-1;assert(!PsxDisc_ReadRawSector(&a,lba+i,left));}
    assert(reads==previous);
    unsigned other=lba>256?16:256;
    assert(!PsxDisc_CacheExtraRange(&a,other,8));assert(a.extra_bytes==8*2352);
    previous=reads;assert(!PsxDisc_ReadRawSector(&a,other,left));assert(reads==previous);
    assert(!PsxDisc_ReadRawSector(&b,other,right));assert(!memcmp(left,right,sizeof(left)));
    assert(a.cache_bytes+a.extra_bytes<=16*1024*1024);
    assert(PsxDisc_CacheExtraRange(&a,80,(16*1024*1024)/2352)==PD_RANGE);
    for(unsigned i=0;i<n;i++) {
        assert(!PsxDisc_ReadRawSector(&a,lba+i,left));assert(!PsxDisc_ReadRawSector(&b,lba+i,right));
        assert(!memcmp(left,right,sizeof(left)));
    }
    assert(PsxDisc_CacheRange(&a,lba,(16*1024*1024)/2352+1)==PD_RANGE && a.raw_cache);
    a.raw_cache[12]^=1;assert(PsxDisc_ReadRawSector(&a,lba,left)==PD_FORMAT);a.raw_cache[12]^=1;
    uint8_t saved=a.raw_cache[18];a.raw_cache[18]|=32;a.raw_cache[22]=a.raw_cache[18];
    assert(PsxDisc_ReadDataSector(&a,lba,left)==PD_FORM2);a.raw_cache[18]=a.raw_cache[22]=saved;
    assert(!PsxDisc_ReadRawSector(&a,lba+n,left));assert(!PsxDisc_ReadRawSector(&b,lba+n,right));assert(!memcmp(left,right,sizeof(left)));
    short_next=1;int failure=PsxDisc_CacheRange(&a,lba+1,n);
    fprintf(stderr,"short preload result=%d remaining=%u reads=%u\n",failure,short_next,reads);
    assert(failure==PD_IO);assert(!a.raw_cache && !a.cache_bytes);
    assert(!PsxDisc_ReadRawSector(&a,lba+2,left));assert(!PsxDisc_ReadRawSector(&b,lba+2,right));assert(!memcmp(left,right,sizeof(left)));
    assert(!PsxDisc_CacheRange(&a,lba,n));PsxDisc_Close(&a);PsxDisc_Close(&b);
    assert(!a.raw_cache && !a.cache_bytes && !a.cache_sectors && !a.extra_cache && !a.extra_bytes);
    printf("PASS: %u cached sectors match disk; zero cached fread; batch reads, bounds, corruption/Form2, short-read fallback, close\n",n);
}
