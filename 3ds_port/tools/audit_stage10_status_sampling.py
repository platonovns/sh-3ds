"""Original FONT16.TIM, actual Status 16 -> 12 row sampling, all 84 glyphs."""
import hashlib,json,math,struct,zlib
from pathlib import Path
p=Path(__file__).resolve().parents[1]
with (p.parent/'sh1_data/sh1.bin').open('rb') as f:
    data=b''
    for i in range(5):
        f.seek((647+i)*2352+24);data+=f.read(2048)
data=data[:8448];assert zlib.crc32(data)==0x42714ea6
offset=8+struct.unpack_from('<I',data,8)[0]
_,_,_,words,height=struct.unpack_from('<I4H',data,offset)
image=data[offset+12:offset+12+words*height*2]
palette=struct.unpack_from('<16H',data,20)
def pixel(g,x,y):
    atlas_x=(g//21)*256+(g%21)*12+x
    index=(image[y*words*2+atlas_x//2]>>(4*(atlas_x%2)))&15
    return (palette[index]&31)/31
def samples(g,linear,phase=0):
    out=[]
    for y in range(12):
        # Native folded geometry starts at a half pixel; UV endpoints are
        # source texel centres 240.5 ... 255.5, a 15-texel delta.
        uv=.5+(y+phase)*15/12
        if not linear:out.append([pixel(g,x,int(uv)) for x in range(12)]);continue
        source=uv-.5;lo=math.floor(source);t=source-lo
        out.append([pixel(g,x,lo)*(1-t)+pixel(g,x,min(lo+1,15))*t for x in range(12)])
    return out
rows=[]
for g in range(84):
    old=samples(g,False);new=samples(g,True)
    rows.append(dict(char=chr(g+39),source_ink=sum(pixel(g,x,y) for y in range(16) for x in range(12)),
        nearest_ink=sum(map(sum,old)),filtered_ink=sum(map(sum,new))))
g=ord('e')-39
old=samples(g,False);new=samples(g,True)
assert pixel(g,4,7)>.8 and pixel(g,4,8)<.1
assert old[6][4]<.1 and new[6][4]>.4,(old[6][4],new[6][4])
phase_rows=[]
for phase in (i/64 for i in range(64)):
    values=[]
    for linear in (False,True):
        sampled=samples(g,linear,phase)
        values.append(max(sampled[y][4] for y in range(12) if 6<=(y+phase)*15/12<=8.5))
    phase_rows.append(dict(phase=phase,nearest_crossbar=values[0],filtered_crossbar=values[1]))
assert min(r['nearest_crossbar'] for r in phase_rows)<.1
assert min(r['filtered_crossbar'] for r in phase_rows)>.3
report=dict(status='PASS',source_sha256=hashlib.sha256(data).hexdigest(),source_crc32='42714ea6',
    source_cell=[12,16],lcd_cell=[12,12],source_rows_nearest=[int(.5+y*15/12) for y in range(12)],
    e_crossbar_column=4,e_source_rows_7_8=[pixel(g,4,7),pixel(g,4,8)],
    e_lcd_row_6_nearest_filtered=[old[6][4],new[6][4]],subpixel_phases=phase_rows,glyphs=rows,
    scope='Sampling oracle; actual PICA capture still required. No character-specific rendering rule.',hardware_accepted=False)
(p/'reports/stage10-status-sampling.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='glyphs'},indent=2))
