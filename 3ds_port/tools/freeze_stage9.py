"""Freeze the audio candidate, never grant hardware acceptance."""
from pathlib import Path
import difflib,hashlib,json,re,shutil,struct,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
baseline=read(p/'reports/stage9-baseline.json')
assert baseline['source_differences']==[]
assert sha(p/'baselines/stage8-diagnostic-r2.zip')==baseline['archive_sha256']
assert sha(p/'build/hardware-stage8-diagnostic-r2/silenthill_game.3dsx')==baseline['binary_sha256']
with zipfile.ZipFile(p/'baselines/stage8-diagnostic-r2.zip') as z:
    prior=json.loads(z.read('manifest.json'))
allowed={'3ds_port/Makefile.game','3ds_port/source/main_game.c','3ds_port/source/game_services.c',
         '3ds_port/tools/build_identity.py','3ds_port/tools/run_azahar.ps1',
         '3ds_port/tools/run_arm_game.py','3ds_port/tools/test_game_gpu_arm.py'}
changed=[]
for name,v in prior.items():
    if not name.startswith(('src/','include/','pc_port/','3ds_port/source/','3ds_port/include/','3ds_port/tools/')):continue
    f=root/name
    if not f.is_file() or sha(f)!=v['sha256']:changed.append(name)
assert set(changed)<=allowed,changed
elf_sha=sha(p/'silenthill_game.elf')
audio=read(p/'reports/stage9-audio-arm.json');reg=read(p/'reports/stage9-regressions.json')
ndsp=read(p/'reports/stage9-ndsp-arm.json')
assert audio['status']==reg['status']=='PASS'
assert audio['elf_sha256']==reg['elf_sha256']==elf_sha
assert ndsp['status']=='PASS' and ndsp['elf_sha256']==elf_sha
assert len(reg['results'])==14
assert 'All PsyX_SPUCore standalone tests passed.' in (p/'reports/stage9-core-tests.log').read_text()
assert 'PASS: 48 PCM/voice-state/SPU-RAM/ENDX cases' in (p/'reports/stage9-core-tests.log').read_text()
assert (p/'reports/stage9-core-equivalence-original.txt').read_bytes()==(p/'reports/stage9-core-equivalence-native.txt').read_bytes()
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
status=dict(line.split('=',1) for line in (p/'reports/azahar-stage9-cafe/final-cafe.txt').read_text().splitlines() if '=' in line)
identity=re.search(r'"(stage9[^\"]+)"',(p/'build/build_identity.h').read_text())[1]
assert status['build']==identity and status['first_failure']=='0' and status['report_complete']=='1'
assert status['game_state']=='11' and status['map_idx']=='1'
assert status['audio_ndsp_result']=='0' and status['audio_started']=='1'
assert int(status['audio_nonzero_samples'])>0
assert sha(root/'sh1_data/memcard.mcr').upper()==read(p/'reports/azahar-stage9-cafe/card-before.json')['Hash']
for name in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/name).exists(),name
assert not (p/'build/azahar/user/sdmc/3ds/dspfirm.cdc').exists()
def sections(path):
    b=path.read_bytes();off=struct.unpack_from('<I',b,32)[0];size,count,strings=struct.unpack_from('<HHH',b,46)
    h=[struct.unpack_from('<10I',b,off+i*size) for i in range(count)]
    names=b[h[strings][4]:h[strings][4]+h[strings][5]]
    return {names[s[0]:].split(b'\0')[0].decode():s[5] for s in h}
current=sections(p/'silenthill_game.elf');old=sections(p/'build/hardware-stage8-diagnostic-r2/silenthill_game.elf')
candidate=p/'build/hardware-stage9-audio-r1';archive=p/'baselines/stage9-audio-r1.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
shutil.copy2(root/'docs/3ds-stage9-handoff.md',candidate/'README.md')
(candidate/'diagnostics').mkdir()
(candidate/'diagnostics/stage6_observe.txt').write_bytes(b'OBSERVE\n')
record=dict(status='HARDWARE CANDIDATE; USER NEW 3DS AUDIO TEST PENDING',hardware_accepted=False,
    baseline=baseline,build=identity,binary=str((candidate/'silenthill_game.3dsx').relative_to(root)),
    bytes=(candidate/'silenthill_game.3dsx').stat().st_size,sha256=sha(candidate/'silenthill_game.3dsx'),
    elf_sha256=elf_sha,changed_baseline_sources=changed,
    preservation='All frozen gameplay/map/renderer/input/save sources unchanged; only native audio integration and test/build tools changed',
    sections={n:current[n] for n in ('.text','.rodata','.data','.bss')},
    bss_delta_to_R2=current['.bss']-old['.bss'],audio_linear_bytes=8192,audio_worker_stack_bytes=32768,
    audio_ARM=audio,ndsp_control_ARM=ndsp,regressions=reg,
    emulator=dict(context='Azahar HLE DSP; emulator-only placeholder, no real firmware validation',
        evidence='3ds_port/reports/azahar-stage9-cafe/final-cafe.txt',
        metrics={n:status[n] for n in status if n.startswith('audio_') or n in ('recent_fps','recent_work_ms','map_idx','player_state')}),
    memory_card_unchanged=True,hardware_gameplay_validation_boundary='Cafe only',
    XA_and_spoken_dialogue='DEFERRED',KDT_music='Original sequencer connected; ARM key-on/PCM/timer tested',
    out_of_scope_backlog='docs/3ds-backlog.md')
observations={}
for mode in (30,60):
    file=p/f'reports/azahar-stage9-cafe/final-cafe-{mode}.txt'
    if file.exists():
        values=dict(line.split('=',1) for line in file.read_text().splitlines() if '=' in line)
        assert values['build']==identity and values['stage8_fps_limit']==str(mode)
        observations[str(mode)]={n:values[n] for n in ('recent_fps','recent_work_ms','recent_sim_speed',
            'audio_queue_starves','audio_ndsp_dropped','player_x','player_z','player_yaw')}
record['emulator']['same_save_cap_observations']=observations
report=p/'reports/stage9-candidate.json';report.write_text(json.dumps(record,indent=2)+'\n')
diff=[]
with zipfile.ZipFile(p/'baselines/stage8-diagnostic-r2.zip') as z:
    for name in changed+['3ds_port/Makefile.game']:
        if name in prior:
            old=z.read(name).decode('utf-8-sig').splitlines(keepends=True)
            new=(root/name).read_text(encoding='utf-8-sig').splitlines(keepends=True)
            diff.extend(difflib.unified_diff(old,new,fromfile='accepted-r2/'+name,tofile='stage9/'+name))
(p/'reports/stage9-baseline-changes.patch').write_text(''.join(diff))
paths={root/n for n in prior if (root/n).is_file() and not n.startswith(('3ds_port/build/','3ds_port/build-game/','3ds_port/reports/','docs/'))}
for directory in (p/'source',p/'include',p/'tools',p/'tests',p/'shaders',p/'patches',candidate,p/'build/audio',p/'reports/azahar-stage9-cafe'):
    paths.update(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths.update(root/n for n in read(p/'build/audio/inputs.json'))
paths.update(root/n for n in ('pc_port/PsyCross/include/psx/libspu.h',
    'pc_port/PsyCross/include/psx/types.h','pc_port/PsyCross/include/PsyX/PsyX_public.h',
    'pc_port/PsyCross/src/audio/PsyX_SPUReverb.cpp','pc_port/PsyCross/src/audio/PsyX_SPUReverb.h',
    'pc_port/PsyCross/src/audio/PsyX_IdealReverb.h','pc_port/PsyCross/src/audio/PsyX_ReferenceReverb.h',
    'pc_port/PsyCross/src/audio/PsyX_ReferenceResampler.h'))
paths.update(f for f in (p/'reports').glob('stage9-*') if f.is_file() and f.stat().st_size<5*1024*1024)
paths.update((root/'docs/3ds-stage9-handoff.md',root/'docs/3ds-backlog.md',root/'docs/3ds-stage8-r2-accepted.md',
              p/'build/build_identity.h',p/'build-game/flags',p/'Makefile.game'))
paths=sorted(paths)
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin','.cue','.mcr','.cdc') for f in paths)
manifest={str(f.relative_to(root)).replace('\\','/'):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:z.write(f,str(f.relative_to(root)))
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for n,v in manifest.items():
        b=z.read(n);assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'],n
record.update(archive_sha256=sha(archive),verified_archive_members=len(manifest))
report.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('status','build','binary','bytes','sha256','archive_sha256','bss_delta_to_R2','verified_archive_members')},indent=2))
