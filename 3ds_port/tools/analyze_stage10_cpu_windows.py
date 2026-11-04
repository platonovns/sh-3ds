"""Analyze immutable hardware recording windows without using lifetime timings."""
import argparse
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_sample(path, label, elf_data, symbols):
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            require(key not in values, f'{path}: duplicate {key}')
            values[key] = value
    for key, expected in (('cpu_record_schema', '1'), ('sample_complete', '1'),
                          ('report_complete', '1'), ('cpu_audit_schema', '2'),
                          ('build_variant', 'CPU_AUDIT_RECORDER_ONLY'),
                          ('reference_scope', 'LIFETIME_AT_SAVE_NOT_RECORDING_WINDOW')):
        require(values.get(key) == expected, f'{path}: unsupported/incomplete {key}')
    require(values['build'].encode() in elf_data, 'Use the exact recording ELF')
    duration = float(values['sample_duration_ms'])
    frames = int(values['sample_profile_frames'])
    require(math.isfinite(duration) and duration > 0 and frames > 0, 'Empty window')
    require(frames == int(values['sample_lcd_frames']), 'LCD/profile frame mismatch')
    fps = frames * 1000 / duration
    require(abs(fps - float(values['sample_lcd_fps'])) < .0001, 'FPS mismatch')
    require(abs(duration - float(values['sample_profile_wall_ms'])) < 1, 'Window mismatch')
    context_keys = values['sample_context_schema'].split(',')
    contexts = {}
    for boundary in ('start', 'end'):
        row = values[f'sample_{boundary}_context'].split(',')
        require(len(row) == len(context_keys), 'Invalid context')
        contexts[boundary] = dict(zip(context_keys, row))
    scopes = {}
    for name in ('spu_block', 'spu_wait', 'xa_step', 'xa_wait', 'flashlight_setup', 'resolve'):
        valid, count, total, mean = values[f'sample_cpu_{name}'].split(',')
        require(valid == '1', f'{path}: incoherent {name} snapshot')
        count, total, mean = int(count), float(total), float(mean)
        require(count >= 0 and math.isfinite(total) and total >= 0, 'Invalid scope')
        require(abs((total / count if count else 0) - mean) < .00011, 'Scope mean mismatch')
        scopes[name] = dict(calls=count, elapsed_ms=total, mean_elapsed_ms=mean,
                            calls_per_second=count * 1000 / duration,
                            elapsed_wall_fraction_percent=total * 100 / duration,
                            scheduled_cpu_percent=None)
    profiles = {}
    for key, value in values.items():
        if key.startswith('sample_profile_') and key.endswith('_total_ms'):
            name = key[len('sample_profile_'):-len('_total_ms')]
            n = int(values['sample_profile_gte_frames']) if name == 'gte_sampled' else frames
            total = float(value)
            mean = float(values[f'sample_profile_{name}_mean_ms'])
            require(abs((total / n if n else 0) - mean) < .00011, 'Profile mean mismatch')
            profiles[name] = dict(elapsed_ms=total, mean_elapsed_ms=mean,
                                  elapsed_wall_fraction_percent=total * 100 / duration,
                                  denominator_frames=n)
    counts = {}
    for name in ('gte_ops', 'cache_probes', 'decodes', 'uploads', 'upload_bytes',
                 'reads', 'read_bytes', 'raw_reads', 'raw_bytes', 'raw_seeks',
                 'primitives', 'batches', 'draws'):
        count = int(values[f'sample_profile_{name}'])
        counts[name] = dict(total=count, per_frame=count / frames,
                            per_second=count * 1000 / duration)
    valid, id_result, tid, priority_result, priority = values['cpu_thread_0_runtime'].split(',')
    require(valid == '1' and int(id_result, 0) == 0 and int(priority_result, 0) == 0,
            'Main thread runtime identity/priority unavailable')
    threads = [dict(function='main', thread_id=int(tid), priority=int(priority), live=True)]
    for i in range(1, 17):
        key = f'cpu_thread_{i}_create'
        if key not in values:
            continue
        handle, tid, entry, stack, priority, core, detached, result = values[key].split(',')
        valid, id_result, runtime_tid, priority_result, runtime_priority = values[f'cpu_thread_{i}_runtime'].split(',')
        if valid == '1':
            require(int(id_result, 0) == 0 and int(runtime_tid) == int(tid), 'Reused thread handle')
        threads.append(dict(function=symbols.get(int(entry, 0), 'UNKNOWN'), entry=entry,
                            thread_id=int(tid), requested_priority=int(priority),
                            priority=int(runtime_priority) if valid == '1' and int(priority_result, 0) == 0 else None,
                            requested_core=int(core),
                            stack_bytes=int(stack), detached=bool(int(detached)),
                            create_result=result, live=valid == '1', runtime_result=id_result))
    observed = {}
    for name in ('main', 'spu', 'xa', 'ndsp'):
        tid, mask = values[f'cpu_observed_{name}'].split(',')
        observed[name] = dict(thread_id=int(tid), sampled_core_mask=int(mask, 0))
    probes = {}
    for i in range(4):
        attempted, executed, core, pending = map(int, values[f'cpu_probe_{i}'].split(','))
        probes[i] = dict(attempted=bool(attempted), executed=bool(executed),
                         observed_core=core, pending=bool(pending))
    thread_count_result, thread_count = values['cpu_process_thread_count'].split(',')
    require(int(thread_count_result, 0) == 0 and
            int(thread_count) == sum(t['live'] for t in threads), 'Thread inventory count mismatch')
    require(values['cpu_core_reader'] == 'LUMA_MPIDR_OPT_IN' and
            int(values['cpu_kext_detect_result'], 0) == 1, 'No verified hardware core reader')
    return dict(file=path.name, sha256=digest(path), label=label, build=values['build'],
                sample_number=int(values['sample_number']), duration_ms=duration, frames=frames,
                fps=fps, frame_wall_ms=duration / frames,
                work_excluding_pacing_report_pause_ms=float(values['sample_profile_work_ms']) / frames,
                context_changed_mask=int(values['sample_context_changed_mask'], 0), contexts=contexts,
                fps_mode=int(values['sample_fps_mode']), control_mode=values['sample_control_name'],
                scopes=scopes, profiles=profiles, counts=counts, threads=threads,
                observed_core_history=observed, startup_probes=probes,
                runtime={k: v for k, v in values.items() if k.startswith(('cpu_luma_', 'cpu_new3ds',
                         'cpu_apt_budget_', 'cpu_core_reader', 'cpu_process_thread_count'))},
                scheduled_cpu_percent=None, core_idle_percent=None,
                lifetime_timings_used=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples', type=Path, required=True, help='JSON file/name/label provenance list')
    ap.add_argument('--elf', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    elf_data = args.elf.read_bytes()
    readelf = Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-readelf'
    raw = subprocess.check_output([str(readelf), '-sW', str(args.elf)], text=True)
    symbols = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[3] == 'FUNC' and parts[6] != 'UND':
            symbols[int(parts[1], 16)] = parts[-1]
    samples = []
    for spec in json.loads(args.samples.read_text(encoding='utf-8-sig')):
        path = args.samples.parent / spec['file']
        require(digest(path) == spec['sha256'], f'{path}: evidence hash changed')
        samples.append(read_sample(path, spec['label'], elf_data, symbols))
    require(len(samples) == 3 and [s['sample_number'] for s in samples] == [1, 2, 3], 'Expected ordered hardware samples')
    require(len({s['build'] for s in samples}) == 1, 'Mixed builds')
    off, on, cafe = samples
    for sample in (off, on):
        require(sample['contexts']['start']['map'] == '3' and
                sample['contexts']['start']['room'] == '23', 'Expected school courtyard')
    require(off['contexts']['start']['flashlight'] == 'OFF' and
            on['contexts']['start']['flashlight'] == 'ON', 'Incorrect light pairing')
    pose = ('x', 'z', 'yaw')
    require(all(off['contexts']['start'][k] == on['contexts']['start'][k] for k in pose), 'Player pose mismatch')
    cameras_equal = all(off['contexts'][b][k] == on['contexts'][b][k]
                        for b in ('start', 'end') for k in off['contexts'][b] if k.startswith('camera_'))
    comparison = dict(off_on_camera_matched=cameras_equal,
                      flashlight_fps_change_percent=(on['fps'] / off['fps'] - 1) * 100,
                      flashlight_frame_wall_delta_ms=on['frame_wall_ms'] - off['frame_wall_ms'],
                      cafe_draws_per_frame_ratio=cafe['counts']['draws']['per_frame'] / off['counts']['draws']['per_frame'],
                      cafe_command_time_ratio=cafe['profiles']['command']['mean_elapsed_ms'] / off['profiles']['command']['mean_elapsed_ms'])
    output = dict(schema=1, source='USER_REAL_NEW_3DS_RECORDINGS_2026_10_28',
                  elf_sha256=digest(args.elf), samples=samples, comparison=comparison,
                  limitations=['Inclusive elapsed scopes, not scheduled CPU utilization.',
                               'GTE is sampled; audio substage estimates are extrapolated.',
                               'No system-wide core idle or sustained extra-core throughput measurement.',
                               'Worker calls and completed frames may straddle recording boundaries.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(elf_sha256=output['elf_sha256'], comparison=comparison,
                         samples=[dict(number=s['sample_number'], seconds=s['duration_ms']/1000,
                                       fps=s['fps'], spu_block_ms=s['scopes']['spu_block']['mean_elapsed_ms'],
                                       spu_elapsed_fraction=s['scopes']['spu_block']['elapsed_wall_fraction_percent'])
                                  for s in samples]), indent=2))


if __name__ == '__main__':
    main()
