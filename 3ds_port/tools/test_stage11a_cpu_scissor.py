"""Compare effective SDK scissor and empty-clip state to frozen F1 per call."""
import json,subprocess,zipfile
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
def function(text):
    start=text.index('bool render3ds_set_scissor(');begin=text.index('{',start);depth=1;end=begin+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
with zipfile.ZipFile(PORT/'baselines/stage11a-tracefix-c4c8ac8829ac3fac.zip') as z:
    before=z.read('3ds_port/source/render_3ds.c').decode()
after=(PORT/'source/render_3ds.c').read_text()
folder=PORT/'build/stage11a-cpu-host';folder.mkdir(exist_ok=True)
source='''#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
enum{GPU_SCISSOR_NORMAL=1};
typedef struct {bool in_frame,native_frame,empty_clip,scissor_valid;struct{int width;}native_color;int scissor[4];} State;
static State ref,cur;
static int old_sdk[5],new_sdk[5];static unsigned old_calls,new_calls;
static void set(int *state,unsigned *calls,int mode,int a,int b,int c,int d){int x[]={mode,a,b,c,d};memcpy(state,x,sizeof(x));(*calls)++;}
#define C3D_SetScissor(...) set(old_sdk,&old_calls,__VA_ARGS__)
'''+function(before).replace('render3ds_set_scissor','reference').replace('renderer.','ref.')+'''
#undef C3D_SetScissor
#define C3D_SetScissor(...) set(new_sdk,&new_calls,__VA_ARGS__)
'''+function(after).replace('render3ds_set_scissor','candidate').replace('renderer.','cur.')+'''
int main(){unsigned seed=0x11a;
 for(unsigned frame=0;frame<200;frame++){
  memset(&ref,0,sizeof(ref));memset(&cur,0,sizeof(cur));
  ref.in_frame=cur.in_frame=true;ref.native_frame=cur.native_frame=frame%2;
  ref.native_color.width=cur.native_color.width=frame%3?320:512;
  memset(old_sdk,0,sizeof(old_sdk));memset(new_sdk,0,sizeof(new_sdk));
  int v[4]={0,0,320,240};
  for(unsigned i=0;i<512;i++){
   if(i%8==0)for(unsigned j=0;j<4;j++){seed=seed*1664525u+1013904223u;v[j]=(int)(seed%900)-200;}
   assert(reference(v[0],v[1],v[2],v[3])==candidate(v[0],v[1],v[2],v[3]));
   assert(ref.empty_clip==cur.empty_clip);assert(!memcmp(old_sdk,new_sdk,sizeof(old_sdk)));
  }
 }
 printf("PASS: 102400 calls, effective SDK clip and empty state exact; SDK calls %u -> %u\\n",old_calls,new_calls);
}
'''
fixture=folder/'scissor.c';fixture.write_text(source);exe=folder/'scissor'
subprocess.run(['gcc','-O2','-fsanitize=address,undefined',str(fixture),'-o',str(exe)],check=True)
run=subprocess.run([str(exe)],capture_output=True,text=True,check=True);assert not run.stderr
report=dict(status='PASS',scope=__doc__,result=run.stdout.strip())
(PORT/'reports/stage11a-cpu-scissor.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
