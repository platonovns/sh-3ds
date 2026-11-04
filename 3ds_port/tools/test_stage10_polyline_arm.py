"""MAP2 opaque polyline packets must equal their connected LINE_F2 segments."""
import hashlib,json,struct
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
ns={'__file__':str(fixture),'__name__':'polyline_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
p=ns['port'];symbols=ns['symbols'];results=[]
def machine():
    m=ns['Machine']();m.call('Game3ds_BeginUpdate',11)
    m.call('GsInitGraph2',320,224,0,0,0)
    return m
def draw(m,words):
    address=symbols['g_PsxRam']+0x100
    m.uc.mem_write(address,struct.pack('<IHH'+'I'*len(words),
        symbols['prim_terminator'],len(words),0,*words))
    m.call('DrawPrim',address)
for vertices in (((-50,-30),(40,-30),(40,30)),
                 ((-50,-30),(40,-30),(40,30),(-50,30)),
                 ((-15,-20),(22,41),(-9,13),(8,-16))):
    xy=[(x&65535)|((y&65535)<<16) for x,y in vertices]
    kind=0x48 if len(xy)==3 else 0x4c
    m=machine();draw(m,[(kind<<24)|0x735129,*xy,0x55555555])
    reference=machine()
    for a,b in zip(xy,xy[1:]):draw(reference,[0x40735129,a,b])
    assert m.draws==reference.draws,(vertices,len(m.draws),len(reference.draws))
    results.append(dict(points=len(xy),submitted_triangles=sum(d['count']//3 for d in m.draws)))
m=machine();address=symbols['g_PsxRam']+0x100
for words in ([0x4a735129,0,1,2,0x55555555],[0x48735129,0,1,2,0]):
    m.uc.mem_write(address,struct.pack('<IHH5I',symbols['prim_terminator'],5,0,*words))
    m.call('DrawPrim',address,expected_failure=425)
report=dict(status='PASS',cases=results,invalid_contracts_rejected=2,
    elf_sha256=hashlib.sha256(ns['elf_path'].read_bytes()).hexdigest(),hardware_accepted=False)
(p/'reports/stage10-polyline-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
