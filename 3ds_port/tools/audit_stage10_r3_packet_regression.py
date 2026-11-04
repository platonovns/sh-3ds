"""Focused frozen R2/R3 source comparison for the Cafe window arena failure."""
import hashlib,json,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1]
archives={}
for rev in ('r2','r3'):
    receipt=json.loads((p/f'reports/stage10-{rev}-freeze.json').read_text())
    archive=p.parent/receipt['archive']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['archive_sha256']
    archives[rev]=zipfile.ZipFile(archive)
names=('src/bodyprog/sys/game_main.c','3ds_port/source/main_game.c',
    '3ds_port/source/game_tmd.c','3ds_port/tools/prepare_tmd_emit.py',
    'src/maps/map0_s01/map0_s01_events.c','src/maps/particle.c','src/maps/particle_glass.c',
    'src/bodyprog/bodyprog_8005E0DC.c','src/bodyprog/bodyprog_8005A838.c',
    '3ds_port/source/game_gpu.c','3ds_port/source/render_3ds.c')
rows=[]
for name in names:
    if not all(name in z.namelist() for z in archives.values()):continue
    a,b=(archives[r].read(name) for r in ('r2','r3'))
    rows.append(dict(path=name,identical=a==b,r2_sha256=hashlib.sha256(a).hexdigest(),r3_sha256=hashlib.sha256(b).hexdigest()))
main=[archives[r].read('src/bodyprog/sys/game_main.c').decode() for r in ('r2','r3')]
packet_sections=[s[s.index('        PACKET *native_packet_start='):s.index('        g_SysWork.bgmStatusFlags =')] for s in main]
assert packet_sections[0]==packet_sections[1] and '131072' in packet_sections[0]
before=json.loads((p/'reports/stage10-r3-window-cadence3.json').read_text())
assert before['run']['failure']['code']==460 and before['window_seen']
peak=max(before['rows'],key=lambda x:x['used'])
assert peak['pose'][0]==10 and peak['pose'][2]==20 and peak['pose'][-1]==5
report=dict(status='PASS',source_comparison=rows,original_packet_partition_identical=True,
    reproduction=dict(failure=before['run']['failure'],vblanks=before['vblanks'],peak=peak),
    hardware=dict(code=460,operation='native packet arena overflow',bytes=131400,capacity=131072,
        image_sha256=hashlib.sha256((p/'reports/stage10-r4-hardware/r3-cafe-overflow.png').read_bytes()).hexdigest()),
    conclusion='A fixed PSX byte partition was retained for larger native packets. Event density/cadence exposes it; source equality does not imply identical runtime high-water marks.',
    hardware_accepted=False)
(p/'reports/stage10-r3-packet-regression-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(status='PASS',identical=[r['path'] for r in rows if r['identical']],reproduced=before['run']['failure']),indent=2))
