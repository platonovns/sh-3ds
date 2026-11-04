#!/usr/bin/env python3
"""Analyze bounded runtime evidence, keeping visual/hardware acceptance separate."""
import argparse, json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--label',default='stage6-normal')
p.add_argument('--motion-run',type=Path,help='Separate physical Cafe motion evidence from the identical binary')
p.add_argument('--route-prefix',type=Path,help='Earlier continuous route samples from the identical binary')
p.add_argument('--require-normal',action='store_true');a=p.parse_args()
read=lambda name:json.loads((a.run/name).read_text(encoding='utf-8-sig'))
info=read('run.json');result=read(a.label+'-result.json');samples=read(a.label+'-samples.json')
assert result['result']=='CAFE_LOG_CAPTURE_COMPLETE_VISUAL_REVIEW_REQUIRED',result['error']
assert len(samples)>=8
states={};media={}
route_samples=samples
if a.route_prefix:
    route_samples=json.loads(a.route_prefix.read_text(encoding='utf-8-sig'))+samples
for sample in route_samples:
    s=sample['status'];assert s['build']==info['build_identity'] and s['first_failure']=='0' and s['report_complete']=='1'
    assert int(s['cache_active'])<=96 and int(s['texture_bytes'])<=96*262144 and float(s['command_percent'])<100
    for key,value in s.items():
        if key.startswith('state_'):states[key]=[int(x) for x in value.split(',')]
        if key.startswith('skipped_media_') and key.rsplit('_',1)[-1].isdigit():
            row=[int(x) for x in value.split(',')];media[tuple(row[:3])]=row[3]
last=samples[-1]['status'];end=samples[-1]['elapsed']
free=[x for x in samples if x['elapsed'] >= (result.get('cafe_start_elapsed') or 0)
      and x['status'].get('map_idx')=='1' and x['status'].get('game_state')=='11' and x['status'].get('player_state')=='0'
      and x['status'].get('control_disabled')=='0' and int(x['status']['player_health'])>0]
assert free and result['elapsed']-free[0]['elapsed']>=result['seconds']-4
if a.require_normal:
    assert result['elapsed']-end<=20, 'Capture ended without fresh runtime evidence'
    assert result.get('cafe_scene_finished'), 'Original Cafe scene completion was not recorded'
late=[x['status'] for x in free if x['elapsed']>=end-120]
if not a.require_normal and len(late)<5:late=[x['status'] for x in free]
assert len(late)>=(5 if a.require_normal else 2)
memory={k:{'min':min(int(x[k]) for x in late),'max':max(int(x[k]) for x in late)} for k in
        ('heap_used','linear_free','resource_cache_bytes','texture_bytes')}
assert memory['heap_used']['max']-memory['heap_used']['min']<=4096,memory
assert all(memory[k]['min']==memory[k]['max'] for k in ('linear_free','resource_cache_bytes','texture_bytes')),memory
assert memory['linear_free']['min']>=4*1024*1024,memory
motion_delta=int(free[-1]['status']['control_changes'])-int(free[0]['status']['control_changes'])
motion={'run':a.run.name,'source':'extended capture','control_changes':motion_delta}
if motion_delta<20 and a.motion_run:
    other=lambda name:json.loads((a.motion_run/name).read_text(encoding='utf-8-sig'))
    mi=other('run.json');mr=other(a.label+'-result.json');ms=other(a.label+'-samples.json')
    assert mi['build_sha256']==info['build_sha256'] and mi['build_identity']==info['build_identity']
    assert not mi['gdb_stub'] and not mi['diagnostic_gameplay'] and not mi['diagnostic_stationary']
    assert mr['cafe_scene_finished'] and mr['last']['first_failure']=='443'
    assert mr['last']['operation']=='pickup TMD presentation unavailable'
    mf=[x for x in ms if x['elapsed'] >= mr['cafe_start_elapsed'] and
        x['status']['map_idx']=='1' and x['status']['player_state']=='0' and
        x['status']['control_disabled']=='0' and x['status']['first_failure']=='0']
    assert len(mf)>=3 and all(x['status']['boot_variant']=='NORMAL_NEW_GAME' and
        x['status']['stage6_pad_route']=='0' and x['status']['build']==info['build_identity'] for x in mf)
    motion_delta=int(mf[-1]['status']['control_changes'])-int(mf[0]['status']['control_changes'])
    assert (mf[-1]['status']['player_x'],mf[-1]['status']['player_z']) != \
           (mf[0]['status']['player_x'],mf[0]['status']['player_z'])
    motion={'run':a.motion_run.name,'source':'separate physical motion capture, identical binary',
            'control_changes':motion_delta,'seconds':round(mf[-1]['elapsed']-mf[0]['elapsed'],2),
            'later_stop':mr['error']}
assert motion_delta>=20,motion
rows=sorted(states.values(),key=lambda x:x[0])
route={'title':any(r[3]==7 for r in rows),'first_map':any(r[1]==0 and r[3]==11 for r in rows),
       'room_transition':any(r[1]==0 and r[5]==6 for r in rows),
       'overlay_transition':any(r[1]==0 and r[5]==5 for r in rows),
       'cafe_fmv':any(r[1]==1 and r[5]==4 for r in rows),
       'cafe_script':any(r[1]==1 and r[5]==10 and r[8]==3 for r in rows),
       'functional_cafe':last['map_idx']=='1' and last['player_state']=='0' and last['control_disabled']=='0'}
if a.require_normal:
    assert last['boot_variant']=='NORMAL_NEW_GAME',last['boot_variant']
    assert all(route.values()),route
report={'status':'AZAHAR LOG PASS; VISUAL REVIEW AND REAL HARDWARE VALIDATION REQUIRED',
    'build':info['build_identity'],'sha256':info['build_sha256'],'variant':last['boot_variant'],
    'samples':len(samples),'late_samples':len(late),'movement_evidence':motion,
    'functional_cafe_seconds':round(result['elapsed']-free[0]['elapsed'],2),
    'route':route,'memory_last_120_seconds':memory,'cache_peak':int(last['cache_peak']),
    'max_pinned_textures':int(last['cache_peak_pinned']),'max_primitives':int(last['max_draws']),
    'max_command_percent':max(float(x['status']['command_percent']) for x in samples),
    'late_simulation_speed_min':min(float(x['recent_sim_speed']) for x in late),
    'late_simulation_speed_max':max(float(x['recent_sim_speed']) for x in late),
    'skipped_media':[list(k)+[v] for k,v in sorted(media.items())],
    'state_history':rows,'last':last}
out=a.run/(a.label+'-analysis.json');out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('state_history','last','skipped_media')},indent=2))
