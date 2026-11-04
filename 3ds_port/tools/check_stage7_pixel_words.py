#!/usr/bin/env python3
"""Independent 15-bit oracle for actual native PICA readback probe samples."""
import json,sys
from pathlib import Path
p=Path(sys.argv[1]);lines=p.read_text().splitlines();kind=lines[0].split('=')[1]
assert lines[-1]=='readback=PASS'
back=[64,128,192];cells=[]
for line in lines[1:-1]:
    r,c,word=line.split('=')[1].split(',');r=int(r);c=int(c);word=int(word,16)
    if kind=='order':expected=[132,132,132]
    elif kind=='mask':expected=[back,[0,0,0],[255,64,64],[0,255,0]][c]
    else:
        precision=kind=='precision'
        front=[None,[0,0,0],[0,255,0],[255,0,0]] if precision else [None,[0,0,0],[255,0,0],[0,255,0]]
        color=front[c];stp=c>0 if precision else c in (1,3)
        if color is None:expected=back
        elif not r or not stp:expected=color
        elif r==1:expected=[(b+f)//2 for b,f in zip(back,color)]
        elif r==2:expected=[min(255,b+f) for b,f in zip(back,color)]
        elif r==3:expected=[max(0,b-f) for b,f in zip(back,color)]
        else:expected=[min(255,b+f//4) for b,f in zip(back,color)]
    actual=[word&31,(word>>5)&31,(word>>10)&31];want=[v>>3 for v in expected]
    error=max(abs(a-b) for a,b in zip(actual,want))
    cells.append({'row':r,'column':c,'actual_5bit':actual,'expected_5bit':want,'error':error})
    assert error<=1,(kind,r,c,actual,want)
    if kind=='mask':assert word&0x8000,(kind,c,hex(word))
assert len(cells)==(5 if kind=='order' else 4 if kind=='mask' else 20)
print(json.dumps({'status':'PASS','kind':kind,'source':str(p),'native_PICA_readback':True,'quantization_tolerance_5bit':1,'cells':cells},indent=2))
