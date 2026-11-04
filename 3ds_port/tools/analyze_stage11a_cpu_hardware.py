"""Reproducible assessment of user-provided New 3DS school windows 019--022.

Core 2 adoption is a recorded project decision, not automatic full-stage acceptance.
All percentiles are histogram intervals; timer scopes include preemption/blocking.
"""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_stage11a_cpu import analyze
from analyze_stage11a_lifetime import read

PORT = Path(__file__).resolve().parents[1]
DEST = PORT / 'reports/stage11a-cpu-hardware-019-022'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess():
    windows = []
    for number, label, phase in ((19, 'A', 'EARLY'), (20, 'A', 'LATE'),
                                 (21, 'B', 'EARLY'), (22, 'B', 'LATE')):
        path = DEST / f'raw/cpu_audit_{number:03}.txt'
        w, row = analyze(path), read(path)
        data = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)
        manifest_path = PORT / f'build/stage11a-cpu-{label}/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        assert w['build'] == manifest['build'], 'Identify A/B by embedded build ID'
        assert w['F1'] == '1' and w['profiling']
        assert 20000 <= w['duration_ms'] <= 30000
        assert row['begin']['context'][:6] == [11, 3, 9, 1, 30, 2]
        assert row['end']['context'][:6] == [11, 3, 9, 1, 30, 2]
        expected_core = '0x4' if label == 'B' else '0x1'
        assert data['cpu_observed_spu'].split(',')[1] == expected_core
        worker_id = data['cpu_observed_spu'].split(',')[0]
        creates = [v.split(',') for k, v in data.items() if k.startswith('cpu_thread_') and k.endswith('_create')]
        worker = next(c for c in creates if c[1] == worker_id)
        assert list(map(int, worker[3:7])) == [32768, 24, 2 if label == 'B' else -2, 0]
        assert int(worker[7], 0) == 0
        for thread in ('main', 'xa', 'ndsp'):
            assert data['cpu_observed_' + thread].split(',')[1] == '0x1'
        metric = w['metrics']['spu_block']
        assert metric['valid'] and metric['calls'] > 2000
        assert metric['deadline_exceedances'] == 0 and metric['max_ms'] < 512000 / 44100
        assert list(map(int, w['audio'].split(','))) == [metric['calls'] * 512, 0, 0]
        assert list(map(int, w['queue'].split(','))) == [0, 0, 0, 0, metric['calls']]
        fast = w['pitch_trace_resolved']['fast_stats']
        assert fast['F0_blocks'] == fast['toggles'] == 0
        assert fast['F1_blocks'] == fast['blocks']
        if phase == 'LATE':
            assert fast['used_last'] >= 23 and fast['grouped_last'] == 20
            assert row['begin']['spu'][5] == row['end']['spu'][5] == 24
            events = w['pitch_trace_resolved']['events']
            assert len(events) == 21
            assert [e['voice'] for e in events] == list(range(3, 24))
            assert all(e['writer']['symbol'] == 'pitch_calc' and e['scope_caller']['symbol'] == 'readtrack2'
                       and [e['scope_kind'], e['scope_channel'], e['cc1'], e['cc2']] == [1, 0, 1, 0]
                       and [e['old_pitch'], e['new_pitch'], e['env_level'], e['ever_keyed']] == [0, 4096, 0, 0]
                       for e in events)
        w.update(label=label, phase=phase, session=row['session'], frames=row['frames'],
                 uptime_ms=[row['begin']['uptime_ms'], row['end']['uptime_ms']],
                 context_begin=row['begin']['context'], context_end=row['end']['context'],
                 context_changed_mask=hex(row['pose_changed']),
                 main_lock_ms_per_lcd_frame=w['metrics']['main_lock']['mean_ms'] * w['metrics']['main_lock']['calls'] / row['frames'],
                 cache_per_frame=row['cache_per_frame'],
                 memory_begin=row['begin']['memory'], memory_end=row['end']['memory'],
                 allocation_changes={k: [v, row['end']['allocator'][k]] for k, v in row['begin']['allocator'].items()
                                     if v != row['end']['allocator'][k]},
                 observer_total_probe_ms=float(data['lifetime_probe_total_ms']),
                 history_used=int(data['lifetime_history_used']), history_capacity=int(data['lifetime_history_capacity']),
                 pitch_trace_used=int(data['pitch_trace_used']), pitch_trace_capacity=int(data['pitch_trace_capacity']))
        w['file'] = path.relative_to(PORT.parent).as_posix()
        windows.append(w)
    ae, al, be, bl = windows
    assert ae['session'] == al['session'] and be['session'] == bl['session'] and ae['session'] != be['session']
    assert be['context_begin'] == bl['context_begin'] == bl['context_end']
    assert al['memory_begin'] == al['memory_end'] == be['memory_begin'] == be['memory_end'] == bl['memory_begin'] == bl['memory_end']
    assert not al['allocation_changes'] and not be['allocation_changes'] and not bl['allocation_changes']
    for key in ('cache_entries', 'cache_pinned', 'cache_dirty', 'renderer_textures', 'pending_draws',
                'pending_primitives', 'pending_vertices', 'threads', 'spu_resets'):
        assert len({w['memory_and_state'][key] for w in windows}) == 1
    return dict(status='CORE2_SCHOOL_HARDWARE_PASS_FREEZE_CANDIDATE',
        source='User explicitly identified all four windows as real New Nintendo 3DS captures.',
        filename_label_correction='User text labels 21/22 A; embedded build IDs unambiguously identify B.',
        block_budget_ms=512000 / 44100, windows=windows,
        late_main_work_reduction_percent=100 * (1 - bl['metrics']['work']['mean_ms'] / al['metrics']['work']['mean_ms']),
        late_spu_block_reduction_percent=100 * (1 - bl['metrics']['spu_block']['mean_ms'] / al['metrics']['spu_block']['mean_ms']),
        writer_confirmed_on_hardware=True,
        writer_path='readtrack2 -> chanmessage -> control_change(channel=0, CC1=1, value=0) -> pitch_calc -> SpuSetVoiceAttr',
        disassembly_evidence='Exact B ELF: 0x1c7cac BL SpuSetVoiceAttr (return PC 0x1c7cb0); 0x1cb4a8 BL chanmessage (return PC 0x1cb4ac).',
        core2_adopted=True, stage11a_accepted=False,
        limitations=[
            'School is capped at 30 FPS; A/B player/camera poses differ slightly. A early has a small pose change/cache warm-up. CPU differences are these windows, not a universal speedup.',
            'B main-lock wait is higher (mean 25--34 us, max 1.324 ms). B block p99/max are slightly higher than A, within 11.61 ms budget; no audio health failure.',
            'Deadline counter measures block compute-budget exceedances, not an independently observed NDSP playback deadline. Zero starves/drops are separate evidence.',
            'Percentiles are half-open histogram intervals. Timing includes blocking and preemption; no scheduled CPU utilization claim.',
            'Fast-path counters and pitch events are lifetime snapshots; performance and queue histograms describe completed observations around the window boundaries.',
            'XA is inactive in these school windows. User SFX/music/XA listening result is positive but qualitative.',
            'No current B Title -> New Game or suspend/resume recorder sequence supplied. Largest allocatable heap/linear block is unavailable.',
            'Bounded diagnostic storage and low probe/report cost are consistent with stable baseline; these P1-only windows do not measure exact P0/P1 overhead.'
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-from', dest='origin', type=Path)
    args = parser.parse_args()
    DEST.mkdir(exist_ok=True)
    if args.origin:
        (DEST / 'raw').mkdir(exist_ok=True)
        for n in (19, 20, 21, 22):
            source = args.origin / f'cpu_audit_{n:03}.txt'
            target = DEST / 'raw' / source.name
            if target.exists():
                assert target.read_bytes() == source.read_bytes(), 'Do not overwrite received evidence'
            else:
                target.write_bytes(source.read_bytes())
    result = assess()
    target = DEST / 'assessment.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], windows=len(result['windows']),
                         core2_adopted=result['core2_adopted'], stage11a_accepted=False)))
