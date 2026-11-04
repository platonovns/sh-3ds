#!/usr/bin/env python3
"""Freeze the narrow Stage 5 polygon-size follow-up without changing baselines."""
from pathlib import Path
import hashlib,json,shutil,sys,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
build=read(p/'reports/stage5-edge-build.json');run=p/'build/azahar/runs'/sys.argv[1]
info=read(run/'run.json');result=read(run/'stage5-stability.json');samples=read(run/'stage5-samples.json');s=result['last']
expected='482db74e5b541ea70de80f8e7a58005a511fe6b697ac4c18e9f7c922e78b3b0b'
assert sha(p/'silenthill_game.3dsx')==sha(run/'silenthill_3ds.3dsx')==build['sha256']==info['build_sha256']==expected
assert build['build']==s['build']==info['build_identity'] and build['bytes']==667868
assert result['result']=='STABILITY_LOG_PASS_VISUAL_AND_HARDWARE_REVIEW_REQUIRED' and result['map_seconds']>=300
assert s['input']=='DIAGNOSTIC_GAMEPLAY_PAD' and s['profile']=='OFF' and int(s['gpu_oversize_triangles'])>0
assert all(int(v['status']['first_failure'])==0 for v in samples)
assert all(int(v['status']['cache_active'])<=48 and int(v['status']['texture_bytes'])<=12582912 for v in samples)
late=[v['status'] for v in samples if v['elapsed']>=result['elapsed']-75]
assert len(late)>2 and int(s['control_changes'])-int(late[0]['control_changes'])>=5
assert len({v['linear_free'] for v in late})==1
assert max(int(v['heap_used']) for v in late)-min(int(v['heap_used']) for v in late)<4096
assert int(s['resource_cache_bytes'])==11896416 and s['resource_cache_status']==s['resource_common_status']=='0'
assert max(float(v['status']['command_percent']) for v in samples)<100
gpu=read(p/'reports/stage5-edge-gpu-arm.json')['results'];assert len(gpu['psx_triangle_size_contracts'])==10
assert 'oversize_x' in (p/'reports/stage5-edge-arm-before.log').read_text()
assert 'PASS:' in (p/'reports/stage5-edge-sanitizers.log').read_text()
game=read(p/'reports/stage5-edge-game-arm.json')
assert game['state']==11 and game['failure'] is None and not game['invalid'] and game['exception'] is None
assert read(p/'reports/stage5-edge-pose-arm.json')['failure_bits']==0
assert read(p/'reports/stage5-edge-menu-arm.json')['passed']
assert sha(p/'build/hardware-stage5-final/silenthill_game.3dsx')=='6ec42ff66d294c9eff3430aaf8377bd551a340966cca5858e95cdaa742572fb2'
for f in ('stage4_autoinput.txt','stage5_profile.txt','stage5_io_cache.txt','stage5_capture.txt'):assert not(root/'sh1_data'/f).exists()
candidate=p/'build/hardware-stage5-edge';archive=p/'baselines/stage5-edge-candidate.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
evidence=p/'reports/azahar-stage5-edge/current';evidence.mkdir()
for f in ('run.json','stage5-samples.json','stage5-stability.json','azahar_log.txt','qt-config.ini'):shutil.copy2(run/f,evidence/f)
(evidence/'stage4_status.txt').write_text(''.join(f'{k}={v}\n' for k,v in s.items()))
handoff=root/'docs/3ds-stage5-edge-handoff.md';text=handoff.read_text()
for k,v in {'SECONDS':result['map_seconds'],'FRAMES':s['map_frames'],'LINEAR':s['linear_free']}.items():text=text.replace('{{'+k+'}}',str(v))
assert '{{' not in text;handoff.write_text(text)
report={'status':'AZAHAR VERIFIED; HARDWARE ACCEPTANCE PENDING','build':build,'run':result,
        'change':'PSX per-triangle 1023x511 size rejection in native packet decoder; no object exceptions',
        'inherited_validation':'Unchanged render surfaces, STP/ABR, pixel paths and resource cache retain prior final-candidate tests; not rerun on this ELF.'}
report_path=p/'reports/stage5-edge-azahar.json';report_path.write_text(json.dumps(report,indent=2)+'\n')
# Reuse the preceding source closure, replacing each member by current bytes.
previous=p/'baselines/stage5-final-candidate.zip'
with zipfile.ZipFile(previous) as z:old_manifest=json.loads(z.read('manifest.json'))
paths=[root/n for n in old_manifest if not n.startswith('3ds_port/build/')]
paths += list(candidate.iterdir())+[v for v in (p/'reports/azahar-stage5-edge').rglob('*') if v.is_file()]
paths += [v for v in (p/'reports').glob('stage5-edge-*') if v.is_file()]
paths += [handoff,p/'tools/freeze_stage5_edge.py',p/'tools/analyze_stage5_edges.py']
paths=sorted(set(v for v in paths if v.is_file()))
assert all('sh1_data' not in v.relative_to(root).parts and v.suffix.lower() not in ('.bin','.cue') for v in paths)
manifest={v.relative_to(root).as_posix():{'bytes':v.stat().st_size,'sha256':sha(v)} for v in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for v in paths:z.write(v,v.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for n,e in manifest.items():
        data=z.read(n);assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256']
report['archive']={'path':archive.relative_to(root).as_posix(),'bytes':archive.stat().st_size,'sha256':sha(archive),'verified_members':len(manifest)}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'build':build['build'],'bytes':build['bytes'],'sha256':expected,'seconds':result['map_seconds'],'archive':report['archive']},indent=2))
