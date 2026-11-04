#include "game_lower_policy.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    assert(lower_owner(11,0,0,0,0)==LOWER_GAME_DRAW);
    assert(lower_owner(11,0,0,1,0)==LOWER_START);
    assert(lower_owner(11,0,0,1,1)==LOWER_START);
    assert(lower_owner(11,7,0,0,0)==LOWER_GAME_HOLD);
    assert(lower_owner(11,10,0,0,0)==LOWER_GAME_HOLD);
    assert(lower_owner(12,0,0,0,0)==LOWER_GAME_HOLD);
    assert(lower_owner(11,5,0,0,0)==LOWER_GAME_HOLD);
    assert(lower_owner(11,6,0,0,0)==LOWER_GAME_HOLD);
    assert(lower_owner(10,6,0,0,0)==LOWER_GAME_HOLD);
    assert(lower_owner(11,0,0,0,1)==LOWER_GAME_HOLD);
    assert(lower_owner(11,0,0,0,0)==LOWER_GAME_DRAW);
    assert(lower_owner(11,3,0,0,0)==LOWER_SPECIAL);
    assert(lower_owner(11,4,0,0,0)==LOWER_SPECIAL);
    assert(lower_owner(11,8,0,0,0)==LOWER_SPECIAL);
    assert(lower_owner(11,0,1,0,0)==LOWER_SPECIAL);
    for(unsigned state=14;state<=20;state++)assert(lower_owner(state,0,0,0,0)==LOWER_SPECIAL);
    assert(lower_owner(9,0,0,0,0)==LOWER_SPECIAL);
    puts("PASS: START, interaction, bidirectional transition and fullscreen ownership");
}
