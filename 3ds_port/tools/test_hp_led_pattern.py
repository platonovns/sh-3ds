"""Verify the real LED bucket and one-shot transition pattern with a mock MCU."""
import subprocess
import tempfile
from pathlib import Path

port = Path(__file__).resolve().parents[1]
source = (port / 'source/main_game.c').read_text()
block = source[source.index('static bool hp_led_ready;'):source.index('typedef struct { uint32_t frame,map,room,game,step,sys,s0,s1,event;')]
driver = r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
#define R_SUCCEEDED(x) ((x)==0)
typedef struct {uint8_t delay,smoothing,loopDelay,blinkSpeed,redPattern[32],greenPattern[32],bluePattern[32];} InfoLedPattern;
static InfoLedPattern sent;static int calls;
static bool hardware_foreground(void){return true;}
static int MCUHWC_SetInfoLedPattern(const InfoLedPattern *p){sent=*p;calls++;return 0;}
''' + block + r'''
int main(void) {
    static const int health[7]={100,80,65,50,35,20,5};
    static const unsigned char colors[7][2]={{0,3},{1,3},{2,3},{3,3},{3,2},{3,1},{3,0}};
    hp_led_ready=1;
    for(int i=0;i<7;i++) {
        hp_led_update(health[i]*4096);
        assert(hp_led_bucket==i && sent.redPattern[31]==colors[i][0] && sent.greenPattern[31]==colors[i][1]);
    }
    hp_led_ready=1;hp_led_update(100*4096);assert(hp_led_bucket==0 && sent.greenPattern[31]==3 && !sent.redPattern[31]);
    assert(sent.delay==1 && sent.loopDelay==255 && sent.smoothing==1);
    hp_led_update(50*4096);assert(hp_led_bucket==3 && sent.redPattern[31]==3 && sent.greenPattern[31]==3);
    hp_led_update(0);assert(hp_led_bucket==6 && sent.redPattern[31]==3 && !sent.greenPattern[31]);
    hp_led_off();assert(hp_led_bucket==-1 && !sent.redPattern[31] && sent.redPattern[0]>0);
    int before=calls;hp_led_off();assert(calls==before);
    hp_led_resume=1;hp_led_off();assert(calls==before+1);
    puts("PASS: literal 0..3 HP colours, fade pattern and wake replay");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-led-') as name:
    root=Path(name); c=root/'led.c'; binary=root/'led'; c.write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
