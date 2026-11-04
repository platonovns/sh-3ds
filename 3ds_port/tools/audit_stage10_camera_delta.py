"""Require identical loadable bytes outside the tested camera function and build ID.
This permits retaining the full foundation run across a camera-axis-only fix,
without claiming those tests were re-run on a different ELF.
"""
import hashlib,json,os,re,struct,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1]
before=p/'build/stage10-r4-axis-reference/game.elf';after=p/'silenthill_game.elf'
def loads(data):
    off=struct.unpack_from('<I',data,28)[0];size,count=struct.unpack_from('<HH',data,42)
    out=[]
    for i in range(count):
        typ,pos,addr,_,length,memory,flags,align=struct.unpack_from('<8I',data,off+i*size)
        if typ==1:out.append((addr,memory,flags,bytearray(data[pos:pos+length])))
    return out
def function(file):
    raw=subprocess.check_output([os.environ['DEVKITARM']+'/bin/arm-none-eabi-nm','-S',str(file)],text=True)
    row=next(line.split() for line in raw.splitlines() if line.split()[-1]=='Game3ds_CameraLook')
    return int(row[0],16),int(row[1],16)
a,b=before.read_bytes(),after.read_bytes();fa,fb=function(before),function(after)
assert fa==fb,('Camera function layout changed; rerun the complete suite',fa,fb)
la,lb=loads(a),loads(b);assert len(la)==len(lb)
ids=[];changed=0
for left,right in zip(la,lb):
    assert left[:3]==right[:3] and len(left[3])==len(right[3]),'Runtime layout changed'
    addr=left[0];x,y=left[3],right[3]
    changed+=sum(v!=w for v,w in zip(x,y))
    found=[list(re.finditer(rb'stage10\.0-src-[a-f0-9]{16}',v)) for v in (x,y)]
    assert [(m.start(),m.end()) for m in found[0]]==[(m.start(),m.end()) for m in found[1]]
    for side,matches in zip((x,y),found):
        for match in matches:
            ids.append(match.group().decode());side[match.start():match.end()]=bytes(match.end()-match.start())
    start=max(fa[0],addr);end=min(fa[0]+fa[1],addr+len(x))
    if start<end:
        x[start-addr:end-addr]=bytes(end-start);y[start-addr:end-addr]=bytes(end-start)
    assert x==y,'Loadable bytes changed outside camera function/build ID; rerun the complete suite'
report=dict(status='PASS',before_elf_sha256=hashlib.sha256(a).hexdigest(),after_elf_sha256=hashlib.sha256(b).hexdigest(),
    changed_loadable_bytes=changed,function=dict(name='Game3ds_CameraLook',address=hex(fa[0]),bytes=fa[1]),
    build_ids=sorted(set(ids)),other_loadable_bytes_identical=True,
    requirement='Re-run complete camera/physical-pad tests on final ELF; retain prior foundation results with their actual ELF hash.',hardware_accepted=False)
(p/'reports/stage10-r4-camera-delta.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
