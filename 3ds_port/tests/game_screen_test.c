#include "game_screen.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    for(unsigned word=0;word<65536;word++) {
        int expected=word%2048;if(expected>=1024)expected-=2048;
        assert(game_screen_signed11(word)==expected);
    }
    for(int x=-1024;x<1024;x++) {
        float a[2],b[2];game_screen_point(a,x,224);game_screen_point(b,x,224);
        assert(a[0]==x+.5f && a[1]==224.5f && a[0]==b[0] && a[1]==b[1]);
    }
    assert(game_screen_uv(0)==.5f/256 && game_screen_uv(255)==255.5f/256);
    assert(game_screen_overlay_edges(-160,-112,256,224,320,224)==1);
    assert(game_screen_overlay_edges(96,-112,64,224,320,224)==2);
    assert(game_screen_overlay_edges(-160,-112,320,224,320,224)==3);
    assert(game_screen_overlay_edges(-160,-111,256,224,320,224)==0);
    assert(game_screen_overlay_edges(-159,-112,64,224,320,224)==0);
    for(int origin=-1024;origin<=0;origin+=128) {
        assert(game_screen_triangle_size_valid(origin,origin,origin+1023,origin,origin,origin+511));
        assert(!game_screen_triangle_size_valid(origin,origin,origin+1024,origin,origin,origin+511));
        assert(!game_screen_triangle_size_valid(origin,origin,origin+1023,origin,origin,origin+512));
    }
    assert(!game_screen_triangle_size_valid(0,-300,10,0,0,300));
    assert(game_screen_triangle_size_valid(0,-100,10,0,0,400));
    puts("PASS: all packed coordinate sign bits, exact shared native sample positions and texel centers");
}
