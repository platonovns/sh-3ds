#include "game_feedback.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
int main(void)
{
    /* A 320-wide intermediate is read in two 16-bit texture pages. */
    assert(game_feedback_target_sprite(320,256,256,224,320,256,320,224));
    assert(game_feedback_target_sprite(576,256,64,224,320,256,320,224));
    assert(!game_feedback_target_sprite(576,256,65,224,320,256,320,224));
    assert(!game_feedback_target_sprite(0,256,256,224,320,256,320,224));
    float a[9]={40.5f,0,0,.5f/256,1-.5f/256};
    float b[9]={296.5f,0,0,256.5f/256,1-.5f/256};
    float c[9]={296.5f,0,0,.5f/256,1-.5f/256};
    float d[9]={360.5f,0,0,64.5f/256,1-.5f/256};
    game_feedback_target_vertex(a,0x115,320,256,40,-40);
    game_feedback_target_vertex(b,0x115,320,256,40,0);
    game_feedback_target_vertex(c,0x119,320,256,40,0);
    game_feedback_target_vertex(d,0x119,320,256,40,40);
    assert(a[0]==0.5f && b[0]==296.5f && c[0]==296.5f && d[0]==400.5f);
    assert(a[3]==.5f/512 && b[3]==296.5f/512 && c[3]==296.5f/512 && d[3]==400.5f/512);
    /* Exhaust all 32768 PS1 RGB colors and all modulator byte values. */
    for(unsigned c=0;c<256;c++)for(unsigned w=0;w<32768;w++) {
        unsigned v=game_feedback_modulate(w,c,c,c);
        for(unsigned k=0;k<3;k++) {
            unsigned expected=(((w>>(k*5))&31)*c)/128;
            if(expected>31)expected=31;
            assert(((v>>(k*5))&31)==expected);
        }
    }
    /* Every native sample, both source PSX pages, normal/death transitions:
     * reconstruct the interpolated source texel from actual bridge vertices.
     * 127/128 decays to black in <=31 passes without ever moving a pixel. */
    for(unsigned page_y=0;page_y<2;page_y++)for(unsigned wide=0;wide<2;wide++) {
        unsigned width=wide?400:320;
        for(unsigned tile=0;tile<2;tile++) {
            unsigned page=0x100+(page_y?0x10:0)+tile*4;
            float left[9]={tile*256+40.5f,8.5f,0,.5f/256,1-(page_y? .5f:32.5f)/256};
            game_feedback_vertex(left,page,width,240,320,224,40,8,page_y?256:32);
            for(unsigned x=0;x<width;x++)for(unsigned y=0;y<240;y++) {
                float u=left[3]+(x+.5f-left[0])/512;
                float v=left[4]-(y+.5f-left[1])/256;
                assert((unsigned)floorf(u*512)==x);
                assert((unsigned)floorf((1-v)*256)==y);
            }
        }
        for(unsigned original=0;original<32768;original++) {
            unsigned current=original;
            for(unsigned i=0;i<31;i++)current=game_feedback_modulate(current,127,127,127);
            assert(current==0);
        }
    }
    puts("PASS: 8388608 color/modulation cases; native identity mapping; repeated 31-pass fade");
}
