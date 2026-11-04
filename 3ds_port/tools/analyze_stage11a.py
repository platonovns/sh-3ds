"""Validate recording windows and compare explicitly paired hardware trials.

Quantiles are histogram bounds, never invented exact samples. Dynamic scenes
need an operator-defined event/route; full simulation equivalence is not proven
by a save hash or a camera pose. Raw logs are never rewritten.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def quantile(hist, fraction):
    width, *counts = hist
    rank = max(1, math.ceil(sum(counts) * fraction))
    acc = 0
    for index, count in enumerate(counts):
        acc += count
        if acc >= rank:
            return dict(lower_ms=index * width / 1000,
                        upper_ms=(index + 1) * width / 1000 if index < 255 else None)
    return None


def window(path, expected_sha):
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha, f'Hash mismatch: {path}'
    data = {}
    for line in raw.decode('utf-8-sig').splitlines():
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        if key in data and (key.startswith(('sample_', 'stage11a_')) or key == 'build'):
            raise ValueError(f'Duplicate key: {key}')
        data[key] = value
    assert all(data[k] == '1' for k in ('sample_complete', 'report_complete', 'stage11a_schema'))
    assert data['build'].startswith('stage11a.')
    frames = int(data['sample_profile_frames'])
    assert frames > 0 and frames == int(data['sample_lcd_frames'])
    metrics = {}
    for key, val in data.items():
        if not key.startswith('stage11a_metric_') or key == 'stage11a_metric_schema':
            continue
        name = key.removeprefix('stage11a_metric_')
        fields = val.split(',')
        assert len(fields) == 5
        valid, calls, total, maximum, misses = map(float, fields)
        assert valid in (0, 1) and calls == int(calls) and calls >= 0
        assert all(math.isfinite(x) and x >= 0 for x in (total, maximum, misses))
        assert maximum <= total + 0.000002
        row = dict(valid=bool(valid), calls=int(calls), total_ms=total,
                   max_ms=maximum, mean_ms=total / calls if calls else None,
                   block_budget_exceedances=int(misses))
        if 'stage11a_hist_' + name in data:
            hist = list(map(int, data['stage11a_hist_' + name].split(',')))
            assert len(hist) == 257 and hist[0] > 0 and min(hist[1:]) >= 0
            assert sum(hist[1:]) == calls, f'Incoherent histogram: {name}'
            row.update({f'p{q}_bounds_ms': quantile(hist, q / 100) if calls else None for q in (50, 95, 99)})
        metrics[name] = row
    for name in ('wall', 'work'):
        assert metrics[name]['valid'] and metrics[name]['calls'] == frames
        assert abs(metrics[name]['total_ms'] - float(data['sample_profile_' + name + '_ms'])) < 0.001
    assert metrics['spu_block']['valid'] and metrics['spu_render']['valid']
    assert metrics['spu_block']['calls'] > 0 and metrics['spu_render']['calls'] > 0, 'No real SPU blocks captured'
    profiles = {key.removeprefix('sample_profile_'): float(value)
                for key, value in data.items() if key.startswith('sample_profile_') and
                key.endswith(('_total_ms', '_mean_ms', '_peak_ms'))}
    health = list(map(int, data['stage11a_audio_window'].split(',')))
    assert len(health) == 3
    return dict(file=str(path), sha256=expected_sha, build=data['build'],
                detail=int(data['stage11a_spu_detail']), frames=frames,
                fps=float(data['sample_lcd_fps']), duration_ms=float(data['sample_duration_ms']),
                context_start=data['sample_start_context'], context_end=data['sample_end_context'],
                changed=int(data['sample_context_changed_mask'], 0), metrics=metrics,
                profile_inclusive_overlapping=profiles,
                counts={key: int(data['sample_profile_' + key]) for key in ('draws', 'primitives', 'decodes', 'uploads', 'upload_bytes')},
                resolve=data['sample_cpu_resolve'],
                queue_depth=list(map(int, data['stage11a_queue_depth_after_submit'].split(','))),
                queue_valid=data['stage11a_queue_valid'] == '1',
                audio_window=dict(rendered_frames=health[0], queue_starves=health[1], dropped_frames=health[2]),
                audio_no_starves_or_drops=health[1:] == [0, 0],
                cache_window=data.get('stage11a_cache_window'),
                memory_start=data.get('stage11a_memory_start'), memory_end=data.get('stage11a_memory_end'),
                runtime_inventory={key: val for key, val in data.items() if key.startswith(('cpu_thread_', 'cpu_observed_', 'cpu_core_', 'cpu_hardware_', 'cpu_clock_', 'cpu_luma_'))},
                simulation_state_equivalence_proven=False,
                scheduled_cpu_time_available=False)


def session(path):
    data = read_json(path)
    assert data['measurement'] == 'REAL_NEW_3DS', 'Do not mix emulator and hardware evidence'
    assert data['hardware'] and data['trials']
    trials = []
    keys = set()
    for trial in data['trials']:
        assert trial['scene'] in 'ABCDE' and len(trial['scene']) == 1
        assert trial['state_id'] and len(trial['save_sha256']) == 64 and trial['repeat'] >= 1
        assert trial['fps_mode'] in (30, 60) and trial['kind'] in ('stationary', 'scripted')
        key = (trial['scene'], trial['fps_mode'], trial['repeat'])
        assert key not in keys, f'Duplicate trial {key}'
        keys.add(key)
        row = window(path.parent / trial['file'], trial['sha256'])
        assert int(row['context_start'].split(',')[4]) == trial['fps_mode']
        assert row['build'] == data['build']
        context = row['context_start'].split(',')
        if trial['scene'] in ('A', 'B'):
            assert trial['kind'] == 'stationary'
            assert context[3] == ('OFF' if trial['scene'] == 'A' else 'ON')
        if trial['kind'] == 'scripted':
            assert trial['event_or_route'] and not (row['changed'] & 31), 'Configuration/map changed inside route'
        row['trial'] = trial
        row['static_context_stable'] = row['changed'] == 0
        row['pair_quality'] = 'STATIC_OBSERVABLE_CONTEXT' if trial['kind'] == 'stationary' else 'OPERATOR_DEFINED_ROUTE_OR_EVENT'
        trials.append(row)
    return dict(build=data['build'], hardware=data['hardware'], trials=trials,
                scene_coverage=sorted(set(t['trial']['scene'] for t in trials)),
                full_acceptance=False)


def compare(before, after):
    assert before['hardware'] == after['hardware'], 'Different hardware configuration'
    key = lambda r: (r['trial']['scene'], r['trial']['fps_mode'], r['trial']['repeat'])
    a, b = {key(r): r for r in before['trials']}, {key(r): r for r in after['trials']}
    assert a.keys() == b.keys(), 'Missing paired trials'
    pairs = []
    for k in sorted(a):
        x, y = a[k], b[k]
        for field in ('state_id', 'save_sha256', 'kind'):
            assert x['trial'][field] == y['trial'][field], f'Unmatched {field}: {k}'
        assert x['detail'] == y['detail'], 'Different instrumentation modes'
        if x['trial']['kind'] == 'stationary':
            assert x['static_context_stable'] and y['static_context_stable'], f'Unstable pose/camera: {k}'
            assert x['context_start'] == y['context_start'], f'Unmatched pose/camera: {k}'
        else:
            assert x['trial']['event_or_route'] == y['trial']['event_or_route']
        delta = y['metrics']['work']['mean_ms'] - x['metrics']['work']['mean_ms']
        pairs.append(dict(scene=k[0], fps_mode=k[1], repeat=k[2], before=x, after=y,
                          mean_work_delta_ms=delta, fps_delta=y['fps'] - x['fps'],
                          retained=False, hardware_visual_audio_regression_review_required=True))
    return dict(pairs=pairs, note='Paired observed measurements; no subtraction of overlapping scopes. Full simulation equality and listening require separate evidence.',
                hardware_accepted=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples', type=Path)
    parser.add_argument('--after', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = session(args.samples)
    if args.after:
        result = compare(result, session(args.after))
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: recording hashes, completion, distributions and pairing validated; ' + str(args.output))
