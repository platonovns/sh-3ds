#include "game_display.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    assert(game_display_world(1,0,0,0));
    assert(!game_display_world(1,0,1,0));
    assert(game_display_world(1,0,1,1));
    assert(!game_display_world(0,0,1,0));
    GameDisplayPlan game=game_display_plan(320,224,1,0);
    GameDisplayPlan image=game_display_plan(320,224,0,0);
    assert(game.width==400 && image.width==320);
    puts("PASS: gameplay remains wide and fullscreen authored backgrounds stay 4:3");
}
