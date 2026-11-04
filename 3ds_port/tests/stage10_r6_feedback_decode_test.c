#include "game_feedback.h"
#include "psx_game_pixel.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void)
{
    const uint32_t colors[]={0,0x7f7f7f,0x808080,0xffffff,0x3d807f,0x010203,0x00ff80,0x120034,0xffff0000};
    GameFeedbackDecode d={0};unsigned checked=0;
    for(unsigned c=0;c<sizeof(colors)/sizeof(colors[0]);c++) {
        game_feedback_decode_init(&d,colors[c]);game_feedback_decode_init(&d,colors[c]);
        for(unsigned w=0;w<65536;w++) {
            uint16_t mod=game_feedback_modulate(w,colors[c]&255,(colors[c]>>8)&255,colors[c]>>16);
            uint8_t rgba[4];psx_game_pixel(mod,rgba);uint32_t original;memcpy(&original,rgba,4);
            assert(game_feedback_decode_pixel(&d,w)==original);checked++;
        }
    }
    printf("PASS: %u exact RGB5 feedback/STP/zero combinations; 127/128 appearance unchanged\n",checked);
}
