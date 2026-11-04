#include "game_feedback_cadence.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    for(unsigned parity=0;parity<2;parity++) {
        GameFeedbackCadence c={0};unsigned count=0;
        for(unsigned i=0;i<60;i++)count+=game_feedback_decay(&c,parity+i*2,i,2);
        assert(count==60); /* 30 FPS, either initial field phase. */
        c=(GameFeedbackCadence){0};count=0;
        for(unsigned i=0;i<60;i++)count+=game_feedback_decay(&c,parity+i,i,2);
        assert(count==30); /* 60 FPS retains retail's 30 decay steps/second. */
    }
    GameFeedbackCadence c={0};unsigned now=1;
    for(unsigned i=0;i<120;i++) {
        now+=(i%5==0)?3:2;
        assert(game_feedback_decay(&c,now,i,2));
        assert(game_feedback_decay(&c,now+1,i,2)); /* Same decision for all tiles. */
    }
    puts("PASS: field phase, 30/60 FPS, irregular cadence, one decision per image.");
}
