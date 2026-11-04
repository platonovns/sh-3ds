"""Reproduce R4 starvation with sector IO latency, then test bounded batching."""
from pathlib import Path
import subprocess,zipfile,os,json,wave
p=Path(__file__).resolve().parents[1];root=p.parent
dest=p/'build/stage9-r6-latency';dest.mkdir(exist_ok=True)
with zipfile.ZipFile(p/'baselines/stage9-audio-r4.zip') as z:(dest/'r4.cpp').write_bytes(z.read('3ds_port/source/game_xa.cpp'))
a=root/'pc_port/PsyCross/src/audio'
subprocess.run(['gcc','-O2','-fwrapv','-c',str(p/'build/audio/xa_decode.c'),'-o',str(dest/'decode.o')],check=True)
report=[]
for label,source,burst in [('r4',dest/'r4.cpp',1),('working',p/'source/game_xa.cpp',1)]:
    subprocess.run(['g++','-std=c++17','-O2','-fwrapv','-I'+str(p/'include'),'-I'+str(a),
        '-Dfopen=xa_test_fopen','-c',str(source),'-o',str(dest/(label+'.o'))],check=True)
    binary=dest/label
    subprocess.run(['g++','-std=c++17','-O2','-I'+str(p/'include'),str(p/'tests/stage9_r6_latency.cpp'),
        str(dest/(label+'.o')),str(dest/'decode.o'),str(a/'PsyX_XAStream.cpp'),'-pthread','-Wl,--wrap=fread,--wrap=__fread_chk','-o',str(binary)],check=True)
    for latency,bandwidth,jitter in [(9,2*1024*1024,0),(12,1024*1024,20),(18,1024*1024,40)]:
        pcm=dest/f'{label}-{latency}ms.pcm'
        run=subprocess.run([str(binary),str(latency),str(bandwidth),str(jitter),str(pcm),str(burst)],
            env=dict(os.environ,SH_XA_BIN=str(root/'sh1_data/sh1.bin')),check=True,capture_output=True,text=True)
        row=dict(label=label,fixed_read_latency_ms=latency,bytes_per_second=bandwidth,jitter_ms=jitter,**json.loads(run.stdout))
        assert row['read_calls']>0,'IO delay hook did not intercept native reads'
        data=pcm.read_bytes()
        with wave.open(str(pcm.with_suffix('.wav')),'wb') as w:
            w.setparams((2,2,44100,0,'NONE','not compressed'));w.writeframes(data)
        report.append(row)
assert all(v['missing']>0 and v['read_calls']==433 for v in report if v['label']=='r4')
assert all(v['missing']==v['longest_gap_frames']==0 and v['read_calls']==14 for v in report if v['label']=='working')
assert all(abs(v['duration_seconds']-129360/44100)<1e-8 for v in report if v['label']=='working')
assert len({v['supplied_pcm_hash'] for v in report})==1,'Batching changed decoded PCM'
sweep=[]
for latency,bandwidth,jitter in [(12,1024*1024,20),(18,1024*1024,40)]:
    for phase in range(23):
        run=subprocess.run([str(dest/'working'),str(latency),str(bandwidth),str(jitter),os.devnull,'1',str(phase)],
            env=dict(os.environ,SH_XA_BIN=str(root/'sh1_data/sh1.bin')),check=True,capture_output=True,text=True)
        row=json.loads(run.stdout)
        assert row['missing']==row['longest_gap_frames']==0,(latency,jitter,phase,row)
        assert row['supplied_pcm_hash']==report[0]['supplied_pcm_hash']
        sweep.append(dict(latency_ms=latency,jitter_ms=jitter,phase=phase,**row))
(p/'reports/stage9-r6-latency-phase-sweep.json').write_text(json.dumps(sweep,indent=2)+'\n')
(p/'reports/stage9-r6-latency.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
