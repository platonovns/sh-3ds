#!/usr/bin/env python3
"""Freeze one data-free hardware candidate only after sustained pad gameplay."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

port=Path(__file__).resolve().parents[1]
root=port.parent
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
run_info=read(port/'build/azahar/last-run.json')
# The manifest contains Windows paths; resolve from its timestamp on either OS.
run_name=run_info['launched'].replace('\\','/').split('/')[-2]
run=port/'build/azahar/runs'/run_name
stability=read(run/'stage5-stability.json')
samples=read(run/'stage5-samples.json')
assert stability['result']=='STABILITY_LOG_PASS_VISUAL_AND_HARDWARE_REVIEW_REQUIRED',stability['result']
assert stability['map_seconds']>=300
last=stability['last']
assert int(last['first_failure'])==0 and int(last['map_frames'])>5000
assert int(last['control_changes'])>100
assert last['input']=='DIAGNOSTIC_GAMEPLAY_PAD'
assert last['build']==run_info['build_identity']
recent=[s['status'] for s in samples if s['elapsed']>=stability['elapsed']-75]
assert len(recent)>2
assert int(last['control_changes'])-int(recent[0]['control_changes'])>=5,'Late gameplay input stopped'
assert all(int(s['status']['first_failure'])==0 for s in samples)
assert all(int(s['status']['cache_active'])<=48 for s in samples)
assert int(last['cache_peak_pinned'])<=48
assert len({s['linear_free'] for s in recent})==1,'Late linear-memory growth'
assert max(int(s['heap_used']) for s in recent)-min(int(s['heap_used']) for s in recent)<4096
assert int(last['linear_free'])>16*1024*1024
assert int(last['texture_bytes'])<=12*1024*1024
assert float(last['frame_ms'])>0 and int(last['perf_samples'])>1000
assert not (root/'sh1_data/stage4_autoinput.txt').exists()
build=read(port/'reports/stage5-game-build.json')
assert build['build']==last['build'] and build['sha256']==run_info['build_sha256']
assert sha(port/'silenthill_game.3dsx')==build['sha256']==sha(run/'silenthill_3ds.3dsx')
assert 'Stage5_native_regressions_PASS' in (port/'reports/stage5-native-regressions.log').read_text()
assert 'Stage 4.1 FS integration + Stage 1-3 regressions PASS' in (port/'reports/stage5-regressions.log').read_text()
arm=read(port/'reports/stage5-game-path-arm.json')
assert arm['failure'] is None and not arm['invalid'] and arm['exception'] is None
assert sha(port/'build/hardware-stage43-level-b/silenthill_game.3dsx')=='f24e73aa67d9d7e196287c5183a761131dca5e716b41edeb27609fd39df7681a'

candidate=port/'build/hardware-stage5-first-map'
evidence=port/'reports/azahar-stage5-first-map'
archive=port/'baselines/stage5-first-map-candidate.zip'
assert not candidate.exists() and not evidence.exists() and not archive.exists(),'Do not overwrite a frozen candidate'
candidate.mkdir(); evidence.mkdir()
for suffix in ('.3dsx','.elf','.map','.smdh'):
    shutil.copy2(port/('silenthill_game'+suffix),candidate/('silenthill_game'+suffix))
for name in ('run.json','qt-config.ini','stage4_status.txt','stage5-samples.json','stage5-stability.json','azahar_log.txt'):
    shutil.copy2(run/name,evidence/name)
for source in sorted((run/'visual-evidence').glob('*.png')):
    shutil.copy2(source,evidence/source.name)

report={
    'status':'AZAHAR FIRST-MAP GAMEPLAY VALIDATED; REAL NEW3DS HARDWARE PENDING',
    'build':build['build'],'bytes':build['bytes'],'sha256':build['sha256'],
    'candidate':candidate.relative_to(root).as_posix(),
    'evidence':evidence.relative_to(root).as_posix(),
    'acceptance_path':'original boot/title -> normal pad START/New Game/NORMAL -> map0_s00; no direct map/state mutation',
    'map_seconds':stability['map_seconds'],'map_submissions':int(last['map_frames']),
    'control_changes':int(last['control_changes']),
    'cache':{k:int(last[k]) for k in ('cache_active','cache_peak','cache_peak_pinned','cache_hits','cache_misses','cache_evictions','cache_uploads','cache_invalidations','texture_bytes')},
    'memory':{'bss':build['bss'],'initialized_data':build['data_with_bss']-build['bss'],
        'heap_used':int(last['heap_used']),'malloc_arena_free':int(last['heap_free']),
        'linear_free':int(last['linear_free']),'linear_min':int(last['linear_min']),
        'late_linear_samples_identical':True,'late_heap_range':[min(int(s['heap_used']) for s in recent),max(int(s['heap_used']) for s in recent)]},
    'performance_azahar':{k:float(last[k]) for k in ('frame_ms','frame_worst_ms','fps','game_ms','primitive_ms','texture_ms','submit_ms','wait_ms')},
    'performance_samples':int(last['perf_samples']),
    'test_notes':['Stage 1-4.1 host/ARM regressions PASS','ARM native original path and GPU packet contracts PASS',
        'ASan/UBSan cache churn/pins/VRAM dependencies and pad mapping PASS','ELF map excludes desktop backends and RomFS',
        'Late pad movement required; renderer-only endurance runs do not qualify'],
    'visual_review':'See native Azahar captures and handoff; fog/mask/transparency defects remain',
    'hardware_input':'PHYSICAL; one-use diagnostic fixture consumed and excluded',
    'last_status':last}
(port/'reports/stage5-azahar.json').write_text(json.dumps(report,indent=2)+'\n')

paths=[]
for base in ('3ds_port/source','3ds_port/include','3ds_port/shaders','3ds_port/patches','3ds_port/tools','3ds_port/tests',
             'include','src/bodyprog','src/screens','src/maps/map0_s00','src/maps/characters','pc_port/include'):
    paths.extend(p for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
paths.extend(root/'src/maps'/n for n in ('particle.c','chara_util.c'))
paths.extend(root/'pc_port/src'/n for n in ('psx_memory.c','math_impl.c','cheryl_anim_info.c','d_800294f4_data.c'))
paths.append(root/'pc_port/build_gen/extracted_data/map0_s00_extracted_data.c')
paths.extend(root/'src/main'/n for n in ('main.c','fsqueue_1.c','fsqueue_2.c','fsqueue_3.c','fileinfo.c','fsmem.c'))
paths.extend(port/n for n in ('Makefile','Makefile.game','engine_sources.mk','native_map_data.ld','native_map_data.json','native_body_data.json'))
paths.extend(candidate.iterdir()); paths.extend(evidence.iterdir())
paths.extend((port/'reports').glob('stage5-*'))
paths.extend(root/'docs'/n for n in ('3ds-stage5-audit.md','3ds-stage5-handoff.md','3ds-stage43-handoff.md','3ds-port.md'))
paths=[p for p in sorted(set(paths)) if p.is_file()]
assert all('sh1_data' not in p.relative_to(root).parts and p.suffix.lower() not in ('.bin','.cue') for p in paths)
manifest={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in paths: z.write(p,p.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
report['source_archive']={'path':archive.relative_to(root).as_posix(),'sha256':sha(archive)}
(port/'reports/stage5-azahar.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','build','bytes','sha256','candidate','map_seconds','map_submissions','cache','memory','performance_azahar','source_archive')},indent=2))
