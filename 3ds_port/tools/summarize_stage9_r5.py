"""Summarize observed realtime continuity and export an unedited DSP excerpt."""
from pathlib import Path
import json,wave,hashlib,zipfile
import numpy as np
p=Path(__file__).resolve().parents[1];root=p.parent
dest=p/'reports/stage9-r5-ready-azahar'
r=json.loads((dest/'timeline.json').read_text());q=r['continuity'][0]
assert q['entry']==13 and q['supplied']==129360 and q['produced_sectors']==55
assert q['missing']==q['startup_missing']==q['deficient_blocks']==q['longest_gap']==0
assert not r['missing_capture_buffers']
rows=r['timeline'];active=[v for v in rows if v['active'] and 0<v['played']<129360]
xs=np.array([v['played'] for v in active]);ys=np.array([v['wall'] for v in active])
slope,intercept=np.polyfit(xs,ys,1)
matches=[];previous=0
for v in rows:
    if v['active'] and v['matched']>previous:matches.append(v);previous=v['matched']
publish_gaps=[b['wall']-a['wall'] for a,b in zip(matches,matches[1:])]
with wave.open(str(dest/'dsp-output.wav'),'rb') as w:
    frames=min(w.getnframes(),round(3.4*w.getframerate()));data=w.readframes(frames);rate=w.getframerate()
samples=np.frombuffer(data,dtype='<i2')
output=p/'build/stage9-r5-analysis';output.mkdir(exist_ok=True)
clip=output/'harry-cheryl-realtime-dsp.wav'
with wave.open(str(clip),'wb') as w:
    w.setparams((2,2,rate,0,'NONE','not compressed'));w.writeframes(data)
with wave.open(str(p/'build/stage9-r4-analysis/entry13-corrected-arm-spu.wav'),'rb') as w:
    reference=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)
nonzero=np.flatnonzero(np.any(reference,axis=1))
assert q['first_nonzero']==nonzero[0] and q['last_nonzero']==nonzero[-1]
alignment=json.loads((dest/'waveform-alignment.json').read_text())
strong=[v for v in alignment['windows'] if v['correlation']>.6]
offsets=[v['offset_seconds'] for v in strong]
report=dict(status='PASS',scope='Observed Azahar real threads and DSP; NOT a hardware result',
    entry=13,source_rate=37800,source_frames=110880,source_theoretical_seconds=110880/37800,
    output_rate=44100,expected_output_frames=129360,output_theoretical_seconds=129360/44100,
    supplied_output_frames=q['supplied'],supplied_audio_clock_seconds=q['supplied']/44100,
    inserted_underflow_silence_frames=q['missing'],startup_missing_frames=q['startup_missing'],
    longest_underflow_ms=q['longest_gap']/44.1,active_deficient_blocks=q['deficient_blocks'],
    minimum_ring_after_pull=q['min_after'],minimum_ring_ms=q['min_after']/44.1,
    observed_max_publish_gap_ms=max(publish_gaps)*1000,
    source_sector_output_frames=2352,source_sector_audio_ms=2352/44.1,source_sector_required_per_second=44100/2352,
    measured_worker_wakes_per_second=(active[-1]['worker_wakes']-active[0]['worker_wakes'])/(active[-1]['wall']-active[0]['wall']),
    wall_duration_linear_fit_seconds=float(slope*129360),wall_sampling_precision_note='512-frame blocks plus read-only RPC polling; use audio clock for exact duration',
    nonzero_audio_clock_seconds=(q['last_nonzero']-q['first_nonzero']+1)/44100,
    reference_nonzero_audio_clock_seconds=(int(nonzero[-1])-int(nonzero[0])+1)/44100,
    theoretical_minus_supplied_seconds=(129360-q['supplied'])/44100,
    eof_silence_after_source_frames=q['eof_padding'],eof_silence_note='After final XA data, while the original page finishes; not starvation or an internal speech gap',
    before_supplied_frames=119296,before_truncated_frames=129360-119296,before_truncated_ms=(129360-119296)/44.1,
    dsp_native_clock_hz=r['dsp_clock_hz'],wav_integer_header_rate=rate,excerpt_frames=frames,excerpt_seconds=frames/rate,
    excerpt_peak=int(np.max(np.abs(samples.astype(np.int32)))),excerpt_saturated=int(np.sum((samples==-32768)|(samples==32767))),
    dsp_reference_alignment_good_windows=len(strong),dsp_reference_alignment_offset_range_ms=(max(offsets)-min(offsets))*1000,
    clip=clip.relative_to(root).as_posix(),clip_sha256=hashlib.sha256(clip.read_bytes()).hexdigest(),
    producer_scheduling_changed=False,prebuffer_changed=False,authored_timers_pitch_rate_changed=False,
    correction='Subtitle timing begins after actual PCM delivery to SPU; queued/playing driver ID is insufficient',
    hardware_accepted=False,no_new_hardware_candidate=True)
(p/'reports/stage9-r5-continuity-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
