#include "texture_layout.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(void)
{
    uint32_t row[1024];
    for(unsigned width=8;width<=1024;width*=2)for(unsigned height=8;height<=1024;height*=2) {
        unsigned logical=width-3;size_t size=(size_t)width*height*4;
        uint32_t *out=calloc(1,size);uint8_t *reference=calloc(1,size);assert(out&&reference);
        for(unsigned y=0;y<height-2;y++) {
            for(unsigned x=0;x<logical;x++)row[x]=0x12345678u+x*65537u+y*271u;
            texture3ds_write_row(out,width,y,row,logical);
            for(unsigned x=0;x<logical;x++)texture3ds_write_rgba8(reference+
                texture3ds_offset(width,height,x,y),(uint8_t*)&row[x]);
        }
        assert(!memcmp(out,reference,size));free(out);free(reference);
    }
    puts("PASS: factored Morton row kernel matches reference, padding untouched for 64 shapes");
}
