"""Run the production backlight state machine against a mocked GSPLCD clock."""
import subprocess
import tempfile
from pathlib import Path

port = Path(__file__).resolve().parents[1]
source = (port / 'source/main_game.c').read_text()
block = source[source.index('static unsigned lower_auto='):source.index('#if defined(SH_3DS_FMV)', source.index('static unsigned lower_auto='))]
driver = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include "game_lower_policy.h"
typedef int Result; typedef int APT_HookType; typedef int aptHookCookie; typedef unsigned int u32;
#define APTHOOK_ONSUSPEND 0
#define APTHOOK_ONSLEEP 3
#define APTHOOK_ONEXIT 4
#define APTHOOK_ONWAKEUP 1
#define APTHOOK_ONRESTORE 2
#define GSPLCD_SCREEN_BOTTOM 2
#define SYSCLOCK_ARM11 16000ULL
#define R_SUCCEEDED(x) ((x)==0)
#define R_FAILED(x) ((x)!=0)
static uint64_t now;static unsigned calls_on,calls_off,calls_brightness,calls_read,calls_led,brightness=96;
static unsigned hp_led_resume;static int hp_led_bucket;
static unsigned game_map_enabled=1,game_ammo_display=1;
static volatile unsigned hardware_suspended;
static int active=1,jumping;
static int hardware_foreground(void){return !hardware_suspended && active && !jumping;}
static int lcd_session;static unsigned lcd_acquires,lcd_releases;
static Result gspLcdInit(void){assert(!lcd_session);lcd_session=1;lcd_acquires++;return 0;}
static void gspLcdExit(void){assert(lcd_session);lcd_session=0;lcd_releases++;}
static void hp_led_set(int x){(void)x;calls_led++;hp_led_resume=0;}
static uint64_t svcGetSystemTick(void){return now;}
static Result GSPLCD_PowerOnBacklight(unsigned x){assert(lcd_session);(void)x;calls_on++;return 0;}
static Result GSPLCD_PowerOffBacklight(unsigned x){assert(lcd_session);(void)x;calls_off++;return 0;}
static Result GSPLCD_GetBrightness(unsigned x,unsigned *v){assert(lcd_session);(void)x;calls_read++;*v=brightness;return 0;}
static Result GSPLCD_SetBrightnessRaw(unsigned x,unsigned v){assert(lcd_session);(void)x;calls_brightness++;brightness=v;return 0;}
static void game3ds_recoverable(const char *s,int e){(void)s;(void)e;assert(0);}
''' + block + r'''
int main(void) {
    lower_lcd_ready=1;lower_lcd_normal=lower_lcd_level=96;
    jumping=1;game3ds_lower_backlight_observe(7,0,0,0,1);game3ds_lower_backlight_tick();
    assert(!calls_on && !calls_off && !calls_brightness && !calls_read && !calls_led && !lcd_acquires);
    lower_apt_hook(APTHOOK_ONSUSPEND,0);jumping=0;active=0;
    lower_backlight(1);game3ds_lower_backlight_observe(7,0,0,0,1);
    assert(!calls_on && !calls_off && !calls_brightness && !calls_read && !calls_led);
    lower_apt_hook(APTHOOK_ONRESTORE,0);game3ds_lower_backlight_tick();
    assert(!calls_on && !calls_off && !calls_brightness && !calls_read && !calls_led);
    active=1;game3ds_lower_backlight_tick();
    assert(calls_off==1 && calls_led==1 && !lower_lcd_on);
    calls_off=calls_led=0;lower_lcd_on=1;lower_lcd_target=1;
    game3ds_lower_backlight_observe(7,0,0,0,1);
    for(int i=0;i<20;i++){now+=SYSCLOCK_ARM11/32;game3ds_lower_backlight_tick();}
    assert(calls_off==1 && !lower_lcd_on);
    game3ds_lower_backlight_observe(11,0,0,0,1);now+=SYSCLOCK_ARM11/10;
    game3ds_lower_backlight_observe(10,0,0,0,1);now+=SYSCLOCK_ARM11/2;
    game3ds_lower_backlight_tick();assert(!calls_on);
    game3ds_lower_backlight_observe(19,0,0,1,0);game3ds_lower_backlight_tick();assert(calls_on==1);
    game3ds_lower_backlight_observe(11,0,0,0,0);
    for(int i=0;i<20;i++){now+=SYSCLOCK_ARM11/32;game3ds_lower_backlight_tick();}
    assert(!lower_lcd_on);
    lower_apt_hook(APTHOOK_ONWAKEUP,0);game3ds_lower_backlight_tick();assert(!lower_lcd_on && calls_off==3);
    game3ds_lower_backlight_observe(11,0,0,0,1);
    now+=SYSCLOCK_ARM11/4;game3ds_lower_backlight_observe(11,0,0,0,1);assert(lower_lcd_on);
    lower_lcd_normal=0;lower_lcd_on=0;lower_lcd_target=0;lower_lcd_pending=0;
    game3ds_lower_backlight_observe(11,0,0,0,1);now+=SYSCLOCK_ARM11/4;
    game3ds_lower_backlight_observe(11,0,0,0,1);assert(lower_lcd_on);
    /* HOME while off: restore system display, release service, retain target. */
    lower_lcd_on=0;lower_lcd_target=0;lower_lcd_normal=96;lower_lcd_level=16;
    unsigned before_on=calls_on,before_off=calls_off,before_brightness=calls_brightness;
    jumping=1;lower_apt_hook(APTHOOK_ONSUSPEND,0);
    assert(calls_on==before_on+1 && calls_brightness==before_brightness+1);
    assert(lower_lcd_on && lower_lcd_level==96 && !lower_lcd_target && !lcd_session);
    game3ds_lower_backlight_tick();assert(calls_off==before_off);
    jumping=0;lower_apt_hook(APTHOOK_ONRESTORE,0);game3ds_lower_backlight_tick();
    assert(calls_off==before_off+1 && !lower_lcd_on && !lower_lcd_target);
    /* HOME during fade: restore brightness even if backlight is already on. */
    lower_lcd_on=1;lower_lcd_level=32;lower_lcd_target=0;
    before_on=calls_on;before_brightness=calls_brightness;jumping=1;
    lower_apt_hook(APTHOOK_ONSUSPEND,0);
    assert(calls_on==before_on && calls_brightness==before_brightness+1);
    assert(lower_lcd_level==96 && !lcd_session);
    hardware_suspended=0;jumping=0;active=1;lower_lcd_resume=0;lower_lcd_normal=0;
    lower_lcd_on=1;lower_lcd_target=1;game_map_enabled=0;game_ammo_display=2;
    game3ds_lower_backlight_observe(11,0,0,0,1);assert(!lower_lcd_on);
    game3ds_lower_backlight_observe(14,0,0,0,0);assert(lower_lcd_on);
    game3ds_lower_backlight_observe(11,0,0,0,1);assert(!lower_lcd_on);
    game3ds_lower_backlight_observe(11,2,0,0,0);assert(lower_lcd_on);
    game3ds_lower_backlight_observe(11,0,0,0,1);assert(!lower_lcd_on);
    game_ammo_display=0;game3ds_lower_backlight_observe(11,0,0,0,0);
    now+=SYSCLOCK_ARM11/4;game3ds_lower_backlight_observe(11,0,0,0,0);assert(lower_lcd_on);
    assert(lcd_acquires && lcd_acquires==lcd_releases && !lcd_session);
    puts("PASS: HOME/suspend service gating, resume, fade, status and no-map");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-lcd-') as name:
    root = Path(name); c = root / 'lcd.c'; binary = root / 'lcd'; c.write_text(driver)
    subprocess.run(['gcc', '-std=c11', '-Wall', '-Wextra', '-I' + str(port / 'include'), str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
