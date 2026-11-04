#include "game_io.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
uint64_t game3ds_ticks(void){static uint64_t t;return t+=1000;}
int main(void)
{
    game_io_context(11,0,900,-62*4096,90*4096,0);
    for(unsigned i=0;i<3000;i++) {
        game_io_begin(i%8,100+i,128);game_io_raw(100+i,2352,2352,i%2,100);
        game_io_data(128);game_io_end(0);
    }
    FILE *f=tmpfile();assert(f);game_io_report(f);long n=ftell(f);assert(n<50000);
    rewind(f);char *text=calloc(n+1,1);assert(text);assert(fread(text,1,n,f)==(size_t)n);fclose(f);
    assert(strstr(text,"io_requests=3000\n"));assert(strstr(text,"io_unique_files=8\n"));
    assert(strstr(text,"io_unique_resource_bytes=1024\n"));assert(strstr(text,"io_repeated_requests=2992\n"));
    assert(strstr(text,"io_request_127="));assert(!strstr(text,"io_request_128="));free(text);
    puts("PASS: bounded 128-request history, per-file/repeated/working-set accounting, exact request completion");
}
