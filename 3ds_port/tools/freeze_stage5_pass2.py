#!/usr/bin/env python3
"""Validate and freeze Stage 5 pass 2, preserving all prior hardware candidates."""
from pathlib import Path
import hashlib,json,shutil,zipfile
port=Path(__file__).resolve().parents[1];root=port.parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
build=read(port/'reports/stage5-pass2-final-build.json')
runs={'profile':'20261024-191637-854','running':read(port/'build/azahar/last-run.json')['launched'].replace('\\','/').split('/')[-2]}
results={}
for label,name in runs.items():
    run=port/'build/azahar/runs'/name;info=read(run/'run.json')
    result=read(run/'stage5-stability.json');samples=read(run/'stage5-samples.json');last=result['last']
    assert result['result']=='STABILITY_LOG_PASS_VISUAL_AND_HARDWARE_REVIEW_REQUIRED'
    assert result['map_seconds'] >= (600 if label=='profile' else 300)
    assert last['build']==info['build_identity']==build['build']
    assert sha(run/'silenthill_3ds.3dsx')==info['build_sha256']==build['sha256']
    assert last['input']==('DIAGNOSTIC_GAMEPLAY_PAD' if label=='profile' else 'DIAGNOSTIC_RUNNING_PAD')
    assert last['profile']==('DETAILED' if label=='profile' else 'OFF')
    if label=='running':assert any(int(s['status']['pad_held'])&32768 for s in samples),'Original Square/run input was not observed'
    assert int(last['first_failure'])==0 and int(last['map_frames'])>1000
    assert int(last['command_bytes'])==768*1024
    assert all(int(s['status']['first_failure'])==0 and int(s['status']['cache_active'])<=48 for s in samples)
    assert int(last['cache_peak_pinned'])<=48 and int(last['texture_bytes'])<=12*1024*1024
    assert int(last['linear_free'])>16*1024*1024
    assert max(float(s['status']['command_percent']) for s in samples)<100
    late=[s['status'] for s in samples if s['elapsed']>=result['elapsed']-75]
    assert len(late)>2 and int(last['control_changes'])-int(late[0]['control_changes'])>=5
    assert len({s['linear_free'] for s in late})==1
    assert max(int(s['heap_used']) for s in late)-min(int(s['heap_used']) for s in late)<4096
    results[label]=result
assert sha(port/'silenthill_game.3dsx')==build['sha256']
for name in ('stage5-pass2-order-after.json','stage5-pass2-precision-after.json','stage5-pass2-pixels-after.json','stage5-pass2-mask-after.json'):
    assert read(port/'reports'/name)['passed'],name
assert not read(port/'reports/stage5-pass2-order-before.json')['passed']
assert not read(port/'reports/stage5-pass2-precision-before.json')['passed']
for file,token in [('stage5-pass2-regression-driver.log','Stage5_pass2_regressions_PASS'),('stage5-pass2-final-arm.log','Stage5_pass2_final_ARM_PASS'),('stage5-pass2-coverage-tests.log','PASS:')]:
    assert token in (port/'reports'/file).read_text(),file
for name in ('stage4_autoinput.txt','stage5_capture.txt','stage5_profile.txt','stage5_probe_mask.txt','stage5_probe_order.txt','stage5_probe_precision.txt'):
    assert not (root/'sh1_data'/name).exists(),name
for name,expected in [('hardware-stage5-followup','03996b0b7bdedee6b1c541971a022b1e9a653537d722aa4786e38fff47ea2e23'),('hardware-stage5-first-map','41c59cd1cc460166c27a85fc750184b81ea9a5acb4b2b8370ee9a5ba1612c9d5'),('hardware-stage43-level-b','f24e73aa67d9d7e196287c5183a761131dca5e716b41edeb27609fd39df7681a')]:
    assert sha(port/'build'/name/'silenthill_game.3dsx')==expected
candidate=port/'build/hardware-stage5-pass2';archive=port/'baselines/stage5-pass2-candidate.zip'
assert not candidate.exists() and not archive.exists(),'Frozen artifacts are immutable'
candidate.mkdir()
for suffix in ('.3dsx','.elf','.map','.smdh'):
    shutil.copy2(port/('silenthill_game'+suffix),candidate/('silenthill_game'+suffix))
evidence=port/'reports/azahar-stage5-pass2'
for label,name in {**runs,'before':'20261024-182146-603','intermediate':'20261024-184441-541'}.items():
    source=port/'build/azahar/runs'/name;dest=evidence/label;dest.mkdir()
    for file in ('run.json','stage5-samples.json','stage5-stability.json','azahar_log.txt','qt-config.ini'):
        if (source/file).exists():shutil.copy2(source/file,dest/file)
    last=read(source/'stage5-stability.json')['last']
    (dest/'stage4_status.txt').write_text(''.join(f'{k}={v}\n' for k,v in last.items()))
report={'status':'AZAHAR PASS; REAL NEW3DS ACCEPTANCE PENDING','build':build,'candidate':candidate.relative_to(root).as_posix(),
        'runs':results,'hardware_default':'PHYSICAL input; profiling OFF; no periodic gameplay SD reports',
        'budgets':{'texture_slots':48,'texture_bytes':12582912,'command_bytes':786432,'primitives':2048,'vertices':12288},
        'running_input_evidence':'Original ControllerFlag_Square (0x8000) observed in complete status samples; no direct game-state writes',
        'limits':'Stage 5 only. Exact hardware garage route and photographed pixels require retest. Synchronous loading remains.',
        'profile_comparison':read(port/'reports/stage5-pass2-profile-comparison.json')}
report_path=port/'reports/stage5-pass2-azahar.json';report_path.write_text(json.dumps(report,indent=2)+'\n')
handoff=root/'docs/3ds-stage5-pass2-handoff.md';content=handoff.read_text()
for key,value in {'BUILD':build['build'],'BYTES':build['bytes'],'SHA256':build['sha256'],
                  'PROFILE_SECONDS':results['profile']['map_seconds'],'RUN_SECONDS':results['running']['map_seconds'],
                  'PROFILE_FRAMES':results['profile']['last']['map_frames'],'RUN_FRAMES':results['running']['last']['map_frames'],
                  'BSS':build['bss'],'LINEAR':results['profile']['last']['linear_free']}.items():content=content.replace('{{'+key+'}}',str(value))
assert '{{' not in content;handoff.write_text(content)
paths=[]
for base in ('3ds_port/source','3ds_port/include','3ds_port/shaders','3ds_port/patches','3ds_port/tools','3ds_port/tests','include','src/bodyprog','src/screens','src/maps/map0_s00','src/maps/characters','pc_port/include'):
    paths += [p for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [root/'src/maps'/n for n in ('particle.c','chara_util.c')]
paths += [root/'pc_port/src'/n for n in ('psx_memory.c','math_impl.c','cheryl_anim_info.c','d_800294f4_data.c')]
paths += [root/'pc_port/build_gen/extracted_data/map0_s00_extracted_data.c']
paths += [root/'src/main'/n for n in ('main.c','fsqueue_1.c','fsqueue_2.c','fsqueue_3.c','fileinfo.c','fsmem.c')]
paths += [port/n for n in ('Makefile','Makefile.game','engine_sources.mk','native_map_data.ld','native_map_data.json','native_body_data.json')]
paths += list(candidate.iterdir())+[p for p in evidence.rglob('*') if p.is_file()]
paths += list((port/'reports').glob('stage5-pass2-*'))
paths += list((root/'docs').glob('3ds-stage5*'))+[root/'docs/3ds-port.md']
paths=sorted(set(p for p in paths if p.is_file()))
assert all('sh1_data' not in p.relative_to(root).parts and p.suffix.lower() not in ('.bin','.cue') for p in paths)
manifest={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in paths:z.write(p,p.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for name,entry in manifest.items():
        data=z.read(name);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
report['archive']={'path':archive.relative_to(root).as_posix(),'bytes':archive.stat().st_size,'sha256':sha(archive),'verified_members':len(manifest)}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'build':build,'archive':report['archive'],'runs':{k:{f:v[f] for f in ('result','map_seconds','sample_count')} for k,v in results.items()}},indent=2))
