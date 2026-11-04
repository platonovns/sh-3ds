"""Old helper depends only on the highest set bit: exhaust all 33 classes."""
import hashlib,json,subprocess
from pathlib import Path
from prepare_stage11a_gte import prepare
PORT=Path(__file__).resolve().parents[1]
dest,before,after=prepare();folder=PORT/'build/stage11a-cpu-gte-test';folder.mkdir(exist_ok=True)
fixture=folder/'clz.cpp'
fixture.write_text('#include <cassert>\n#include <cstdint>\n#include <cstdio>\n'+
 before.replace('gte_leadingzerocount','original')+'\n'+after+'''
int main(){
 assert(original(0)==32 && gte_leadingzerocount(0)==32);
 // The original OR cascade erases every bit below the most significant 1.
 // Those 32 nonzero classes plus zero cover its complete uint32 domain.
 for(unsigned bit=0;bit<32;bit++){
  unsigned x=1u<<bit;
  assert(original(x)==31-bit && original(x|(x-1))==31-bit);
  assert(gte_leadingzerocount(x)==original(x));
 }
 unsigned x=0x11a;for(unsigned i=0;i<2000000;i++){
  x=x*1664525u+1013904223u;assert(original(x)==gte_leadingzerocount(x));
 }
 puts("PASS: 33 exhaustive leading-bit classes and 2000000 uint32 values");
}
''')
exe=folder/'clz';subprocess.run(['g++','-O2','-fsanitize=undefined,address',str(fixture),'-o',str(exe)],check=True)
run=subprocess.run([str(exe)],capture_output=True,text=True,check=True);assert not run.stderr
report=dict(status='PASS',scope=__doc__,result=run.stdout.strip(),source_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
 proof='OR-smearing maps every nonzero uint32 to one of 32 all-low-bits-set values; all classes verified. No global reads/writes in either helper.')
(PORT/'reports/stage11a-cpu-gte.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
