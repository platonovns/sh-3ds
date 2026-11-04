"""Read morning windows; report bounded histogram quantiles without false precision."""
import argparse,hashlib,json,math
from pathlib import Path
from analyze_stage11a_lifetime import read,state
from analyze_stage11a_tracefix import analyze as analyze_trace
PORT=Path(__file__).resolve().parents[1]

def analyze(path):
    parsed={k:v for line in path.read_text(encoding='utf-8-sig').splitlines() if '=' in line for k,v in [line.split('=',1)]}
    row=read(path);metrics={}
    for name in ('wall','work','spu_block','spu_render','main_lock','spu_lock'):
        raw=parsed.get('stage11a_metric_'+name)
        if raw is None:continue
        valid,calls,total,peak,misses=map(float,raw.split(','))
        metric=dict(valid=bool(valid),calls=int(calls),mean_ms=total/calls if calls else None,max_ms=peak,deadline_exceedances=int(misses))
        hist=parsed.get('stage11a_hist_'+name)
        if hist:
            width,*counts=map(int,hist.split(','));assert len(counts)==256
            for q in (95,99):
                rank=math.ceil(sum(counts)*q/100);count=0
                for i,n in enumerate(counts):
                    count+=n
                    if rank and count>=rank:
                        metric['p'+str(q)+'_ms_interval']=[i*width/1000,(i+1)*width/1000 if i<255 else None];break
        metrics[name]=metric
    trace={}
    if parsed.get('pitch_trace_schema')=='1':
        for folder in ('stage11a-cpu-A','stage11a-cpu-B','stage11a-tracefix'):
            manifest_path=PORT/'build'/folder/'manifest.json'
            if not manifest_path.exists():continue
            manifest=json.loads(manifest_path.read_text())
            if manifest['build']!=row['build']:continue
            symbols={}
            for line in (manifest_path.parent/'symbols.txt').read_text().splitlines():
                fields=line.split()
                if len(fields)==3 and fields[1].lower()=='t' and not fields[2].startswith('$'):symbols.setdefault(int(fields[0],16),fields[2])
            resolved=analyze_trace(path,manifest,symbols)
            trace=dict(elf_sha256=manifest['elf_sha256'],events=resolved['events'],fast_stats=resolved['fast_stats'],note=resolved['note'])
            break
    return dict(file=str(path),build=row['build'],sha256=row['sha256'],fps=row['fps'],duration_ms=row['duration_ms'],
        profiling=row['profiling_enabled'],F1=parsed.get('silent_fast_mode'),fast_stats=parsed.get('silent_fast_stats'),
        affinity_requested=parsed.get('stage11a_spu_requested_core'),core_observations={k:v for k,v in parsed.items() if k.startswith('cpu_observed_') or k.endswith('_create')},
        metrics=metrics,audio=parsed.get('stage11a_audio_window'),queue=parsed.get('stage11a_queue_depth_after_submit'),
        memory_and_state=state(row),frame_cost_ms=row['frame_cost_ms'],
        cpu_counters={k:v for k,v in parsed.items() if k.startswith('sample_profile_') and not k.endswith(('_ms','frames','basis','audio'))},
        pitch_trace_total=parsed.get('pitch_trace_total'),pitch_trace_resolved=trace,hardware_acceptance=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('files',nargs='+',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=dict(scope='HARDWARE_WINDOWS_ONLY_IF_INPUTS_ARE_FROM_HARDWARE',windows=[analyze(p) for p in args.files])
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    print(text)
