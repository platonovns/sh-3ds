"""Derive the six hardware windows supplied on 2026-10-28. No game changes."""
import hashlib
import json
from pathlib import Path
from analyze_stage11a_lifetime import read, compare, state

PORT = Path(__file__).resolve().parents[1]
CASE = PORT / 'reports/stage11a-lifetime-hardware-20261028'
LABELS = ('EARLY', 'DEGRADED', 'WARM_NEW_GAME', 'COLD_RESTART',
          'DEGRADED_P0_FLASH_ON', 'DEGRADED_P1_FLASH_OFF')


def fields(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)


def metric(data, name, duration, enabled):
    valid, calls, total, maximum, exceeded = data['stage11a_metric_' + name].split(',')
    calls, total = int(calls), float(total)
    # In P0 the inherited valid flag is 1 but no measurements are collected.
    measured = bool(enabled and int(valid) and calls)
    return dict(measured=measured, calls=calls, total_ms=total if measured else None,
                mean_ms=total / calls if measured else None,
                max_ms=float(maximum) if measured else None,
                elapsed_fraction_of_wall=total / duration if measured else None,
                note='Elapsed includes preemption/blocking; not scheduled CPU ticks')


def main():
    rows, summaries = [], []
    timeline = {}
    inventory = []
    for number, label in enumerate(LABELS, 11):
        path = CASE / 'raw' / f'cpu_audit_{number:03}.txt'
        row, data = read(path), fields(path)
        row['label'] = label
        rows.append(row)
        inventory.append(dict(file=path.name, bytes=path.stat().st_size, sha256=row['sha256'],
                              user_label=label, source='C:/Users/sombo/Downloads/' + path.name))
        begin, end = row['begin'], row['end']
        delta = lambda group, index: (end[group][index] - begin[group][index]) & 0xffffffff
        alloc = {api: [(x - y) & 0xffffffff for x, y in zip(end['allocator'][api], counters)]
                 for api, counters in begin['allocator'].items() if end['allocator'][api] != counters}
        metrics = {name: metric(data, name, row['duration_ms'], row['profiling_enabled'])
                   for name in ('spu_block', 'spu_render', 'main_lock', 'spu_lock', 'dsp_flush', 'ndsp_submit')}
        summaries.append(dict(number=number, label=label, build=row['build'], session=row['session'],
            fps=row['fps'], frames=row['frames'], duration_ms=row['duration_ms'],
            mode=begin['mode'], context_begin=begin['context'], context_end=end['context'],
            context_changed_mask=row['pose_changed'], begin=state(dict(row, end=begin)), end=state(row),
            metrics=metrics, cache_per_frame=row['cache_per_frame'],
            invalidation_calls_per_frame=delta('cache', 0) / row['frames'],
            image_dirty_marks_per_frame=delta('cache', 1) / row['frames'],
            clut_dirty_marks_per_frame=delta('cache', 2) / row['frames'],
            vram_generations_per_frame=delta('render', 15) / row['frames'],
            feedback_generations_per_frame=delta('render', 16) / row['frames'],
            allocation_api_deltas=alloc, memory_begin=begin['memory'], memory_end=end['memory'],
            resource_begin=begin['resource'], resource_end=end['resource'],
            queue_starves_delta=delta('audio', 1), drops_delta=delta('audio', 2),
            process_threads=end['threads'], observed_core_masks={k:v for k,v in data.items() if k.startswith('cpu_observed_')},
            category_elapsed_ms=row['frame_cost_ms'] if row['profiling_enabled'] else None,
            primitives_per_frame=int(data['sample_profile_primitives'])/row['frames'] if row['profiling_enabled'] else None,
            profile_table_used=end['profile'][43:46],
            observer_boundary_ms=[begin['probe_ms'], end['probe_ms']]))
        for snap in (row['first'], *row['history'], begin, end):
            key = (row['session'], snap['serial'])
            if key in timeline:
                assert timeline[key]['snapshot'] == snap, key
            else:
                timeline[key] = dict(session=row['session'], snapshot=snap)
    four = compare(rows[:4])
    assert all(r['build'] == rows[0]['build'] for r in rows)
    assert rows[4]['session'] == rows[5]['session'] == rows[3]['session']
    assert rows[0]['begin']['context'] == rows[1]['begin']['context']
    assert rows[0]['pose_changed'] == rows[1]['pose_changed'] == 0
    assert [r['begin']['mode'] for r in rows] == [1,1,1,1,0,1]
    assert rows[4]['begin']['context'][3] == 1 and rows[5]['begin']['context'][3] == 0
    a, b, w, c = summaries[:4]
    warm_cache_extra = w['end']['cache_entries'] - c['end']['cache_entries']
    warm_linear_extra = c['end']['linear_free'] - w['end']['linear_free']
    assert warm_linear_extra == warm_cache_extra * 262144
    assert a['memory_end'] == b['memory_begin'] == b['memory_end']
    assert not b['allocation_api_deltas']
    assert a['resource_end'] == b['resource_end']
    assert all(not s['queue_starves_delta'] and not s['drops_delta'] for s in summaries)
    result = dict(status='HARDWARE_GROWING_SPU_WORK_IDENTIFIED_BASELINE_UNSTABLE',
        measurement_source='REAL_NEW_3DS_USER_RECORDINGS', windows=summaries,
        matched_early_degraded=True, warm_cold_pose_matched=False, p0_p1_flashlight_pair_matched=False,
        four_window_comparison=four,
        warm_cold_texture_memory_accounting=dict(extra_slots=warm_cache_extra, bytes_per_slot=262144,
                                                observed_extra_linear_bytes=warm_linear_extra,
                                                extra_heap_bytes=w['end']['heap_used']-c['end']['heap_used']),
        growing_cost_owner='NATIVE_SPU_RENDER',
        growth_mechanism='Unkeyed silent voices receive nonzero pitch and leave the existing frozen fast path',
        hardware_pitch_write_caller_confirmed=False,
        title_resets_spu=False, process_restart_recovers_fps_and_frozen_voice_population=True,
        true_memory_leak_proven=False, fragmentation_evidence_in_matched_school_pair=False,
        coarse_diagnostics_disable_does_not_restore_fps=True, all_diagnostics_exonerated=False,
        source_write_candidate='control_change CC1 -> pitch_calc -> SpuSetVoiceAttr',
        frozen_r6_synthetic_cc_reproduction='pitch-writer-arm.json',
        full_route_reproduced_on_frozen_r6_hardware=False,
        optimization_or_gameplay_fix_applied=False, normal_control='ON_HOLD', core2='NOT_STARTED',
        warnings=four['warnings'] + [
            'Window 15/16 differ in flashlight, pose, time, cache occupancy and an intervening room trip.',
            'Window 13 averages 27.0863 FPS; the earlier reported 16 FPS phase is outside that recording.',
            'Elapsed SPU share is not a scheduled CPU utilization measurement.',
            'Synthetic CC reproduction identifies a possible writer, not the hardware event that triggered it.'])
    (CASE / 'case-analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    ordered = sorted(timeline.values(), key=lambda item:(item['session'], item['snapshot']['uptime_ms']))
    (CASE / 'timeline.json').write_text(json.dumps(ordered, indent=2) + '\n')
    (CASE / 'raw-inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps(dict(status=result['status'], windows=[dict(number=s['number'], fps=s['fps'],
          spu_block_ms=s['metrics']['spu_block']['mean_ms'], silent=s['end']['silent_nonzero_pitch_voices']) for s in summaries],
          warm_cold_texture_memory_accounting=result['warm_cold_texture_memory_accounting']), indent=2))


if __name__ == '__main__':
    main()
