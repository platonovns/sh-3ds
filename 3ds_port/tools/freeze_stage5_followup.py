#!/usr/bin/env python3
"""Freeze the measured Stage 5 corrections without replacing older candidates."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

port = Path(__file__).resolve().parents[1]
root = port.parent
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
info = read(port/'build/azahar/last-run.json')
run = port/'build/azahar/runs'/info['launched'].replace('\\','/').split('/')[-2]
stability = read(run/'stage5-stability.json')
samples = read(run/'stage5-samples.json')
last = stability['last']
assert stability['result'] == 'STABILITY_LOG_PASS_VISUAL_AND_HARDWARE_REVIEW_REQUIRED'
assert stability['map_seconds'] >= 600
assert int(last['first_failure']) == 0 and int(last['map_frames']) > 10000
assert int(last['max_draws']) > 1536, 'Dense-view regression was not exercised'
assert int(last['command_bytes']) == 768*1024
assert last['input'] == 'DIAGNOSTIC_GAMEPLAY_PAD' and int(last['control_changes']) > 100
late = [s['status'] for s in samples if s['elapsed'] >= stability['elapsed']-75]
assert len(late) > 2 and int(last['control_changes'])-int(late[0]['control_changes']) >= 5
assert all(int(s['status']['first_failure']) == 0 for s in samples)
assert all(int(s['status']['cache_active']) <= 48 for s in samples)
assert int(last['cache_peak_pinned']) <= 48
assert len({s['linear_free'] for s in late}) == 1
assert max(int(s['heap_used']) for s in late)-min(int(s['heap_used']) for s in late) < 4096
assert int(last['texture_bytes']) <= 12*1024*1024 and int(last['linear_free']) > 16*1024*1024
peak_command = max(float(s['status']['command_percent']) for s in samples)
assert peak_command < 100
build = read(port/'reports/stage5-followup-build.json')
assert last['build'] == info['build_identity'] == build['build']
assert sha(port/'silenthill_game.3dsx') == info['build_sha256'] == build['sha256']
assert sha(run/'silenthill_3ds.3dsx') == build['sha256']
moving = read(port/'reports/stage5-followup-moving-analysis.json')
assert moving['build'] == build['build']
assert 'Stage5_followup_regressions_PASS' in (port/'reports/stage5-followup-regressions.log').read_text()
assert 'Stage5_followup_native_PASS' in (port/'reports/stage5-followup-cache-clock.log').read_text()
assert 'Stage5_final_ARM_PASS' in (port/'reports/stage5-followup-final-arm.log').read_text()
for name in ('stage5-pixels-after.json', 'stage5-mask-pixels.json'):
    assert read(port/'reports'/name)['passed']
assert read(port/'reports/stage5-pose-after.json')['failure_bits'] == 0
arm = read(port/'reports/stage5-followup-game-path-arm.json')
assert arm['failure'] is None and arm['exception'] is None and not arm['invalid']
for name in ('stage4_autoinput.txt','stage5_capture.txt','stage5_probe_mask.txt'):
    assert not (root/'sh1_data'/name).exists(), name
assert sha(port/'build/hardware-stage5-first-map/silenthill_game.3dsx') == '41c59cd1cc460166c27a85fc750184b81ea9a5acb4b2b8370ee9a5ba1612c9d5'
assert sha(port/'build/hardware-stage43-level-b/silenthill_game.3dsx') == 'f24e73aa67d9d7e196287c5183a761131dca5e716b41edeb27609fd39df7681a'
candidate = port/'build/hardware-stage5-followup'
evidence = port/'reports/azahar-stage5-followup'
archive = port/'baselines/stage5-followup-candidate.zip'
assert not candidate.exists() and not archive.exists(), 'Frozen artifacts are immutable'
candidate.mkdir()
for suffix in ('.3dsx','.elf','.map','.smdh'):
    shutil.copy2(port/('silenthill_game'+suffix), candidate/('silenthill_game'+suffix))
for name in ('run.json','qt-config.ini','stage5-samples.json','stage5-stability.json','azahar_log.txt'):
    shutil.copy2(run/name, evidence/name)
# A second raw file copy can race the next guest write. Preserve the complete
# parsed snapshot that actually passed validation, with every field unchanged.
(evidence/'stage4_status.txt').write_text(''.join(f'{k}={v}\n' for k,v in last.items()))
for label, name in (('before','20261024-161817-566'), ('after','20261024-164401-822')):
    dest = evidence/('stationary-'+label)
    dest.mkdir()
    source = port/'build/azahar/runs'/name
    for file in ('run.json',f'stationary-{label}-samples.json',f'stationary-{label}-result.json'):
        shutil.copy2(source/file, dest/file)
report = {
    'status':'AZAHAR FOLLOW-UP VALIDATED; REAL NEW3DS HARDWARE PENDING',
    'build':build['build'], 'bytes':build['bytes'], 'sha256':build['sha256'],
    'candidate':candidate.relative_to(root).as_posix(),
    'map_seconds':stability['map_seconds'], 'map_submissions':int(last['map_frames']),
    'control_changes':int(last['control_changes']), 'peak_sampled_command_percent':peak_command,
    'capacity':{'primitives':2048,'vertices':12288,'command_bytes':786432,
                'observed_max_primitives':int(last['max_draws']),
                'old_1536_limit_exceeded_without_failure':True},
    'acceptance_path':'Original boot/title/New Game/NORMAL; diagnostic pad only; no map/state mutation',
    'cache':{k:int(last[k]) for k in ('cache_active','cache_peak','cache_peak_pinned','cache_misses','cache_evictions','cache_uploads','cache_invalidations','texture_bytes')},
    'memory':{'bss':build['bss'],'initialized_data':build['data_with_bss']-build['bss'],
              'heap_used':int(last['heap_used']), 'linear_free':int(last['linear_free']),
              'linear_min':int(last['linear_min']), 'extra_stencil_vram_bytes':384000,
              'late_heap_range':[min(int(s['heap_used']) for s in late),max(int(s['heap_used']) for s in late)]},
    'stationary_comparison':read(port/'reports/stage5-stationary-comparison.json'),
    'moving_cost_analysis':moving,
    'last_status':last,
    'crash_status':'Reported unlocalized hardware tree-area crash not reproduced; cause unknown',
    'limitations':'No hardware progressive-cost conclusion; no full VRAM feedback/transfer mask or exact PSX blending; Stage 5 scope only',
    'hardware_input':'PHYSICAL; one-use diagnostic fixtures consumed and excluded',
    'evidence':evidence.relative_to(root).as_posix()}
report['status_snapshot_source'] = 'Complete status dictionary in stage5-stability.json; avoids racing a later guest write'
report_path = port/'reports/stage5-followup-azahar.json'
report_path.write_text(json.dumps(report,indent=2)+'\n')
handoff = root/'docs/3ds-stage5-followup-handoff.md'
content = handoff.read_text()
for key, value in {'BUILD':build['build'], 'BYTES':build['bytes'], 'SHA256':build['sha256'],
                   'SECONDS':stability['map_seconds'], 'FRAMES':last['map_frames'],
                   'CONTROLS':last['control_changes'], 'EVICTIONS':last['cache_evictions'],
                   'PINNED':last['cache_peak_pinned'], 'COMMAND':peak_command,
                   'MAX_DRAWS':last['max_draws'],
                   'HEAP':last['heap_used'], 'LINEAR':last['linear_free'], 'BSS':build['bss']}.items():
    content = content.replace('{{'+key+'}}', str(value))
assert '{{' not in content
handoff.write_text(content)
paths = []
for base in ('3ds_port/source','3ds_port/include','3ds_port/shaders','3ds_port/patches','3ds_port/tools','3ds_port/tests',
             'include','src/bodyprog','src/screens','src/maps/map0_s00','src/maps/characters','pc_port/include'):
    paths += [p for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [root/'src/maps'/n for n in ('particle.c','chara_util.c')]
paths += [root/'pc_port/src'/n for n in ('psx_memory.c','math_impl.c','cheryl_anim_info.c','d_800294f4_data.c')]
paths += [root/'pc_port/build_gen/extracted_data/map0_s00_extracted_data.c']
paths += [root/'src/main'/n for n in ('main.c','fsqueue_1.c','fsqueue_2.c','fsqueue_3.c','fileinfo.c','fsmem.c')]
paths += [port/n for n in ('Makefile','Makefile.game','engine_sources.mk','native_map_data.ld','native_map_data.json','native_body_data.json')]
paths += list(candidate.iterdir()) + [p for p in evidence.rglob('*') if p.is_file()]
paths += list((port/'reports').glob('stage5-*'))
paths += [root/'docs'/n for n in ('3ds-stage5-followup.md','3ds-stage5-followup-handoff.md','3ds-stage5-audit.md','3ds-stage5-handoff.md','3ds-stage43-handoff.md','3ds-port.md')]
paths = [p for p in sorted(set(paths)) if p.is_file()]
assert all('sh1_data' not in p.relative_to(root).parts and p.suffix.lower() not in ('.bin','.cue') for p in paths)
manifest = {p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in paths: z.write(p,p.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
report['source_archive'] = {'path':archive.relative_to(root).as_posix(),'sha256':sha(archive)}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','build','bytes','sha256','candidate','map_seconds','map_submissions','control_changes','peak_sampled_command_percent','cache','memory','source_archive')},indent=2))
