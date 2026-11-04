#ifndef SH_GAME_FEEDBACK_CADENCE_H
#define SH_GAME_FEEDBACK_CADENCE_H
#include <stdint.h>
typedef struct {uint32_t tick,frame,period,debt;int started,decay;} GameFeedbackCadence;
static inline int game_feedback_decay(GameFeedbackCadence *c,uint32_t now,uint32_t frame,uint32_t period)
{
    if(!period)period=1;
    if(c->started && c->frame==frame)return c->decay;
    uint32_t elapsed=now-c->tick;
    if(!c->started || c->period!=period || frame-c->frame!=1 || elapsed>30) {
        c->debt=0;c->decay=1;
    } else {
        c->debt+=elapsed;c->decay=c->debt>=period;
        /* One original RGB5 feedback iteration per image. A slow frame must
         * not accumulate a burst of hidden decay iterations afterward. */
        if(c->decay)c->debt%=period;
    }
    c->started=1;c->tick=now;c->frame=frame;c->period=period;
    return c->decay;
}
#endif
