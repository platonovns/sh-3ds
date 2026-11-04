#!/usr/bin/env python3
"""Freeze tested Stage 5 bytes and curated evidence; hardware acceptance is separate."""
from pathlib import Path
import hashlib,json,shutil,sys,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
build=read(p/'reports/stage5-final-build.json')
assert build['bytes']==667380 and build['bss']<5*1024*1024
assert sha(p/'silenthill_game.3dsx')==build['sha256']=='6ec42ff66d294c9eff3430aaf8377bd551a340966cca5858e95cdaa742572fb2'
assert len(sys.argv)==3,'Arguments: detailed run, profile-OFF run'
runs=dict(zip(('profile','normal'),sys.argv[1:]));results={}
for label,name in runs.items():
    d=p/'build/azahar/runs'/name;info=read(d/'run.json');r=read(d/'stage5-stability.json');samples=read(d/'stage5-samples.json');s=r['last']
    assert r['result']=='STABILITY_LOG_PASS_VISUAL_AND_HARDWARE_REVIEW_REQUIRED'
    assert r['map_seconds']>=(600 if label=='profile' else 300)
    assert s['build']==info['build_identity']==build['build']
    assert sha(d/'silenthill_3ds.3dsx')==info['build_sha256']==build['sha256']
    assert s['input']=='DIAGNOSTIC_GARAGE_PAD' and s['profile']==('DETAILED' if label=='profile' else 'OFF')
    assert int(s['route_laps'])>=(20 if label=='profile' else 10)
    assert any(int(v['status']['pad_held'])&32768 for v in samples),'Square/run input missing'
    assert int(s['resource_cache_enabled'])==1 and int(s['resource_cache_status'])==0 and int(s['resource_common_status'])==0
    assert int(s['resource_cache_bytes'])==int(s['resource_cache_peak_bytes'])==11896416
    assert int(s['resource_cache_budget'])==16777216 and int(s['resource_cache_files'])==300
    assert int(s['resource_common_file'])==2043 and int(s['resource_common_bytes'])==89376
    assert int(s['resource_preload_reads'])==159 and int(s['resource_preload_seeks'])==2
    assert int(s['command_bytes'])==786432 and int(s['map_frames'])>1000
    assert all(int(v['status']['first_failure'])==0 and int(v['status']['cache_active'])<=48 for v in samples)
    assert int(s['cache_peak_pinned'])<=48 and int(s['texture_bytes'])<=12582912
    assert int(s['linear_free'])>16*1024*1024 and int(s['normal_heap_free'])>70*1024*1024
    assert max(float(v['status']['command_percent']) for v in samples)<100
    late=[v['status'] for v in samples if v['elapsed']>=r['elapsed']-75]
    assert len(late)>2 and int(s['control_changes'])-int(late[0]['control_changes'])>=5
    assert len({v['linear_free'] for v in late})==1
    assert max(int(v['heap_used']) for v in late)-min(int(v['heap_used']) for v in late)<4096
    assert len({v['cache_evictions'] for v in late})==1,'Late texture churn'
    results[label]=r
for n in ('pixels','precision','mask','order'):
    assert read(p/f'reports/stage5-final-{n}.json')['passed'],n
raster=read(p/'reports/stage5-final-raster-final.json')['panels']['surface']
assert raster['passed'] and raster['missing']==raster['extra']==0
assert read(p/'reports/stage5-final-raster-grid.json')['panels']['old']['missing']>0
for f,token in [('stage5-final-regressions.log','Stage5_final_PC_sanitizers_PASS'),('stage5-final-arm.log','Stage5_final_ARM_PASS')]:
    assert token in (p/'reports'/f).read_text(),f
for v in read(p/'reports/stage5-final-cache-arm.json')['results'].values():assert v['passed']
perf=read(p/'reports/stage5-final-performance.json');after=perf['runs']['after'];normal=perf['runs']['normal']
assert after['directory']==runs['profile'] and normal['directory']==runs['normal']
assert len(after['matched_pose_windows'])>=3
assert max(v['work_change_ms'] for v in after['matched_pose_windows'])<1.5
assert all(v['reads']==0 and v['seeks']==0 for v in after['requests']),'Unexpected post-approach raw I/O'
assert any(v['file']==2043 and v['before_ms']['max']>50 and v['after_ms']['max']<1 for v in perf['identical_request_pairs'])
fixtures=['stage4_autoinput.txt','stage5_capture.txt','stage5_profile.txt','stage5_io_cache.txt']
fixtures += [v.name for v in (root/'sh1_data').glob('stage5_probe_*.txt')]
assert all(not(root/'sh1_data'/n).exists() for n in fixtures),'One-use fixture remains'
old={'hardware-stage5-pass2':'dcb5ac72c9e2851783e42a78dddc058613c0f38b50f0b5092edc637b7c7387ac',
     'hardware-stage5-followup':'03996b0b7bdedee6b1c541971a022b1e9a653537d722aa4786e38fff47ea2e23',
     'hardware-stage5-first-map':'41c59cd1cc460166c27a85fc750184b81ea9a5acb4b2b8370ee9a5ba1612c9d5',
     'hardware-stage43-level-b':'f24e73aa67d9d7e196287c5183a761131dca5e716b41edeb27609fd39df7681a'}
for n,h in old.items():assert sha(p/'build'/n/'silenthill_game.3dsx')==h,n
candidate=p/'build/hardware-stage5-final';archive=p/'baselines/stage5-final-candidate.zip'
assert not candidate.exists() and not archive.exists(),'Frozen artifacts are immutable'
candidate.mkdir()
for suffix in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+suffix),candidate/('silenthill_game'+suffix))
evidence=p/'reports/azahar-stage5-final'
for label,name in {**runs,'before':'20261025-030636-917'}.items():
    source=p/'build/azahar/runs'/name;dest=evidence/label;dest.mkdir()
    for f in ('run.json','stage5-samples.json','stage5-stability.json','azahar_log.txt','qt-config.ini'):
        shutil.copy2(source/f,dest/f)
    status=read(source/'stage5-stability.json')['last']
    (dest/'stage4_status.txt').write_text(''.join(f'{k}={v}\n' for k,v in status.items()))
report={'status':'AZAHAR PASS; REAL NEW3DS ACCEPTANCE PENDING','build':build,'candidate':candidate.relative_to(root).as_posix(),
        'runs':results,'hardware_default':'PHYSICAL pad; resource cache ON; detailed profiling OFF; no periodic gameplay SD reports',
        'raster':raster,'memory':after['memory'],'cache':after['cache'],'matched_pose_windows':after['matched_pose_windows'],
        'limitations':'Hardware road/garage acceptance pending; first-entry street decode peaks remain. Original Triangle Map state3 FAIL451/detail3 unsupported. Stage6 not started.'}
report_path=p/'reports/stage5-final-azahar.json';report_path.write_text(json.dumps(report,indent=2)+'\n')
handoff=root/'docs/3ds-stage5-final-handoff.md';content=handoff.read_text()
for k,v in {'PROFILE_SECONDS':results['profile']['map_seconds'],'PROFILE_LAPS':results['profile']['last']['route_laps'],
            'NORMAL_SECONDS':results['normal']['map_seconds'],'NORMAL_LAPS':results['normal']['last']['route_laps']}.items():content=content.replace('{{'+k+'}}',str(v))
assert '{{' not in content;handoff.write_text(content)
paths=[]
for base in ('3ds_port/source','3ds_port/include','3ds_port/shaders','3ds_port/patches','3ds_port/tools','3ds_port/tests','include','src/bodyprog','src/screens','src/main','src/maps/map0_s00','src/maps/characters','pc_port/include'):
    paths += [v for v in (root/base).rglob('*') if v.is_file() and '__pycache__' not in v.parts]
paths += [root/'src/maps'/n for n in ('particle.c','chara_util.c')]
paths += [root/'pc_port/src'/n for n in ('psx_memory.c','math_impl.c','cheryl_anim_info.c','d_800294f4_data.c')]
paths += [root/'pc_port/build_gen/extracted_data/map0_s00_extracted_data.c']
paths += [p/n for n in ('Makefile','Makefile.game','engine_sources.mk','native_map_data.ld','native_map_data.json','native_body_data.json')]
paths += list(candidate.iterdir())
allowed=('raster-grid.png','raster-final.png','pixels-surface.png','precision-surface.png','mask-surface.png','order-surface.png','garage-final.png')
paths += [evidence/n for n in allowed]
for label in ('profile','normal','before'):paths += [v for v in (evidence/label).rglob('*') if v.is_file()]
paths += [v for v in (p/'reports').glob('stage5-final-*') if v.is_file() and not v.name.startswith(('stage5-final-raster-surface','stage5-final-raster-corrected'))]
paths += list((root/'docs').glob('3ds-stage5*'))+[root/'docs/3ds-port.md']
paths += [v for v in root.glob('LICENSE*') if v.is_file()]
paths=sorted(set(v for v in paths if v.is_file()))
assert all('sh1_data' not in v.relative_to(root).parts and v.suffix.lower() not in ('.bin','.cue') for v in paths)
manifest={v.relative_to(root).as_posix():{'bytes':v.stat().st_size,'sha256':sha(v)} for v in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for v in paths:z.write(v,v.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for name,entry in manifest.items():
        data=z.read(name);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
report['archive']={'path':archive.relative_to(root).as_posix(),'bytes':archive.stat().st_size,'sha256':sha(archive),'verified_members':len(manifest)}
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'build':build['build'],'candidate':str(candidate),'archive':report['archive'],
                  'runs':{k:{f:v[f] for f in ('result','map_seconds','sample_count')} for k,v in results.items()}},indent=2))
