"""Exercise the production card-change gate with controllable pending work."""
from pathlib import Path
import subprocess, tempfile

p = Path(__file__).resolve().parents[1]
source = (p/'source/game_services.c').read_text()
body = source[source.index('int Game3ds_CardChange('):source.index('\ns_WorldGfxWork')]
fixture = r'''
#include <assert.h>
#include <stdio.h>
enum { MemCardWorkState_Idle=0, MemCardWorkState_Init=1, MemCardIoMode_Init=0, MemCardProcess_None=0 };
struct { int state, MemCardIoMode, stateStep; } g_MemCard_Work;
struct { struct { int processId; } saveWork[2]; } g_MemCard_SaveWork;
static int g_MemCard_AvailibityStatus=1;
static int steps, remaining, mount_ok, mounted, resets;
void MemCard_StateInit(void) {g_MemCard_Work.state=0;}
void MemCard_StateUpdate(void) { steps++; if(remaining>0 && !--remaining)g_MemCard_Work.state=0; }
int game_card_select(unsigned card) { mounted++; return mount_ok && card==2; }
int game_card_select_error(void) { return 60042; }
void MemCard_SysDisable(void) { resets++; }
void MemCard_SysInit(void) { resets++; }
void MemCard_SysInit2(void) { resets++; }
void MemCard_InitStatus(void) { resets++; }
''' + body + r'''
int main(void) {
    mount_ok=1;g_MemCard_Work.state=1;remaining=3;
    assert(Game3ds_CardChange(2) && steps==3 && mounted==1 && resets==4);
    steps=mounted=resets=0;g_MemCard_Work.state=1;remaining=-1;
    assert(Game3ds_CardChange(2)==-5000 && steps==64 && !mounted && !resets);
    steps=mounted=resets=0;g_MemCard_Work.state=0;mount_ok=0;
    assert(Game3ds_CardChange(2)==-60042 && mounted==1 && !resets);
    steps=mounted=resets=0;g_MemCard_Work.state=1;mount_ok=1;g_MemCard_AvailibityStatus=0;
    assert(Game3ds_CardChange(2)==1 && steps==0 && mounted==1 && resets==4);
    steps=mounted=resets=0;g_MemCard_Work.state=1;g_MemCard_Work.MemCardIoMode=3;remaining=-1;
    assert(Game3ds_CardChange(2)==-4300 && steps==64 && !mounted && !resets);
    steps=mounted=resets=0;g_MemCard_Work.state=1;g_MemCard_Work.MemCardIoMode=0;g_MemCard_SaveWork.saveWork[0].processId=3;
    assert(Game3ds_CardChange(2)==-4000 && steps==64 && !mounted && !resets);
    puts("PASS: pending card work completes before switch; busy or failed mount cannot reset state");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-card-change-') as temp:
    root=Path(temp); (root/'test.c').write_text(fixture)
    subprocess.run(['cc','-std=c11','-Wall','-Werror',str(root/'test.c'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],check=True)

card = (p/'source/game_card.c').read_text()
card = card[card.index('static struct {unsigned block,offset,size,flags;} handles'):card.index('/* This card event loop')]
fixture = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "game_card_image.h"
''' + card + r'''
int main(void) {
    char path[64]; card_path(1,path);assert(game_card_mount(path));
    assert(game_card_create("TEST",1));
    handles[0].block=1;assert(!game_card_select(2) && game_card_select_error()==200);handles[0].block=0;
    assert(game_card_select(2) && !game_card_find("TEST"));
    assert(game_card_create("OTHER",1));
    assert(game_card_select(1) && game_card_find("TEST") && !game_card_find("OTHER"));
    assert(game_card_select(2) && game_card_find("OTHER") && !game_card_find("TEST"));
    FILE *bad=fopen("sdmc:/3ds/silenthill/memcard3.mcr","wb");assert(bad);fputs("bad",bad);fclose(bad);
    assert(!game_card_select(3) && game_card_select_error()==40000 && game_card_find("OTHER"));
    puts("PASS: selection preserves isolated card files and rolls back failed mounts");
}
'''
with tempfile.TemporaryDirectory(prefix='sh-card-select-') as temp:
    root=Path(temp); (root/'sdmc:/3ds/silenthill').mkdir(parents=True)
    (root/'test.c').write_text(fixture)
    subprocess.run(['cc','-std=gnu11','-I'+str(p/'include'),str(root/'test.c'),
                    str(p/'source/game_card_image.c'),'-o',str(root/'test')],check=True)
    subprocess.run([str(root/'test')],cwd=root,check=True)
