#!/usr/bin/env python3
"""Freeze a verified emulator candidate; hardware acceptance stays pending."""
import argparse,ast,contextlib,hashlib,io,json,runpy,shutil,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);parser.add_argument('--label',default='stage7-normal');args=parser.parse_args()
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
info=read(args.run/'run.json');analysis=read(args.run/(args.label+'-analysis.json'))
validation=read(p/'reports/stage7-validation.json')
required={'normal_route','original_pickup','bottom_inventory','navigate_equip_use','original_save_ui',
          'native_exit','restart_and_original_load','restored_cafe_state','native_wide_geometry',
          'same_camera_comparison','bounded_memory','pixel_regressions','component_regressions'}
assert required<=validation['checks'].keys() and all(validation['checks'][k] for k in required)
assert validation['status']=='AZAHAR VERIFIED; HARDWARE PENDING'
assert validation['build']==info['build_identity'] and validation['sha256']==info['build_sha256']
assert analysis['variant']=='NORMAL_NEW_GAME' and all(analysis['route'].values())
assert analysis['functional_cafe_seconds']>=596 and analysis['sha256']==info['build_sha256']
assert not info['gdb_stub'] and not info['diagnostic_gameplay']
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
assert sha(p/'silenthill_game.3dsx')==info['build_sha256']==sha(args.run/'silenthill_3ds.3dsx')
assert sha(p/'build/hardware-stage6-cafe/silenthill_game.3dsx')=='a48506efab80c29ef57dbc55c2083a09ab69855f456ee544291cdc376d83b674'
assert sha(p/'baselines/stage6-cafe-candidate.zip')=='83d33b3cfce68de1686baa4bb9a28500cea495032e573b6945774e9c4a46dd98'
assert read(p/'reports/stage6-accepted.json')['status']=='HARDWARE ACCEPTED'
with contextlib.redirect_stdout(io.StringIO()):identity=runpy.run_path(str(p/'tools/build_identity.py'))
assert identity['identity']==info['build_identity']
for name in ('stage4_autoinput.txt','stage5_profile.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt'):
    assert not (root/'sh1_data'/name).exists(),name
for name in ('stage7-card-tests','stage7-save-arm','stage7-tmd-arm','stage7-gpu-extensions-arm'):
    assert read(p/('reports/'+name+'.json'))['status']=='PASS',name
for name in ('stage7-contract-arm','stage7-pose-arm'):
    assert read(p/('reports/'+name+'.json'))['failure_bits']==0,name
assert read(p/'reports/stage7-menu-arm.json')['passed']
assert read(p/'reports/stage7-particle-arm.json')['closed_convex_contour']
for kind in ('regular','precision','order','mask'):
    assert read(p/('reports/stage7-pixel-'+kind+'.json'))['status']=='PASS'
candidate=p/'build/hardware-stage7-native-wide';archive=p/'baselines/stage7-native-wide-candidate.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
evidence=p/'reports/azahar-stage7-normal';assert not evidence.exists();evidence.mkdir()
for name in ('run.json','qt-config.ini','stage4_status.txt',args.label+'-samples.json',
             args.label+'-result.json',args.label+'-analysis.json'):
    shutil.copy2(args.run/name,evidence/name)
if (args.run/'stage7-normal-samples.json').exists():shutil.copy2(args.run/'stage7-normal-samples.json',evidence/'stage7-normal-samples.json')
if (args.run/'azahar_log.txt').exists():shutil.copy2(args.run/'azahar_log.txt',evidence/'azahar_log.txt')
log=p/'build/azahar/user/log/azahar_log.txt'
if log.exists():shutil.copy2(log,evidence/'azahar_log-last-session.txt')
record={'status':'HARDWARE PENDING','build':info['build_identity'],'binary':(candidate/'silenthill_game.3dsx').relative_to(root).as_posix(),
        'bytes':info['build_bytes'],'sha256':info['build_sha256'],'normal_route_run':args.run.name,
        'validation':validation,'normal_route_analysis':analysis,
        'card':{'path':'sdmc:/3ds/silenthill/memcard.mcr','format':'PS1_RAW_128K','bytes':131072},
        'hardware_acceptance':'Requires user validation on real New Nintendo 3DS'}
report=p/'reports/stage7-candidate.json';report.write_text(json.dumps(record,indent=2)+'\n')
with zipfile.ZipFile(p/'baselines/stage6-cafe-candidate.zip') as z:previous=json.loads(z.read('manifest.json'))
paths=[root/n for n in previous if not n.startswith('3ds_port/build/')]+identity['paths']
prepare=ast.parse((p/'tools/prepare_psycross.py').read_text())
upstream_inputs=next(ast.literal_eval(n.value) for n in prepare.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='sources' for t in n.targets))
upstream=root/'pc_port/PsyCross';paths += [upstream/n for n in upstream_inputs]
paths += list((upstream/'include').rglob('*'))
paths += [f for f in upstream.iterdir() if f.is_file() and f.name.lower().startswith(('license','copying'))]
for directory in (candidate,evidence,p/'reports/azahar-stage7-systems',p/'tools',p/'tests'):
    paths += [f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
paths += list((p/'reports').glob('stage7-*'))+list((root/'docs').glob('3ds-stage7-*'))
paths += [p/'reports/stage6-accepted.json',root/'docs/3ds-stage6-accepted.md',p/'build-game/flags',p/'build/build_identity.h',report,root/'.gitmodules']
paths=sorted(set(f for f in paths if f.is_file()))
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin','.cue','.mcr') for f in paths)
manifest={f.relative_to(root).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(manifest)+1
    for name,expected in manifest.items():
        data=z.read(name);assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256'],name
record['archive']={'path':archive.relative_to(root).as_posix(),'bytes':archive.stat().st_size,'sha256':sha(archive),'verified_members':len(manifest)}
report.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('validation','normal_route_analysis')},indent=2))
