#!/usr/bin/env python3
"""Descriptive cost/work correlations; changing camera/scene is not controlled."""
from pathlib import Path
import json
import math

port = Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
info = read(port/'build/azahar/last-run.json')
run = port/'build/azahar/runs'/info['launched'].replace('\\','/').split('/')[-2]
samples = read(run/'stage5-samples.json')
data = [dict(s['status'], elapsed=s['elapsed']) for s in samples
        if int(s['status']['map_frames']) > 700 and s['status']['player_state'] == '0'
        and int(s['status']['recent_samples']) == 120]
assert len(data) > 20
def mean(rows, key): return sum(float(s[key]) for s in rows)/len(rows)
def correlation(key):
    xs = [float(s[key]) for s in data]; ys = [float(s['recent_frame_ms']) for s in data]
    mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
    denom = math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denom if denom else None
keys = ('recent_frame_ms','recent_primitive_ms','recent_texture_ms','recent_submit_ms',
        'recent_wait_ms','recent_begin_wait_ms','recent_cache_comparisons',
        'recent_primitives','recent_batches','recent_uploads','recent_evictions','recent_sim_speed')
groups = {}
for label, rows in (('early_60_to_180s',[s for s in data if 60<=s['elapsed']<=180]),
                    ('late_last_120s',[s for s in data if s['elapsed']>=samples[-1]['elapsed']-120]),
                    ('no_uploads',[s for s in data if float(s['recent_uploads'])==0]),
                    ('uploads',[s for s in data if float(s['recent_uploads'])>0])):
    if rows: groups[label] = {'samples':len(rows), 'means':{k:mean(rows,k) for k in keys}}
result = {'build':info['build_identity'], 'run':run.name, 'sample_count':len(data),
          'scope':'Moving scenes/cameras: descriptive only; not proof of same-scene time growth',
          'cost_correlations':{k:correlation(k) for k in ('elapsed','recent_primitives','recent_batches',
                  'recent_cache_comparisons','recent_uploads','recent_evictions')},
          'groups':groups,
          'memory_ranges':{k:[min(int(s[k]) for s in data),max(int(s[k]) for s in data)]
                           for k in ('heap_used','linear_free','cache_active')},
          'notes':['Stationary comparison is the controlled runtime-cost experiment',
                   'Lifetime counters can rise while per-window work remains bounded',
                   'Correlation is not causation; renderer submission includes synchronous CPU work']}
(port/'reports/stage5-followup-moving-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
