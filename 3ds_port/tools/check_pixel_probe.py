#!/usr/bin/env python3
"""Compare native Azahar pixels with a small PSX word/STP/ABR/mask oracle."""
import json,struct,sys,zlib
from pathlib import Path
def png(path):
    blob=Path(path).read_bytes(); assert blob[:8]==b'\x89PNG\r\n\x1a\n'
    pos=8; compressed=b''
    while pos<len(blob):
        size=struct.unpack_from('>I',blob,pos)[0]; typ=blob[pos+4:pos+8]; data=blob[pos+8:pos+8+size]
        assert zlib.crc32(typ+data)==struct.unpack_from('>I',blob,pos+8+size)[0]
        if typ==b'IHDR': w,h,bits,color,_,_,interlace=struct.unpack('>IIBBBBB',data)
        if typ==b'IDAT': compressed+=data
        pos+=size+12
    assert bits==8 and color in (2,6) and not interlace
    channels=3 if color==2 else 4; raw=zlib.decompress(compressed); stride=w*channels
    rows=[]; prev=bytearray(stride); pos=0
    for y in range(h):
        kind=raw[pos]; pos+=1; row=bytearray(raw[pos:pos+stride]); pos+=stride
        for i in range(stride):
            a=row[i-channels] if i>=channels else 0; b=prev[i]; c=prev[i-channels] if i>=channels else 0
            if kind==1: value=a
            elif kind==2: value=b
            elif kind==3: value=(a+b)//2
            elif kind==4:
                p=a+b-c; pa=abs(p-a); pb=abs(p-b); pc=abs(p-c)
                value=a if pa<=pb and pa<=pc else b if pb<=pc else c
            else: assert kind==0; value=0
            row[i]=(row[i]+value)&255
        rows.append(row); prev=row
    return lambda x,y:list(rows[y][x*channels:x*channels+3])
get=png(sys.argv[1]); back=[64,128,192]; cells=[]
if '--surface' in sys.argv:
    original_get=get
    get=lambda x,y:original_get(int(40+x*.8),y)
if '--order' in sys.argv:
    for mode in range(5):cells.append({'mode':mode,'actual':get(190,27+mode*46),'expected':[132,132,132]})
elif '--mask' in sys.argv:
    expected=[back,[0,0,0],[255,64,64],[0,255,0]]
    for c,color in enumerate(expected): cells.append({'column':c,'actual':get(80+c*80,120),'expected':color})
else:
    precision='--precision' in sys.argv
    front=[None,[0,0,0],[0,255,0],[255,0,0]] if precision else [None,[0,0,0],[255,0,0],[0,255,0]]
    for mode in range(5):
        for c,color in enumerate(front):
            stp=c>0 if precision else c in (1,3)
            if color is None: expected=back
            elif not mode or not stp: expected=color
            elif mode==1: expected=[(b+f)//2 for b,f in zip(back,color)]
            elif mode==2: expected=[min(255,b+f) for b,f in zip(back,color)]
            elif mode==3: expected=[max(0,b-f) for b,f in zip(back,color)]
            else: expected=[min(255,b+f//4) for b,f in zip(back,color)]
            cells.append({'mode':mode,'column':c,'actual':get(52+c*96,27+mode*46),'expected':expected})
for cell in cells: cell['max_error']=max(abs(a-b) for a,b in zip(cell['actual'],cell['expected']))
report={'source':sys.argv[1],'kind':'framebuffer mask' if '--mask' in sys.argv else '0000/STP/ABR',
    'passed':all(c['max_error']<=2 for c in cells),'cells':cells}
print(json.dumps(report,indent=2))
if '--expect-broken' in sys.argv: assert not report['passed']
else: assert report['passed'],report
