"""Qualify R4 against its normal ELF, preserved CPU variant and actual PICA runs."""
import hashlib,json,struct,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def read(f):return json.loads(f.read_text(encoding='utf-8-sig'))
def status(f):return dict(line.split('=',1) for line in f.read_text().splitlines() if '=' in line)
def states(s):return [list(map(int,s[k].split(','))) for k in sorted((k for k in s if k.startswith('state_') and k[6:].isdigit()),key=lambda k:int(k[6:]))]
elfsha=sha(p/'silenthill_game.elf');suite=read(p/'reports/stage10-foundation-regressions.json')
assert suite['status']=='PASS' and len(suite['tests'])==28 and suite['elf_sha256']==elfsha
for name in ('packet','status','modern'):
    r=read(p/f'reports/stage10-{name}-arm.json');assert r['status']=='PASS' and r['elf_sha256']==elfsha
sampling=read(p/'reports/stage10-status-sampling.json')
assert len(sampling['glyphs'])==84 and len(sampling['subpixel_phases'])==64
assert min(r['filtered_crossbar'] for r in sampling['subpixel_phases'])>.3
window=read(p/'reports/stage10-r4-window-runtime.json');wd=read(p/'build/stage10-r4-window-cpu/manifest.json')
assert wd['base_elf_sha256']==elfsha and window['elf_sha256']==wd['elf_sha256']
assert sha(p/'build/stage10-r4-window-cpu/diagnostic.elf')==wd['elf_sha256']
assert window['window_seen'] and window['after_window']>=20 and not any(window['run'][k] for k in ('failure','invalid','exception'))
peak=max(window['rows'],key=lambda r:r['used'])
assert 131072<peak['used']<=peak['capacity']==262144 and peak['packet_walk_exact']
assert peak['retail_tag_equivalent']<131072 and peak['pose'][2]==20 and peak['pose'][-1]==5
reload=read(p/'reports/stage10-reload-runtime.json');rd=read(p/'build/stage10-dev-scene-3/manifest.json')
assert rd['base_elf_sha256']==elfsha and reload['elf_sha256']==rd['elf_sha256'] and len(reload['cases'])==2
reload_cases=[]
for c in reload['cases']:
    assert c['ammo_seed_tick'] and c['reload_done'] and c['aim_released']==c['reload_done']+c['hold_after_reload']
    assert not any(c['run'][k] for k in ('failure','invalid','exception'))
    assert not c['final'][9] and not c['final'][15] and c['final'][2] in (0,1,2)
    reload_cases.append({k:c[k] for k in ('hold_after_reload','ammo_seed_tick','reload_start','reload_done','aim_released')})
ui=status(p/'reports/stage10-r4-ui/menus-status.txt');ud=read(p/'reports/stage10-r4-ui/manifest.json')
assert ud['base_elf_sha256']==elfsha and ui['build']==ud['build'] and ui['checkpoint']=='EXIT' and ui['first_failure']=='0'
route=states(ui);first=next(i for i,r in enumerate(route) if r[3]==14);games=[]
for row in route[first:]:
    if not games or games[-1]!=row[3]:games.append(row[3])
assert games==[14,15,14,11],games
before=next(r for r in reversed(route[:first]) if r[3]==11)
assert before[9:12]==route[-1][9:12]
for name in ('status','map'):
    data=(p/f'reports/stage10-r4-ui/{name}.bmp').read_bytes()
    assert data[:2]==b'BM' and struct.unpack_from('<2i',data,18)==(320,240)
gate=status(p/'reports/stage10-r4-cafe/status.txt');gd=read(p/'reports/stage10-r4-cafe/manifest.json')
assert gd['base_elf_sha256']==elfsha and gate['build']==gd['build']
assert gate['first_failure']=='0' and gate['checkpoint']=='EXIT' and gate['map_idx']=='10' and gate['game_state']=='11'
assert gate['dev_combat_died']==gate['dev_combat_event_done']==gate['dev_radio_picked_up']=='1'
route=states(gate);assert any(r[1]==1 and r[8]==9 for r in route) and route[-1][1]==10
assert int(gate['packet_peak'])>131072 and gate['readback_direct_mismatches']==gate['gpu_duplicate_presents']=='0'
assert int(gate['gpu_partial_flushes'])>0 and int(gate['readback_gpu_copies'])>0
trace=[list(map(int,v.split(','))) for k,v in gate.items() if k.startswith('feedback_trace_') and k[15:].isdigit()]
assert any(r[0]==2 and r[2] in (10,20) for r in trace)
early=(p/'reports/stage10-r4-cafe/feedback-early.bmp').read_bytes();late=(p/'reports/stage10-r4-cafe/feedback-late.bmp').read_bytes()
assert struct.unpack_from('<2i',early,18)==struct.unpack_from('<2i',late,18)==(400,240)
assert len(early)==len(late)==288054
lookup={};brighter=0
for i,(a,b) in enumerate(zip(early[54:],late[54:])):
    key=((i//3)%400>=320,(a*31+127)//255);lookup.setdefault(key,set()).add((b*31+127)//255);brighter+=b>a
assert not brighter and all(len(values)==1 for values in lookup.values())
pixels=read(p/'reports/stage8-r2-pixel-index.json')
assert pixels['status']=='PASS' and pixels['renderer_object_sha256']==sha(p/'build-game/render_3ds.o')
surface=status(p/'reports/stage10-r4-feedback-surface.txt');assert surface['result']=='PASS' and surface['bad_samples']=='0'
preserved=[]
with zipfile.ZipFile(p/'baselines/stage10-r3.zip') as z:
    for name in ('src/maps/characters/air_screamer.c','src/maps/map0_s01/map0_s01_events.c','src/bodyprog/player_control.c','src/bodyprog/text/text_draw.c','src/bodyprog/items/item_screens_3.c','src/bodyprog/bodyprog_mapscreen_80066D90.c'):
        assert z.read(name)==(root/name).read_bytes(),name
        preserved.append(name)
    def boot(s):
        a=s.index('void GameState_Boot_Update(');b=s.find('\nvoid ',a+1);return s[a:b]
    assert boot(z.read('src/bodyprog/sys/game_main.c').decode())==boot((root/'src/bodyprog/sys/game_main.c').read_text())
assert sha(root/'sh1_data/memcard.mcr')=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
phase_names=['idle','dialogue','window_entry','monster_active','combat','death','cleared_and_exit'];phases=[]
hz=int(gate['dev_cafe_profile_hz'])
for i,name in enumerate(phase_names):
    _,count,ticks,worst,packet=map(int,gate[f'dev_cafe_profile_{i}'].split(','));assert count>0
    phases.append(dict(phase=name,samples=count,emulator_input_interval_ms=ticks/hz*1000/count,
        emulator_fps=count*hz/ticks,packet_peak=packet,hardware_measurement=False))
report=dict(status='PASS',normal_elf_sha256=elfsha,foundation_tests=28,window_peak=peak,reload=reload_cases,
    actual_cafe_window_combat_radio_exit_to_map2=True,original_map_roundtrip=games,pica_pixels=True,
    feedback_pixels=96000,feedback_brighter_channels=brighter,feedback_rgb5_lut_single_valued=True,
    readback_direct_mismatches=0,duplicate_lcd_presents=0,cafe_phases=phases,
    performance_scope='Azahar observation; not New 3DS FPS or hardware performance acceptance',
    original_sources_preserved=preserved,boot_function_preserved=True,memory_card_unchanged=True,
    controls_live='Tank; C-stick camera only',controls_modern_hybrid='Architecture/input contract only; not implemented',
    hardware_accepted=False,stage10_complete=False)
(p/'reports/stage10-r4-runtime-qualification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(status='PASS',elf=elfsha,foundation_tests=28,window_peak=peak['used'],reload_cases=2,actual_cafe_exit=True),indent=2))
