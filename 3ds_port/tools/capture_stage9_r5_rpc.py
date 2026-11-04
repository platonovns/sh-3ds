"""Observe an owned Azahar run without pausing or writing guest memory.

Native pad fixtures only navigate New Game -> first Cheryl. Capture the actual
NDSP-submitted buffers by sequence ID; reject a WAV with missing capture buffers.
"""
from pathlib import Path
import sys,struct,time,json,wave,hashlib,os
sys.path.insert(0,r'C:\azahar-windows\scripting')
from AzaharRPC import AzaharRPC
p=Path(__file__).resolve().parents[1];root=p.parent
label=os.environ.get('XA_CAPTURE_LABEL','r4')
symbols={v[2]:int(v[0],16) for l in (p/f'build/stage9-r5-{label}-symbols.txt').read_text().splitlines() if len(v:=l.split())==3}
c=AzaharRPC(timeout=.5,retries=1)
info_names='epoch lba file channel target active paused done error read write count elapsed played starts stops raw matched underflows peak_queue rate channels ll lr rr rl'.split()
def info():return dict(zip(info_names,struct.unpack('<26I',c.read_memory(symbols['_ZN12_GLOBAL__N_1L1sE'],104))))
def word(n):return struct.unpack('<I',c.read_memory(symbols[n],4))[0]
def request():return struct.unpack('<3I',c.read_memory(symbols['_ZN12_GLOBAL__N_1L1dE'],12))[2]
def pad(text):
    target=root/'sh1_data/stage7_pad.txt'
    assert not target.exists()
    target.write_text(text,encoding='ascii')
def state():return word('game_state'),word('player_state')
processes=c.process_list();assert len(processes)==1; c.set_process(next(iter(processes)))
print('processes',processes,flush=True)
perf0=c.perf_stats();began=time.monotonic();rows=[];blocks={};started=None;last=None;seq_start=None
stage='title';moved=False
pad('128 6\n0 15\n2 6\n0 180\n2 6\n0 120\n')
pcm_ptr=word('pcm');assert pcm_ptr
while time.monotonic()-began<190:
    now=time.monotonic()-began
    i=info();entry=request()
    if not moved and state()==(11,0) and not (root/'sh1_data/stage7_pad.txt').exists():
        pad('MOVE -24576 532480 2048 6000\n');moved=True;print('move',now,flush=True)
    if entry and not started:
        started=now;stage='speech';print('speech',entry,now,flush=True)
    if started:
        meta=c.read_memory(symbols['buffers'],96)
        pcm=c.read_memory(pcm_ptr,8192)
        meta2=c.read_memory(symbols['buffers'],96)
        seqs=[]
        for b in range(4):
            address,frames=struct.unpack_from('<2I',meta,b*24)
            seq=struct.unpack_from('<H',meta,b*24+18)[0]
            seq2=struct.unpack_from('<H',meta2,b*24+18)[0]
            seqs.append(seq)
            if seq and seq==seq2 and seq not in blocks:
                assert address==pcm_ptr+b*2048 and frames==512
                blocks[seq]=pcm[b*2048:(b+1)*2048]
        if seq_start is None:seq_start=min(s for s in seqs if s)
        row=dict(wall=now,entry=entry,rendered=word('rendered'),starves=word('starved'),worker_wakes=word('xa_wakes'),**i)
        rows.append(row)
        if now-started>12 or entry!=rows[0]['entry']:
            last=now;break
    time.sleep(.004 if started else .1)
dest=p/f'reports/stage9-r5-{label}-azahar';dest.mkdir(exist_ok=True)
report=dict(scope=__doc__,label=label,perf_start=perf0,perf_end=c.perf_stats(),timeline=rows,
    captured_buffers=len(blocks),capture_first_sequence=seq_start,capture_last_sequence=max(blocks,default=0),
    wall_start=started,wall_end=last)
if blocks:
    # The first metadata read may race a buffer that was already being reused
    # before this observation started. Preserve that fact, then use the first
    # completely captured pre-speech buffer as the capture boundary.
    report['uncaptured_leading_buffers']=min(blocks)-seq_start
    seq_start=min(blocks)
    missing=sorted(set(range(seq_start,max(blocks)+1))-blocks.keys());report['missing_capture_buffers']=missing
    (dest/'buffers.pcm').write_bytes(b''.join(blocks[n] for n in sorted(blocks)))
    report['buffer_sequences']=sorted(blocks)
    if not missing:
        data=b''.join(blocks[n] for n in range(seq_start,max(blocks)+1))
        with wave.open(str(dest/'ndsp-submitted.wav'),'wb') as w:
            w.setparams((2,2,44100,0,'NONE','not compressed'));w.writeframes(data)
        report['captured_audio_seconds']=len(data)/4/44100
if 'stage9_probe_capture' in symbols:
    (dest/'timeline.json').write_text(json.dumps(report,indent=2)+'\n')
    data,frames,_,offset=struct.unpack('<4I',c.read_memory(symbols['stage9_probe_capture'],16))
    dsp=c.read_memory(data,offset*4)
    with wave.open(str(dest/'dsp-output.wav'),'wb') as w:
        w.setparams((2,2,32728,0,'NONE','not compressed'));w.writeframes(dsp)
    report['dsp_capture_frames']=offset
    report['dsp_clock_hz']=268111856/8192
    report['dsp_seconds']=offset/report['dsp_clock_hz']
    name=next(n for n in symbols if n.endswith('L10continuityE'))
    report['continuity']=[]
    fields='entry epoch target pulls requested supplied startup_missing missing eof_padding min_before min_after deficient_blocks longest_gap current_gap first_nonzero last_nonzero nonzero_started produced_sectors cancel_reason'.split()
    for j in range(1):
        words=struct.unpack('<148I',c.read_memory(symbols[name],592))
        q=dict(zip(fields,words[:19]));q['holes']=[list(words[19+k*4:23+k*4]) for k in range(words[-1])]
        report['continuity'].append(q)
(dest/'timeline.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='timeline'},indent=2))
