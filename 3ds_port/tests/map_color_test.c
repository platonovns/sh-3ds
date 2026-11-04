#include "game_map_color.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    assert(game_map_image_color(0xf800,10,0)==0xf800);
    assert(game_map_image_color(0xf800,1,0)==0x1800);
    assert(game_map_image_color(0xf800,10,1)==0x07ff);
    assert(game_map_image_color(0xf800,1,1)==0x00c3);
    assert(game_map_image_color(0,3,1)==((9<<11)|(18<<5)|9));
    assert(game_map_image_color(0xffff,3,1)==0);
    static uint16_t pixels[65536];
    for(unsigned brightness=1;brightness<=10;brightness++)for(unsigned invert=0;invert<2;invert++) {
        for(unsigned p=0;p<65536;p++)pixels[p]=(uint16_t)p;
        game_map_convert(pixels,65536,brightness,invert);
        for(unsigned p=0;p<65536;p++)assert(pixels[p]==game_map_image_color((uint16_t)p,brightness,invert));
    }
    puts("PASS: cached map conversion agrees for every RGB565 value");
}
