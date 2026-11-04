#!/usr/bin/env python3
"""Freeze the visually confirmed Level B candidate, never hardware acceptance."""
from pathlib import Path
import hashlib,json,shutil,struct,zipfile
port=Path(__file__).resolve().parents[1];root=port.parent
expected='f24e73aa67d9d7e196287c5183a761131dca5e716b41edeb27609fd39df7681a'
identity='stage4.3-src-a60cff5187d3053b'
run=port/'build/azahar/runs/20261024-132553-926'
candidate=port/'build/hardware-stage43-level-b'
evidence=port/'reports/azahar-stage43-level-b'
archive=port/'baselines/stage4.3-level-b-candidate.zip'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert not candidate.exists() and not evidence.exists() and not archive.exists()
assert sha(port/'silenthill_game.3dsx')==expected
assert (port/'silenthill_game.3dsx').stat().st_size==635476
assert json.loads((run/'run.json').read_text(encoding='utf-8-sig'))['build_sha256']==expected
assert sha(run/'silenthill_3ds.3dsx')==expected
assert not (root/'sh1_data/stage4_autoinput.txt').exists(),'One-use input fixture must be consumed'
assert sha(port/'baselines/stage4-level-a-accepted.zip')=='ff80832a2edc0b77e6dae2f44fe110d261dc66104f9c04b23fd570942f817b17'
assert 'regressions PASS' in (port/'reports/regressions-level-b.log').read_text()
candidate.mkdir();evidence.mkdir()
for suffix in ('.3dsx','.elf','.map','.smdh'):
    shutil.copy2(port/('silenthill_game'+suffix),candidate/('silenthill_game'+suffix))
for name in ('run.json','qt-config.ini','stage4_status.txt','azahar_log.txt','stdout.txt','stderr.txt'):
    if (run/name).exists():shutil.copy2(run/name,evidence/name)
shutil.copy2(root/'sh1_data/stage4_status.txt',evidence/'terminal-status.txt')
shot=port/'build/azahar/user/screenshots/_24.10.26_13.29.17.753.png'
assert shot.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
shutil.copy2(shot,evidence/'first-map0-scene.png')
width,height=struct.unpack_from('>II',shot.read_bytes(),16)
report={'status':'FIRST RECOGNIZABLE ORIGINAL MAP0_S00 FRAME OBSERVED IN AZAHAR',
    'hardware_acceptance':'PENDING REAL NEW NINTENDO 3DS',
    'stop':'Development stopped after one visual scene inspection; no Stage 5 or gameplay polishing',
    'build':identity,'bytes':635476,'sha256':expected,
    'candidate':candidate.relative_to(root).as_posix(),
    'acceptance_path':'original boot/title -> two physical-pad-boundary B pulses -> original Normal New Game -> original map0_s00 load/camera/GTE/OT -> PICA',
    'direct_map_entry':False,'hardware_input':'PHYSICAL; diagnostic input file absent',
    'observed':['Harry from behind','foggy street/road geometry','snow and a tree fragment',
        'original subtitle: Cheryl. Where could you...'],
    'first_frame_evidence':{'checkpoint':'MAP0_FRAME_SUBMITTED','phase':'MAP0_OT_BUILT','first_failure':0,
        'state':11,'step':2,'reads':42,'uploads':44,'recorded_map_frames':101},
    'later_bounded_halt':{'code':432,'operation':'texture cache budget','detail':32,'map_frames':186,
        'note':'Last recognizable scene remains visible. Deliberately not fixed after the visual stop.'},
    'rendering_gaps':['PSX destination pixel-mask rejection not emulated',
        'rectangular fog/lighting overlays','approximate STP/semitransparency and framebuffer feedback',
        'geometry, texture, animation and clipping completeness beyond this frame not accepted'],
    'intentionally_skipped':['SPU/audio output','XA/music/voices/SFX output','FMV decode/presentation',
        'vibration','memory-card devices: unavailable; original no-card transition retained'],
    'screenshot':{'path':(evidence/'first-map0-scene.png').relative_to(root).as_posix(),
        'sha256':sha(shot),'width':width,'height':height},
    'tests':{'stage1_to_stage41_regressions':'PASS','native_packet_contracts':'PASS',
        'retail_MIPS_SetPriority_oracle':'PASS','ARM_original_path':'three map-state frames, no invalid memory access or failure',
        'ELF_map_budget_and_desktop_exclusion':'PASS'},
    'limitations':['one resident ARM map: map0_s00','other states/resources fail explicitly',
        'idle title attract demo is outside this slice','bottom HUD error flag can remain sticky; inspect the complete SD status report']}
(port/'reports/stage4.3-level-b-azahar.json').write_text(json.dumps(report,indent=2)+'\n')
paths=[]
for base in ('3ds_port/source','3ds_port/include','3ds_port/shaders','3ds_port/patches','3ds_port/tools',
             'include','src/bodyprog','src/screens','src/maps/map0_s00','src/maps/characters','pc_port/include'):
    paths += [p for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [root/'src/maps'/n for n in ('particle.c','chara_util.c')]
paths += [root/'pc_port/src'/n for n in ('psx_memory.c','math_impl.c','cheryl_anim_info.c','d_800294f4_data.c')]
paths += [root/'pc_port/build_gen/extracted_data/map0_s00_extracted_data.c']
paths += [root/'src/main'/n for n in ('main.c','fsqueue_1.c','fsqueue_2.c','fsqueue_3.c','fileinfo.c','fsmem.c')]
paths += [port/n for n in ('Makefile','Makefile.game','engine_sources.mk','native_map_data.ld','native_map_data.json','native_body_data.json')]
paths += list(candidate.iterdir())+list(evidence.iterdir())
paths += [port/'reports'/n for n in ('stage4.3-level-b-azahar.json','game-build-level-b.json',
    'game-path-arm.json','game-gpu-arm.json','retail-priority-contract.json','native-data-provenance.json','regressions-level-b.log')]
manifest={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(set(paths)):z.write(p,p.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
report['source_archive']={'path':archive.relative_to(root).as_posix(),'sha256':sha(archive)}
(port/'reports/stage4.3-level-b-azahar.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','hardware_acceptance','candidate','bytes','sha256','source_archive')},indent=2))
