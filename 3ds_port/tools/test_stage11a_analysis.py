"""Synthetic regression inputs for report arithmetic and A/B eligibility only."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from analyze_stage11a import window, session, compare, quantile

PORT = Path(__file__).resolve().parents[1]


def rejects(fn):
    try:
        fn()
    except (AssertionError, ValueError):
        return
    raise AssertionError('Invalid comparison was accepted')


def main():
    hist = lambda width, count: ','.join(map(str, [width, count, *([0] * 255)]))
    data = dict(sample_complete='1', report_complete='1', stage11a_schema='1', build='stage11a.test',
                sample_profile_frames='10', sample_lcd_frames='10', sample_profile_wall_ms='5.000000',
                sample_profile_work_ms='4.000000', sample_lcd_fps='20', sample_duration_ms='500',
                sample_start_context='11,3,23,OFF,30,2,1,2,3,4,5,6,7,8,9',
                sample_end_context='11,3,23,OFF,30,2,1,2,3,4,5,6,7,8,9',
                sample_context_changed_mask='0x0', sample_cpu_resolve='1,0,0,0',
                stage11a_spu_detail='0', stage11a_audio_window='512,0,0',
                stage11a_queue_valid='1', stage11a_queue_depth_after_submit='0,0,0,0,1',
                stage11a_metric_wall='1,10,5,0.5,0', stage11a_metric_work='1,10,4,0.4,0',
                stage11a_metric_spu_block='1,1,0.05,0.05,0', stage11a_metric_spu_render='1,1,0.04,0.04,0',
                stage11a_hist_wall=hist(1000, 10), stage11a_hist_work=hist(1000, 10),
                stage11a_hist_spu_block=hist(100, 1), stage11a_hist_spu_render=hist(100, 1))
    data.update({'sample_profile_' + name: '0' for name in ('draws', 'primitives', 'decodes', 'uploads', 'upload_bytes')})
    with tempfile.TemporaryDirectory(prefix='stage11a-analysis-', dir=PORT / 'build') as directory:
        d = Path(directory)
        assert d.resolve().parent == (PORT / 'build').resolve()

        def write(values):
            raw = ''.join(f'{k}={v}\n' for k, v in values.items()).encode()
            (d / 'synthetic.txt').write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()

        digest = write(data)
        parsed = window(d / 'synthetic.txt', digest)
        assert parsed['metrics']['wall']['p99_bounds_ms'] == dict(lower_ms=0, upper_ms=1)
        assert not parsed['simulation_state_equivalence_proven']
        rejects(lambda: window(d / 'synthetic.txt', '0' * 64))
        for field, val in [('sample_complete', '0'), ('sample_lcd_frames', '11'),
                           ('stage11a_hist_wall', hist(1000, 9)), ('stage11a_metric_spu_block', '1,0,0,0,0')]:
            bad = {**data, field: val}
            bad_sha = write(bad)
            rejects(lambda: window(d / 'synthetic.txt', bad_sha))
        digest = write(data)
        manifest = dict(measurement='REAL_NEW_3DS', build='stage11a.test', hardware='SYNTHETIC_TEST_ONLY',
                        trials=[dict(scene='A', state_id='test', save_sha256='0' * 64, repeat=1, fps_mode=30,
                                     kind='stationary', file='synthetic.txt', sha256=digest)])
        (d / 'session.json').write_text(json.dumps(manifest))
        result = session(d / 'session.json')
        assert compare(result, result)['hardware_accepted'] is False
        for mutate in ('hardware', 'detail', 'camera', 'state_id'):
            changed = copy.deepcopy(result)
            if mutate == 'hardware':
                changed['hardware'] = 'OTHER'
            elif mutate == 'detail':
                changed['trials'][0]['detail'] = 1
            elif mutate == 'camera':
                changed['trials'][0]['static_context_stable'] = False
            else:
                changed['trials'][0]['trial']['state_id'] = 'OTHER'
            rejects(lambda: compare(result, changed))
        manifest['measurement'] = 'EMULATOR'
        (d / 'session.json').write_text(json.dumps(manifest))
        rejects(lambda: session(d / 'session.json'))
    overflow = quantile([1000, *([0] * 255), 1], 0.99)
    assert overflow == dict(lower_ms=255, upper_ms=None)
    result = dict(status='PASS', scope='SYNTHETIC_REPORT_TESTS_NOT_HARDWARE',
                  rejects=['hash mismatch', 'incomplete sample', 'frame mismatch', 'histogram mismatch',
                           'missing SPU', 'different hardware', 'different detail', 'camera drift',
                           'different state', 'emulator/hardware mixing'], overflow_quantile=overflow)
    (PORT / 'reports/stage11a-analysis-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
