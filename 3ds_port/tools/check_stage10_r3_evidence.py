"""Qualify R3 evidence against the exact normal ELF and isolated dev variants."""
import hashlib,json,struct
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def status(path):return dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
def states(s):
    return [list(map(int,s[k].split(','))) for k in sorted((k for k in s if k.startswith('state_') and k[6:].isdigit()),key=lambda k:int(k[6:]))]
elfsha=sha(p/'silenthill_game.elf');suite=read(p/'reports/stage10-foundation-regressions.json')
assert suite['status']=='PASS' and len(suite['tests'])==26 and suite['elf_sha256']==elfsha
reload=read(p/'reports/stage10-reload-runtime.json');dev=read(p/'build/stage10-dev-scene-3/manifest.json')
assert reload['elf_sha256']==dev['elf_sha256'] and dev['base_elf_sha256']==elfsha
reload_cases=[]
for case in reload['cases']:
    assert case['reload_done'] and case['aim_released']==case['reload_done']+case['hold_after_reload']
    assert case['final'][2] in (0,1,2) and not case['final'][9] and not case['final'][15]
    assert all(s['v'][9] and s['v'][15] for s in case['steps'] if case['reload_done']+2<=s['t']<case['aim_released'])
    assert not any(case['run'][k] for k in ('failure','exception','invalid'))
    reload_cases.append(dict(hold=case['hold_after_reload'],start=case['reload_start'],done=case['reload_done'],
        release=case['aim_released'],actual_loaded_magazine=max(s['v'][10] for s in case['steps'] if s['t']<case['reload_start'])))
assert len(reload_cases)==2
menus=[]
for missing,name,folder in ((False,'map-roundtrip','stage10-dev-scene-5-menus'),(True,'map-unavailable','stage10-dev-scene-5-menus-no-map')):
    s=status(p/f'reports/stage10-r3-final-{name}.txt');d=read(p/f'build/{folder}/manifest.json')
    assert d['base_elf_sha256']==elfsha and s['build']==d['build']
    assert s['checkpoint']=='EXIT' and s['first_failure']=='0' and s['game_state']=='11'
    rows=states(s);first=next(i for i,r in enumerate(rows) if r[3]==14)
    games=[]
    for r in rows[first:]:
        if not games or games[-1]!=r[3]:games.append(r[3])
    assert games==([14,11] if missing else [14,15,14,11]),games
    assert rows[first][-3:]==rows[-1][-3:],'Map menu changed Harry position/health'
    menus.append(dict(missing_map=missing,games=games,build=d['build'],normal_base=elfsha))
air=read(p/'reports/stage10-air-retail-comparison.json')
assert air['status']=='PASS' and len(air['cases'])==90 and air['elf_sha256']==elfsha
pixels=read(p/'reports/stage8-r2-pixel-index.json')
assert pixels['status']=='PASS' and pixels['renderer_object_sha256']==sha(p/'build-game/render_3ds.o')
gate=status(p/'reports/stage10-r3-cafe-exit-pica.txt')
gate_dev=read(p/'build/stage10-dev-scene-2-exit/manifest.json')
assert gate_dev['base_elf_sha256']==elfsha and gate['build']==gate_dev['build']
assert gate['first_failure']=='0' and gate['checkpoint']=='EXIT' and gate['map_idx']=='10' and gate['game_state']=='11'
route=states(gate);assert any(r[1]==1 for r in route) and any(r[1]==10 and r[3] in (10,20) for r in route) and route[-1][1]==10
trace=[list(map(int,v.split(','))) for k,v in gate.items() if k.startswith('feedback_trace_') and k[15:].isdigit()]
assert any(r[0]==2 and r[2] in (10,20) for r in trace),'Missing actual location-transition SPRT evidence'
assert int(gate['readback_gpu_copies'])>0 and int(gate['readback_linear_bytes'])==2097152
early=(p/'reports/stage10-r3-ui/feedback-early.bmp').read_bytes()
late=(p/'reports/stage10-r3-ui/feedback-late.bmp').read_bytes()
assert struct.unpack_from('<2i',early,18)==struct.unpack_from('<2i',late,18)==(400,240)
assert len(early)==len(late)==288054
lookup={};brighter=0
for i,(a,b) in enumerate(zip(early[54:],late[54:])):
    # Each original SPRT can observe a different vblank modulation level.
    # Inside either region every unchanged-position source value must undergo
    # the same RGB5 transform. A pitch/tiling/resampling error breaks this LUT.
    key=((i//3)%400>=320,(a*31+127)//255)
    lookup.setdefault(key,set()).add((b*31+127)//255);brighter+=b>a
assert not brighter and all(len(values)==1 for values in lookup.values())
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
images={}
for name in ('status-before','status-after','map','map-unavailable'):
    path=p/f'reports/stage10-r3-ui/{name}.bmp';data=path.read_bytes()
    assert data[:2]==b'BM' and struct.unpack_from('<2i',data,18)==(320,240)
    images[name]=dict(sha256=sha(path),bytes=len(data))
report=dict(status='PASS',normal_elf_sha256=elfsha,foundation_tests=26,reload=reload_cases,menus=menus,
    air_mips_native_cases=90,air_scope=air['scope'],pica_semantics=True,actual_cafe_exit_to_map2=True,
    actual_feedback_trace=True,readback_direct_mismatches=int(gate['readback_direct_mismatches']),
    actual_feedback_pixels=96000,feedback_brighter_channels=brighter,feedback_rgb5_lut_single_valued=True,
    ui_images=images,memory_card_unchanged=True,hardware_accepted=False,stage10_complete=False,
    cafe_performance_blocker_closed=False,hardware_feedback_defect_closed=False)
(p/'reports/stage10-r3-runtime-qualification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))
