"""Compare qualified actual PICA runs; emulator timings are not hardware FPS."""
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]
def read(name):
    folder=p/'reports'/('stage10-r6-'+name+'-pica')
    q=json.loads((folder/'qualification.json').read_text(encoding='utf-8-sig'))
    s=dict(line.split('=',1) for line in (folder/'status.txt').read_text().splitlines() if '=' in line)
    assert q['status']=='PASS' and s['report_complete']=='1' and s['first_failure']=='0'
    assert s['r6_benchmark_age']=='450' and int(s['readback_direct_mismatches'])==0 and int(s['gpu_duplicate_presents'])==0
    result=dict(name=name,diagnostic=q['diagnostic'],pose=s['r6_benchmark_pose'],
        work_ms=float(s['profile_work_ms']),wall_ms=float(s['profile_wall_ms']),
        logical_wall_fps=1000/float(s['profile_wall_ms']),
        work_only_fps=1000/float(s['profile_work_ms']),legacy_or_current_hud_fps=float(s['recent_fps']),
        fps_scope=s.get('fps_scope','LEGACY_NATIVE_SUBMISSIONS'),
        camera=s.get('r6_benchmark_camera'),
        readback_calls=int(s['r6_readback_calls']),
        readback_gpu_ms_per_call=int(s['r6_readback_total_ticks'])/268123.48/max(1,int(s['r6_readback_calls'])),
        categories={k:float(v) for k,v in s.items() if k.startswith('profile_') and (k.endswith('_ms') or k.endswith('_per_frame')) and ',' not in v},
        scene_rows=[v for k,v in s.items() if k.startswith('profile_scene_')],
        enemy_frames=int(s.get('r6_enemy_frames',0)),enemy_peak=int(s.get('r6_enemy_peak',0)))
    if name.startswith('combat-'):
        active=[list(map(float,v.split(','))) for v in result['scene_rows'] if int(v.split(',')[3])>0]
        assert active and result['enemy_frames']>0,'No actual active enemy; reject fixture'
        frames=sum(v[4] for v in active)
        result['active_scene_frames']=int(frames)
        result['active_scene_wall_ms']=sum(v[4]*v[5] for v in active)/frames
        result['active_scene_work_ms']=sum(v[4]*v[6] for v in active)/frames
        result['active_scene_fps']=1000/result['active_scene_wall_ms']
    if name.startswith('final-') or name.startswith('indoor-') or name.startswith('combat-'):
        assert result['fps_scope']=='LOGICAL_LCD_PRESENTATIONS'
        # Combat/death can straddle the differently aligned 120-frame windows.
        if not name.startswith('combat-'):
            assert abs(result['legacy_or_current_hud_fps']/result['logical_wall_fps']-1)<.08,'HUD counts parts instead of LCD frames'
    return result
names=['baseline-town-off','baseline-town-on','final-town-off','final-town-on','indoor-off','indoor-on']
names += [n for n in ('combat-air-before','combat-air-after','combat-groaner-before','combat-groaner-after')
          if (p/'reports'/('stage10-r6-'+n+'-pica/qualification.json')).exists()]
runs={n:read(n) for n in names}
assert len({runs[n]['pose'] for n in names[:4]})==1
assert len({runs[n]['camera'] for n in names[:4]})==1
assert all(runs[n]['camera'].split(',')[:3]==runs[n]['camera'].split(',')[3:] for n in names[:4]),'Camera must stay fixed throughout measurement'
assert runs['indoor-on']['pose']==runs['indoor-off']['pose']
for kind in ('air','groaner'):
    pair=[runs.get('combat-'+kind+'-'+part) for part in ('before','after')]
    if all(pair):
        assert pair[0]['pose']==pair[1]['pose']
        assert 'SH_STAGE10_RENDERER_REFERENCE_R5' in pair[0]['diagnostic']['flags']
assert all('SH_STAGE10_RENDERER_REFERENCE_R5' in runs[n]['diagnostic']['flags'] for n in names[:2])
before=runs['baseline-town-on'];after=runs['final-town-on']
assert after['work_ms']<before['work_ms']*.5
assert runs['final-town-off']['work_ms']<runs['baseline-town-off']['work_ms']*1.05
report=dict(status='PASS',scope=__doc__,runs=runs,
    flashlight_work_speedup=before['work_ms']/after['work_ms'],
    flashlight_work_reduction_percent=100*(1-after['work_ms']/before['work_ms']),
    hardware_observation_r5=dict(off_fps=25,on_fps=11,town_typical_fps=26),
    hardware_r6_fps=None,
    warnings=['Inclusive profiler categories must not be added together.',
        'Use logical wall FPS, not legacy R5 HUD FPS, when readback splits a frame.',
        'No claim of New 3DS FPS or guaranteed 60 FPS.'],hardware_accepted=False)
(p/'reports/stage10-r6-performance.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='runs'},indent=2))
for n,r in runs.items():print(n,'work',r['work_ms'],'wall',r['wall_ms'],'LCD FPS',round(r['logical_wall_fps'],3),'enemy',r['enemy_frames'])
