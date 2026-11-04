#!/usr/bin/env python3
from fractions import Fraction
from pathlib import Path
import json,math,sys
source=(Path(__file__).with_name('check_pixel_probe.py')).read_text()
reader={};exec(source[:source.index('\nget=png')],reader)
get=reader['png'](sys.argv[1]);expected=set()
for row in range(9):
    y=20+row*20
    triangles=[[(8,y-6),(120,y-6),(8,y)],[(120,y-6),(120,y-3),(8,y)],
       [(8,y),(64,y-1),(8,y+7)],[(64,y-1),(64,y+7),(8,y+7)],
       [(64,y-1),(120,y-3),(64,y+7)],[(120,y-3),(120,y+7),(64,y+7)]]
    for t in triangles:
        for sy in range(min(p[1] for p in t),max(p[1] for p in t)):
            edges=[]
            for a,b in zip(t,t[1:]+t[:1]):
                if min(a[1],b[1])<=sy<max(a[1],b[1]):
                    edges.append(Fraction(a[0])+Fraction((sy-a[1])*(b[0]-a[0]),b[1]-a[1]))
            if len(edges)==2:
                expected.update((x,sy) for x in range(math.ceil(min(edges)),math.ceil(max(edges))))
result={'reference':'Independent rational PSX integer-sample ceil-left/ceil-right, half-open Y scanlines','panels':{}}
for panel in (('surface',) if '--surface' in sys.argv else ('old','native')):
    errors=[];missing=extra=0
    for y in (range(240) if panel=='surface' else range(8,204)):
        for x in range(4,124):
            px,py=(40+x,y) if panel=='surface' else (208+x,8+y) if panel=='native' else (8+x,int((y+.5)*240/224))
            sy=int((y+.5)*224/240) if panel=='surface' else y
            got=min(get(px,py))>240;wanted=(x,sy) in expected
            if got!=wanted:
                missing+=wanted;extra+=not wanted
                if len(errors)<30:errors.append([x,y,got,wanted])
    result['panels'][panel]={'missing':missing,'extra':extra,'examples':errors,'passed':not(missing+extra)}
if '--surface' in sys.argv:
    result['alignment_diagnostic']=[]
    for dx in range(-1,2):
        for dy in range(-1,2):
            errors=0
            for y in range(240):
                sy=int((y+.5)*224/240)
                for x in range(4,124):
                    errors+=(min(get(40+x,y))>240)!=((x+dx,sy+dy) in expected)
            result['alignment_diagnostic'].append({'dx':dx,'dy':dy,'errors':errors})
print(json.dumps(result,indent=2))
