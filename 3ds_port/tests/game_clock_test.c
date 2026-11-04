#include "game_clock.h"
#include "psx_game_pixel.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    const uint32_t hz=268123480;
    assert(game_clock_units(hz, hz,60)==60);
    assert(game_clock_units(hz/20,hz,60)==3);
    assert(game_clock_units(hz/20,hz,15780)==789);
    assert(game_clock_units((uint64_t)hz*300,hz,15780)==4734000);
    assert(game_clock_units((uint64_t)hz*365*86400,hz,15780)==(uint32_t)(365ull*86400*15780));
    /* Work duration advances counters even when no explicit wait is called. */
    uint64_t now=0;
    uint32_t previous=0;
    for(unsigned i=0;i<10000;i++) {
        now+=hz/20;
        uint32_t count=game_clock_units(now,hz,60);
        assert(count-previous==3); previous=count;
    }
    uint8_t rgba[4];
    psx_game_pixel(0,rgba); assert(rgba[3]==0);
    psx_game_pixel(0x8000,rgba); assert(rgba[0]==0 && rgba[3]==128);
    psx_game_pixel(0x001f,rgba); assert(rgba[0]==255 && rgba[3]==255);
    psx_game_pixel(0x83e0,rgba); assert(rgba[1]==255 && rgba[3]==128);
    puts("PASS: independent VBlank/HBlank clock, long-runtime overflow, zero/STP/opaque classes");
}
