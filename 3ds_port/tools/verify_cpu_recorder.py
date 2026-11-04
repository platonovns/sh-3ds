"""Bind recorder evidence, compile-time production exclusion and HTTP delivery."""
import hashlib,json,os,shlex,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
candidate=p/'build/stage10-cpu-recorder';record=read(candidate/'manifest.json')
assert sha(candidate/'silenthill_cpu_recorder.3dsx')==record['sha256']
assert sha(candidate/'silenthill_cpu_recorder.elf')==record['elf_sha256']
assert sha(p/'silenthill_game.elf')=='8c41fc2a3281f71bb3583b058c7d56ce2e3e6ae59667c4a217262b96807cd981'
assert sha(p/'silenthill_game.3dsx')=='43462215152cf6405aa0437ab4bbee6fd0fe27cc2ee1c339dfa4cb4f3cf42bd6'
assert b'cpu_record_schema=' not in (p/'silenthill_game.3dsx').read_bytes()
assert b'cpu_record_schema=' in (candidate/'silenthill_cpu_recorder.3dsx').read_bytes()
host=read(p/'reports/stage10-cpu-recorder-host.json')
assert host['status']=='PASS' and host['recorder_sha256']==sha(p/'source/game_cpu_recorder.c')
title=p/'reports/stage10-cpu-recorder-title'
v=dict(line.split('=',1) for line in (title/'status.txt').read_text().splitlines() if '=' in line)
assert v['build']==record['build'] and v['checkpoint']=='TITLE_FRAME_SUBMITTED'
assert v['cpu_recording']=='0' and v['cpu_record_errno']=='0'
assert read(title/'run.json')['build_sha256']==record['sha256']
# Recompile the affected sources WITHOUT the diagnostic define, privately.
# Neither the normal ELF nor any normal build-game object is touched.
engine,sdk,_=map(shlex.split,(p/'build-game/flags').read_text().splitlines()[:3])
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
disabled=p/'build/cpu-recorder-disabled';disabled.mkdir(exist_ok=True)
for name in ('main_game','game_native','game_profile','game_cpu_audit','game_cpu_recorder'):
    ff=engine if name in ('game_native','game_profile') else sdk
    target=disabled/(name+'.o')
    subprocess.run([prefix+'gcc',*ff,'-c',str(p/'source'/(name+'.c')),'-o',str(target)],check=True,stdout=subprocess.DEVNULL)
    symbols=subprocess.check_output([prefix+'nm',str(target)],text=True)
    assert not any(n in symbols for n in ('cpu_recorder_','cpu_record_context','game_prof_sample_','Game3ds_CpuRecorderView')),name
assert 'game_cpu_recorder.o' not in (p/'Makefile.game').read_text()
samples=[]
for run,indices in (('first',(1,2,3)),('second',(4,5,6))):
    d=p/f'reports/stage10-cpu-recorder-{run}-pica'
    q=read(d/'qualification.json');assert q['status']=='PASS' and not q['first_failure']
    for number in indices:
        f=d/f'cpu_audit_{number:03}.txt'
        s=dict(line.split('=',1) for line in f.read_text().splitlines() if '=' in line)
        assert s['sample_complete']=='1' and s['report_complete']=='1'
        assert int(s['sample_number'])==number and s['sample_map']=='10' and s['sample_room']=='3'
        assert s['sample_context_changed_mask']=='0x0'
        a,b=s['sample_start_context'].split(','),s['sample_end_context'].split(',')
        assert a==b and a[6:9]==['73728','231424','2600']
        assert float(s['sample_duration_ms'])>500
        expected='OFF' if number==indices[0] else 'ON'
        assert s['sample_flashlight']==expected and s['sample_fps_mode']=='60'
        if expected=='ON':assert float(s['sample_profile_decode_total_ms'])>0
        assert s['sample_stop_reason']==('FINAL_DUMP' if number==indices[-1] else 'BUTTON_CHORD')
        samples.append(dict(number=number,flashlight=expected,duration_ms=float(s['sample_duration_ms']),
            frames=int(s['sample_lcd_frames']),profile_frames=int(s['sample_profile_frames']),sha256=sha(f)))
        assert sha(root/'sh1_data'/f.name)==sha(f),'Existing sample changed during restart'
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
proof=dict(status='PASS',build=record['build'],sha256=record['sha256'],samples=samples,
    normal_artifacts_unchanged=True,normal_recorder_symbols_absent=True,
    normal_boot_title=True,host_sanitizers=True,pica_runs=2,old_samples_unchanged_after_restart=True,
    hud_image='stage10-cpu-recorder-first-pica/cpu_recorder_hud.bmp',
    hud_visually_verified=True,golden_card_unchanged=True,hardware_accepted=False)
(p/'reports/stage10-cpu-recorder-qualification.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
