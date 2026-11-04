#!/usr/bin/env python3
"""Compare fixed-position, same-animation windows without cumulative averages."""
from pathlib import Path
import json

port = Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
keys = ('recent_frame_ms', 'recent_primitive_ms', 'recent_texture_ms',
        'recent_submit_ms', 'recent_wait_ms', 'recent_begin_wait_ms',
        'recent_cache_comparisons', 'recent_primitives', 'recent_sim_speed',
        'recent_uploads', 'recent_evictions', 'linear_free', 'heap_used')
results = {}
for label, run_name in (('before', '20261024-161817-566'), ('after', '20261024-164401-822')):
    run = port / 'build/azahar/runs' / run_name
    samples = read(run / f'stationary-{label}-samples.json')
    selected = [s for s in samples if s['status']['anim_state'] == '2']
    early = [s['status'] for s in selected if 20 <= s['control_elapsed'] <= 60]
    late = [s['status'] for s in selected if 240 <= s['control_elapsed'] <= 300]
    assert len(early) >= 5 and len(late) >= 5
    positions = sorted({(s['status']['player_x'], s['status']['player_z'], s['status']['player_yaw'])
                        for s in selected})
    assert len(positions) == 1
    result = {'run': run_name, 'identity': read(run / f'stationary-{label}-result.json')['build'],
              'early_samples': len(early), 'late_samples': len(late),
              'anim_state': 2, 'same_position': positions,
              'early': {k: sum(float(s[k]) for s in early) / len(early) for k in keys},
              'late': {k: sum(float(s[k]) for s in late) / len(late) for k in keys}}
    (port / f'reports/stage5-stationary-{label}.json').write_text(json.dumps(result, indent=2)+'\n')
    results[label] = result
assert results['before']['same_position'] == results['after']['same_position']
summary = {'context': 'Azahar only; real hardware progressive-cost report remains open',
           'measurement': 'Same fixed position/yaw and rest animation; 20-60s versus 240-300s',
           'results': results}
(port / 'reports/stage5-stationary-comparison.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary, indent=2))
