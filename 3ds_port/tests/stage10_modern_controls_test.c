#include "game_modern_controls.h"
#include "game_pad.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    for(unsigned mode=0;mode<3;mode++)for(unsigned c=0;c<16;c++) {
        unsigned keys=c<<24;int x,z;
        assert(!game_control_vector(mode,keys,0,0,&x,&z));
        assert(!game_pad_buttons(keys));
        int active=game_control_vector(mode,keys,83,119,&x,&z);
        assert(active==(mode!=GAME_CONTROL_TANK));
        if(active)assert(x==83 && z==119);
        active=game_control_vector(mode,keys|(1u<<1),83,119,&x,&z);
        assert(active==(mode!=GAME_CONTROL_TANK));
        if(active)assert(x==83 && z==119);
        active=game_control_vector(mode,keys|(1u<<5),83,119,&x,&z);
        assert(active==(mode==GAME_CONTROL_MODERN));
        if(active)assert(x==-1 && z==0);
        assert(game_pad_buttons(keys|(1u<<5)|(1u<<30))==(1u<<7));
    }
    puts("PASS: three-mode vector contract; C-stick isolation; D-pad priority.");
}
