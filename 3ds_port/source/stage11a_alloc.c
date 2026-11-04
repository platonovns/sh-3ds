/* Observational linker wrappers only. No live-object registry, allocation,
 * printf, allocator-size query or mutex is added to an allocation/free path. */
#include <3ds.h>
#include <malloc.h>
#include "stage11a_lifetime.h"
#define WRAP_ALLOC(name,id) \
void *__real_##name(size_t); \
void *__wrap_##name(size_t n){void *p=__real_##name(n);stage11a_lifetime_alloc(id,n,p==NULL);return p;}
#define WRAP_ALIGN(name,id) \
void *__real_##name(size_t,size_t); \
void *__wrap_##name(size_t n,size_t a){void *p=__real_##name(n,a);stage11a_lifetime_alloc(id,n,p==NULL);return p;}
#define WRAP_FREE(name,id) \
void __real_##name(void*); \
void __wrap_##name(void *p){int nonnull=p!=NULL;__real_##name(p);if(nonnull)stage11a_lifetime_alloc(id,0,0);}
WRAP_ALLOC(malloc,0)
void *__real_calloc(size_t,size_t);
void *__wrap_calloc(size_t n,size_t size){void *p=__real_calloc(n,size);stage11a_lifetime_alloc(1,(uint32_t)(n*size),p==NULL);return p;}
void *__real_realloc(void*,size_t);
void *__wrap_realloc(void *old,size_t n){void *p=__real_realloc(old,n);stage11a_lifetime_alloc(2,n,p==NULL && n!=0);return p;}
WRAP_FREE(free,3)
/* memalign takes alignment FIRST, unlike the SDK linear/VRAM functions. */
void *__real_memalign(size_t,size_t);
void *__wrap_memalign(size_t a,size_t n){void *p=__real_memalign(a,n);stage11a_lifetime_alloc(4,n,p==NULL);return p;}
WRAP_ALLOC(linearAlloc,5)
WRAP_ALIGN(linearMemAlign,6)
WRAP_FREE(linearFree,7)
WRAP_ALLOC(vramAlloc,8)
void *__real_vramAllocAt(size_t,vramAllocPos);
void *__wrap_vramAllocAt(size_t n,vramAllocPos pos){void *p=__real_vramAllocAt(n,pos);stage11a_lifetime_alloc(9,n,p==NULL);return p;}
WRAP_ALIGN(vramMemAlign,10)
void *__real_vramMemAlignAt(size_t,size_t,vramAllocPos);
void *__wrap_vramMemAlignAt(size_t n,size_t a,vramAllocPos pos){void *p=__real_vramMemAlignAt(n,a,pos);stage11a_lifetime_alloc(11,n,p==NULL);return p;}
WRAP_FREE(vramFree,12)
