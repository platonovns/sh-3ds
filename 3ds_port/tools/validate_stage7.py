#!/usr/bin/env python3
"""Assemble evidence gates for the emulator candidate, never hardware acceptance."""
import argparse,hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parents[1];ev=p/'reports/azahar-stage7-systems'
parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);parser.add_argument('--label',default='stage7-final');a=parser.parse_args()
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
info=read(a.run/'run.json');analysis=read(a.run/(a.label+'-analysis.json'))
assert info['build_sha256']==sha(p/'silenthill_game.3dsx')==analysis['sha256']
assert all(analysis['route'].values()) and analysis['variant']=='NORMAL_NEW_GAME'
assert analysis['functional_cafe_seconds']>=596
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
labels=['final-wide','final-classic','final-wide-again','final-pickup-dialog','final-inventory',
        'final-equipped','final-used','final-flashlight-dialog','final-flashlight-inventory','final-map-pickup',
        'final-save-screen','final-save-complete','final-exit','final-loaded',
        'final-loaded-movement','final-loaded-inventory']
records={name:read(ev/(name+'.json')) for name in labels}
for name,r in records.items():
    assert r['run']['build_sha256']==info['build_sha256'],name
    assert r['status']['build']==info['build_identity'] and r['status']['first_failure']=='0',name
    assert r['status']['report_complete']=='1',name
s=lambda name:records[name]['status']
assert s('final-pickup-dialog')['player_state']=='10' and s('final-pickup-dialog')['sys_step1']=='2'
assert s('final-inventory')['game_state']=='14' and s('final-inventory')['stage7_display']=='1'
assert s('final-inventory')['stage7_viewport']=='320,448' and int(s('final-inventory')['inventory_count'])==2
assert s('final-equipped')['inventory_equipped']=='160'
assert int(s('final-used')['inventory_count'])==1 and int(s('final-used')['picked_up_item_count'])==2
assert s('final-flashlight-dialog')['player_state']=='10' and int(s('final-flashlight-inventory')['inventory_count'])==2
assert s('final-flashlight-dialog')['map_event']=='7'
assert s('final-map-pickup')['stage7_viewport']=='320,448' and s('final-map-pickup')['stage7_display']=='0'
assert s('final-save-screen')['game_state']=='16'
saved=s('final-save-complete');loaded=s('final-loaded')
assert int(loaded['map_frames'])>=300 and int(loaded['draws'])>350
movement=s('final-loaded-movement');loaded_inventory=s('final-loaded-inventory')
assert records['final-loaded-movement']['run']['pid']==records['final-loaded']['run']['pid']
assert movement['game_state']=='11' and int(movement['draws'])>700
assert abs(int(movement['player_z'])-int(loaded['player_z']))>4096
assert loaded_inventory['game_state']=='14' and loaded_inventory['stage7_display']=='1'
assert loaded_inventory['stage7_viewport']=='320,448' and loaded_inventory['inventory_equipped']=='160'
for r in (saved,loaded):
    assert r['game_state']=='11' and r['player_state']=='0' and r['map_idx']=='1'
    assert r['inventory_equipped']=='160' and int(r['inventory_count'])>=2 and int(r['picked_up_item_count'])>=3
def items(r):return sorted(v for k,v in r.items() if k.startswith('inventory_slot_'))
assert items(saved)==items(loaded)
for key in ('map_idx','map_room','inventory_equipped','inventory_count','picked_up_item_count','player_health'):
    assert saved[key]==loaded[key],(key,saved[key],loaded[key])
for key in ('player_x','player_z'):assert abs(int(saved[key])-int(loaded[key]))<=1024,key
assert s('final-exit')['checkpoint']=='EXIT'
assert read(ev/'final-process-exit.json')['fully_exited']
assert records['final-loaded']['run']['pid']!=records['final-save-complete']['run']['pid']
assert records['final-loaded']['run']['started']>records['final-save-complete']['run']['started']
assert records['final-save-complete']['card']['bytes']==records['final-loaded']['card']['bytes']==131072
assert records['final-save-complete']['card']['sha256']==records['final-loaded']['card']['sha256']
wide=s('final-wide-again');classic=s('final-classic')
for key in ('player_x','player_z','player_yaw','map_idx','map_room'):
    assert wide[key]==classic[key]==s('final-wide')[key],key
assert wide['stage7_viewport']=='400,240' and classic['stage7_viewport']=='320,240'
assert int(wide['linear_free'])==int(classic['linear_free'])>=4*1024*1024
for name in ('stage7-card-tests','stage7-save-arm','stage7-tmd-arm','stage7-gpu-extensions-arm'):
    assert read(p/('reports/'+name+'.json'))['status']=='PASS',name
assert read(p/'reports/stage7-tmd-arm.json')['total_models']==296
assert '15' in read(p/'reports/stage7-gpu-extensions-arm.json')['decimal_counts']
for name in ('stage7-contract-arm','stage7-pose-arm'):assert read(p/('reports/'+name+'.json'))['failure_bits']==0
assert read(p/'reports/stage7-menu-arm.json')['passed']
assert read(p/'reports/stage7-particle-arm.json')['closed_convex_contour']
index=read(p/'reports/stage7-component-index.json')
assert index['binary_sha256']==info['build_sha256'] and index['elf_sha256']==sha(p/'silenthill_game.elf')
for name,digest in index['reports'].items():assert digest==sha(p/('reports/'+name+'.json')),name
for kind in ('regular','precision','order','mask'):
    assert read(p/('reports/stage7-pixel-'+kind+'.json'))['status']=='PASS',kind
pixel_index=read(p/'reports/stage7-pixel-index.json')
assert pixel_index['card_unchanged'] and pixel_index['renderer_object_sha256']==sha(p/'build-game/render_3ds.o')
surface=(ev/'final-surface-probe.txt').read_text().splitlines()
assert len(surface)==2 and all('result=PASS' in line and 'yellow=03ff' in line for line in surface)
for file in ('final-cafe-wide.png','final-cafe-classic.png','final-inventory.png',
             'final-healthdrink.png','final-flashlight.png','final-map-pickup.png','final-save.png','final-loaded.png',
             'final-loaded-movement.png','final-loaded-inventory.png'):
    assert (ev/file).stat().st_size>1000,file
keys=('recent_frame_ms','recent_fps','recent_primitives','recent_batches','recent_primitive_ms','recent_submit_ms',
      'recent_texture_ms','command_percent','heap_used','linear_free','texture_bytes','resource_cache_bytes')
comparison={'status':'PASS','context':'Same-camera Azahar comparison; hardware performance is pending',
    'wide':{k:wide[k] for k in keys},'classic':{k:classic[k] for k in keys},
    'wide_frame_time_change_percent':round((float(wide['recent_frame_ms'])/float(classic['recent_frame_ms'])-1)*100,2),
    'screenshots':['final-cafe-wide.png','final-cafe-classic.png']}
(p/'reports/stage7-wide-comparison-final.json').write_text(json.dumps(comparison,indent=2)+'\n')
checks={k:True for k in ('normal_route','original_pickup','bottom_inventory','navigate_equip_use','original_save_ui',
    'native_exit','restart_and_original_load','restored_cafe_state','native_wide_geometry','same_camera_comparison',
    'bounded_memory','pixel_regressions','component_regressions')}
report={'status':'AZAHAR VERIFIED; HARDWARE PENDING','build':info['build_identity'],'sha256':info['build_sha256'],
    'checks':checks,'normal_run':a.run.name,'continuous_free_cafe_seconds':analysis['functional_cafe_seconds'],
    'comparison':comparison,'memory':analysis['memory_last_120_seconds'],
    'runtime_evidence':{name:{'run':r['run']['started'],'sha256':sha(ev/(name+'.json'))} for name,r in records.items()},
    'save_restoration':{'items':items(saved),'equipped':saved['inventory_equipped'],'pickups':saved['picked_up_item_count'],
        'card_sha256':records['final-save-complete']['card']['sha256'],'card_bytes':131072},
    'limitations':['Hardware validation pending','Silent audio boundary; FMV skipped',
        'Options, paper-map menu, pause and results remain outside this slice',
        'No touch, stereo, C-stick camera, 60 FPS or later-map acceptance']}
(p/'reports/stage7-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
