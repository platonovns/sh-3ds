"""Run the retail weapon selector and observe its actual table writes."""
import json,struct
from retail_mips import Retail,SYMBOLS,PORT
from unicorn import UC_HOOK_MEM_WRITE
r=Retail();writes=[]
for name in ('Fs_QueueStartRead','func_8007F14C'):
    if name in SYMBOLS:r.hook(name,lambda *_:r.ret())
r.uc.hook_add(UC_HOOK_MEM_WRITE,lambda u,a,p,n,v,c:writes.append((hex(p),n,hex(v))),begin=0x80000000,end=0x80300000)
cases=[]
for weapon in (0,3,4,32,33,34,35):
    r.uc.mem_write(0xb9fc0+0x47,bytes([weapon]))
    writes.clear();r.call('GameFs_WeaponInfoUpdate')
    cases.append(dict(weapon=weapon,values=[struct.unpack('<h',r.uc.mem_read(a,2))[0] for a in (0xaf5c6,0xaf624,0xaf626)],writes=list(writes)))
report=dict(cases=cases,table_pointer=hex(struct.unpack('<I',r.uc.mem_read(0x297b8,4))[0]))
(PORT/'reports/stage10-retail-animation-aliases.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
