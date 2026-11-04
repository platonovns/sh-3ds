"""Actual ARM XA observer: allocation failure, successful queue and close state."""
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
PORT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PORT.parent.parent/'.toolchain/python-deps'))
os.environ['SH_GAME_ELF']=str(PORT/'build/stage11a-lifetime/silenthill_stage11a_lifetime.elf')
fixture=PORT/'tools/test_stage9_r6_xa_arm.py'
source=fixture.read_text().split('items=[]')[0]
ns={'__file__':str(fixture),'__name__':'lifetime_xa_fixture'}
exec(compile(source,str(fixture),'exec'),ns)
r,g=ns['r'],ns['g'];out=0x24980000
def snapshot():
    r.uc.mem_write(out,bytes(64));r.call('stage11a_lifetime_xa',out)
    return list(struct.unpack('<16I',r.uc.mem_read(out,64)))
assert snapshot()[11]==0
item=tuple(map(int,(PORT/'build/stage9-r2-xa-items.txt').read_text().splitlines()[1].split()))
idx,lba,ticks,file,channel=item
r.bridge('PsyX_XAStream_Create',lambda *_:r.ret(0))
r.call('game_xa_start',lba,file,channel,ticks);r.call('game_xa_step')
failed=snapshot();assert failed[11]==0 and failed[3]==0
r.uc.hook_del(r.named_hooks.pop('PsyX_XAStream_Create'))
r.call('game_xa_start',lba,file,channel,ticks);r.call('game_xa_step')
loaded=snapshot();assert loaded[11]==1 and loaded[3]>0 and loaded[4]==16384
r.call('game_xa_cancel',1,0,0);r.call('game_xa_close');closed=snapshot();assert closed[11]==0 and closed[3]==0
r.call('game_audio_cd_close')
assert not r.failure and not r.invalid,(r.failure,r.invalid)
for handle in r.handles.values():handle.close()
result=dict(status='PASS',scope='LINKED_ARM_UNICORN_NOT_HARDWARE',
            allocation_failure_present=failed[11],successful_present=loaded[11],closed_present=closed[11],
            queued_after_real_bin_decode=loaded[3],elf_sha256=hashlib.sha256(g.game_elf.read_bytes()).hexdigest())
(PORT/'reports/stage11a-lifetime-xa-arm.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
