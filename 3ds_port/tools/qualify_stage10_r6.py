"""Bind R6 performance/polish evidence to the exact normal production ELF."""
import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def read(n):return json.loads((p/'reports'/n).read_text(encoding='utf-8-sig'))
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
elfsha=sha(p/'silenthill_game.elf')
foundation=read('stage10-foundation-regressions.json')
assert foundation['status']=='PASS' and foundation['elf_sha256']==elfsha and len(foundation['tests'])==34
assert all(t['status']=='PASS' for t in foundation['tests'])
quick=read('stage10-r6-quick-matrix.json');assert quick['status']=='PASS' and len(quick['cases'])==12
dev=read('../build/stage10-dev-scene-3/manifest.json')
assert dev['base_elf_sha256']==elfsha and dev['elf_sha256']==quick['elf_sha256']
auto=read('stage10-r6-auto-reload.json')
assert auto['elf_sha256']==quick['elf_sha256'] and len(auto['cases'])==2
for c in auto['cases']:
    assert c['reload_start'] and c['reload_done'] and c['aim_released']
    assert not any(c['run'][k] for k in ('failure','invalid','exception'))
    assert c['final'][2] in (0,1,2) and not c['final'][9] and not c['final'][15]
pixel=read('stage10-r6-pixel-index.json')
assert pixel['status']=='PASS' and pixel['renderer_object_sha256']==sha(p/'build-game/render_3ds.o')
assert pixel['card_unchanged'] and len(pixel['runs'])==5
perf=read('stage10-r6-performance.json');assert perf['status']=='PASS'
for name in ('baseline-town-off','baseline-town-on','final-town-off','final-town-on','indoor-off','indoor-on',
             'combat-air-before','combat-air-after','combat-groaner-before','combat-groaner-after'):
    run=perf['runs'][name]
    assert run['diagnostic']['base_elf_sha256']==elfsha
    if name.startswith('combat-'):assert run['enemy_frames']>0 and run['enemy_peak']>0
    # Evidence must also refer to the actual preserved development artifact.
    if name.startswith('baseline-town-'):folder='stage10-r6-benchmark-8-'+name.rsplit('-',1)[1]+'-renderer-r5'
    elif name.startswith('final-town-'):folder='stage10-r6-benchmark-8-'+name.rsplit('-',1)[1]
    elif name.startswith('indoor-'):folder='stage10-r6-benchmark-7-'+name.rsplit('-',1)[1]
    elif name.startswith('combat-'):
        _,kind,phase=name.split('-');folder='stage10-r6-benchmark-8-off-'+kind+('-renderer-r5' if phase=='before' else '')
    assert run['diagnostic']['sha256']==sha(p/'build'/folder/'diagnostic.3dsx')
fade=read('stage10-r6-fade-after-analysis.json');assert fade['status']=='PASS'
fq=read('stage10-r6-fade-after-pica/qualification.json')
assert fq['diagnostic']['base_elf_sha256']==elfsha and fq['status']=='PASS'
memory=read('stage10-r6-memory-audit.json')
assert memory['status']=='PASS' and memory['stable_after_warmup'] and not memory['leak_observed']
assert memory['cycles']==6 and memory['door_transitions']>=12
assert memory['diagnostic']['base_elf_sha256']==elfsha
oracles={}
for kind,source in (('readback','include/psx_readback_region.h'),('decode','source/game_texture_decode.c'),('feedback-decode','include/game_feedback.h')):
    r=read('stage10-r6-'+kind+'-host.json');assert r['status']=='PASS'
    assert r['source_sha256']==sha(p/source)
    oracles[kind]=r
cardsha=sha(root/'sh1_data/memcard.mcr')
assert cardsha=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
acceptance=read('stage10-r5-hardware-accepted.json');assert acceptance['status']=='HARDWARE_ACCEPTED'
assert sha(p/'baselines/stage10-r5.zip')==acceptance['archive_sha256']
mips=read('stage10-r6-air-mips.json')
assert mips['status']=='PASS' and len(mips['cases'])==90 and mips['elf_sha256']==elfsha
report=dict(status='PASS',scope=__doc__,normal_elf_sha256=elfsha,foundation_tests=34,
    quick_reload_cases=12,pica_pixel_cases=5,air_mips_arm_cases=90,host_pixel_oracles=oracles,
    performance_report='stage10-r6-performance.json',fade_report='stage10-r6-fade-after-analysis.json',
    memory_report='stage10-r6-memory-audit.json',memory_card_unchanged=True,
    memory_card_sha256=cardsha,r5_functional_milestone_hardware_accepted=True,
    r5_archive_preserved=True,hardware_accepted=False)
(p/'reports/stage10-r6-runtime-qualification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='host_pixel_oracles'},indent=2))
