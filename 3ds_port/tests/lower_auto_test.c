#include "game_lower_policy.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    assert(lower_backlight_policy(0,11,0,1,1,0)==1);
    assert(lower_backlight_policy(1,7,0,0,0,1)==0);
    assert(lower_backlight_policy(1,11,0,0,0,1)==1);
    assert(lower_backlight_policy(1,11,0,0,0,0)==0);
    assert(lower_backlight_policy(1,11,2,0,1,0)==1);
    assert(lower_backlight_policy(1,11,2,1,1,0)==1);
    assert(lower_backlight_policy(1,14,0,1,1,0)==1);
    assert(lower_backlight_policy(1,19,0,0,1,0)==1);
    assert(lower_backlight_policy(1,14,0,0,1,0)==1);
    assert(lower_backlight_policy(1,11,0,1,1,1)==0);
    assert(lower_backlight_policy(1,9,0,0,0,1)==0);
    assert(lower_backlight_policy(1,11,5,0,1,0)==-1);
    assert(lower_backlight_policy(1,12,0,0,0,1)==1);
    assert(lower_backlight_policy(1,12,0,0,1,0)==0);
    for(unsigned sys=0;sys<=14;sys++)if(sys==0 || sys==7 || sys==10 || sys==11 || sys==12 || sys==14) {
        assert(lower_backlight_policy(1,11,sys,0,1,1)==1);
        assert(lower_backlight_policy(1,11,sys,0,1,0)==0);
        assert(lower_backlight_policy(1,11,sys,1,1,1)==0);
    }
    assert(hp_led_hold_policy(11,5,0,0));
    assert(hp_led_hold_policy(11,0,0,0));
    assert(hp_led_hold_policy(14,0,0,0));
    assert(hp_led_hold_policy(15,0,0,0));
    assert(!hp_led_hold_policy(11,5,1,0));
    assert(!hp_led_hold_policy(6,0,0,0));
    for(unsigned automatic=0;automatic<2;automatic++) {
        assert(lower_backlight_content_policy(automatic,11,0,0,0,1,0,0)==0);
        assert(lower_backlight_content_policy(automatic,11,0,0,0,1,0,1)==1);
        assert(lower_backlight_content_policy(automatic,14,0,0,0,0,0,0)==1);
        assert(lower_backlight_content_policy(automatic,11,2,0,0,0,0,0)==1);
        assert(lower_backlight_content_policy(automatic,11,0,0,0,0,1,1)==lower_backlight_policy(automatic,11,0,0,0,0));
    }
    puts("PASS: lower backlight gameplay, status, cutscene, FMV and transitions");
}
