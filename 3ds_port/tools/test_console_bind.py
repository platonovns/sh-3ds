"""Exercise the actual console binding for both lower-buffer parities."""
from pathlib import Path
import subprocess,tempfile
p=Path(__file__).resolve().parents[1]
s=(p/'source/main_game.c').read_text()
fn=s[s.index('static void lower_console_bind(void)'):s.index('static void lower_console(void)')]
driver=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint16_t u16;
typedef struct {u16 *frameBuffer;} PrintConsole;
enum {GFX_BOTTOM=1,GFX_LEFT=0};
static PrintConsole active,template_console,*lower_console_instance,*selected;
static u16 frames[2][4];static int current,double_buffer,lower_owns;
static void gfxSetDoubleBuffering(int screen,bool enabled) {assert(screen==1);double_buffer=enabled;}
static void *gfxGetFramebuffer(int screen,int eye,void *w,void *h) {
    assert(screen==1 && eye==0 && !w && !h);return frames[current ^ double_buffer];
}
static void consoleSelect(PrintConsole *console) {selected=console;}
'''+fn+r'''
int main(void) {
 lower_console_instance=&active;template_console.frameBuffer=frames[0];
 for(current=0;current<2;current++) {
   double_buffer=1;lower_owns=1;selected=0;active.frameBuffer=0;
   lower_console_bind();assert(!double_buffer && !lower_owns);
   assert(selected==&active && active.frameBuffer==frames[current]);
   assert(template_console.frameBuffer==frames[0]);
 }
 puts("PASS: active console bound to visible buffer for both parities");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-console-') as temp:
    root=Path(temp);source=root/'test.c';exe=root/'test';source.write_text(driver)
    subprocess.run(['cc','-std=c11','-Wall','-Werror',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
