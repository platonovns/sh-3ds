"""Exercise the production APT callback and assert it never acquires audio locks."""
import subprocess
import tempfile
from pathlib import Path
port=Path(__file__).resolve().parents[1]
s=(port/'source/game_audio_ndsp.c').read_text()
callback=s[s.index('static void apt_callback('):s.index('int32_t game_audio_init(')]
fmv=(port/'source/game_fmv.c').read_text()
fmv_hook=fmv[fmv.index('static void apt_hook('):fmv.index('static void present(')]
assert 'ndspChnSetPaused' not in fmv_hook and 'LightLock' not in fmv_hook
driver=r"""
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef int APT_HookType;
#define APTHOOK_ONSUSPEND 1
#define APTHOOK_ONSLEEP 2
#define APTHOOK_ONRESTORE 3
#define APTHOOK_ONWAKEUP 4
static uint32_t paused;
"""+callback+r"""
int main(void) {
    paused=1;apt_callback(APTHOOK_ONSUSPEND,0);assert(paused==3);
    apt_callback(APTHOOK_ONRESTORE,0);assert(paused==1);
    paused=0;apt_callback(APTHOOK_ONSLEEP,0);assert(paused==2);
    apt_callback(APTHOOK_ONWAKEUP,0);assert(paused==0);
    puts("PASS: APT audio callback uses no blocking calls and preserves manual pause");
}
"""
with tempfile.TemporaryDirectory(prefix='sh-apt-audio-') as name:
    root=Path(name); c=root/'test.c'; binary=root/'test'; c.write_text(driver)
    subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror',str(c),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
