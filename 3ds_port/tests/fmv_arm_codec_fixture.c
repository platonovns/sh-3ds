/* Freestanding byte helper for a decoder-only ARM ELF. No game entry point. */
#include <stddef.h>
void *memset(void *p,int value,size_t n)
{volatile unsigned char *b=p;while(n--)*b++=(unsigned char)value;return p;}
