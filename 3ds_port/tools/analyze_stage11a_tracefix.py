"""Resolve real-hardware writer PCs with the exact tracefix ELF symbol map."""
import argparse
import bisect
import hashlib
import json
from pathlib import Path
from analyze_stage11a_lifetime import read
PORT=Path(__file__).resolve().parents[1]


def analyze(path,manifest,symbols):
    row=read(path)
    data=dict(l.split('=',1) for l in path.read_text(encoding='utf-8-sig').splitlines() if '=' in l)
    assert row['build']==manifest['build'] and data['pitch_trace_schema']=='1'
    assert data['build_variant'] in ('STAGE11A_LIFETIME_TRACE_FIX_CANDIDATE','STAGE11A_CPU_CANDIDATE')
    names=data['pitch_trace_event_schema'].split(',');stats_names=data['silent_fast_stats_schema'].split(',')
    assert len(names)==28 and int(data['pitch_trace_used'])<=64
    addresses=sorted(symbols);values=[symbols[a] for a in addresses]
    def resolve(pc):
        if not pc:return None
        at=(pc&~1)-1;i=bisect.bisect_right(addresses,at)-1
        if i<0:return dict(return_pc=hex(pc),symbol='OUTSIDE_TEXT')
        return dict(return_pc=hex(pc),symbol=values[i],offset=at-addresses[i])
    events=[]
    for i in range(int(data['pitch_trace_used'])):
        v=list(map(int,data[f'pitch_trace_event_{i:02}'].split(',')));assert len(v)==len(names)
        e=dict(zip(names,v));assert e['old_pitch']==0 and e['new_pitch'] and e['env_level']==0 and e['ever_keyed']==0
        e['uptime_ms']=(e['absolute_ticks']-int(row['session'],16))/268123.480
        e['writer']=resolve(e['caller_return_address']);e['scope_caller']=resolve(e['scope_return_address']);events.append(e)
    mode=int(data['silent_fast_mode']);assert mode in (0,1)
    stats=list(map(int,data['silent_fast_stats'].split(',')));assert len(stats)==len(stats_names)
    measured=row['profiling_enabled'];block=data['stage11a_metric_spu_block'].split(',');calls=int(block[1])
    return dict(file=str(path),sha256=row['sha256'],build=row['build'],session=row['session'],fps=row['fps'],
        profile_mode=row['begin']['mode'],fix_mode=mode,context=row['begin']['context'],context_changed=row['pose_changed'],
        spu_block_mean_ms=float(block[2])/calls if measured and calls else None,
        native_state_begin=row['begin']['spu'],native_state_end=row['end']['spu'],
        fast_stats=dict(zip(stats_names,stats)),events=events,overwritten=int(data['pitch_trace_overwritten']),
        note='Trace and mode snapshots are lifetime-at-save; performance scopes are window exact. Native pitch may remain nonzero in F1.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('records',nargs='+',type=Path)
    p.add_argument('--manifest',type=Path,default=PORT/'build/stage11a-tracefix/manifest.json')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=json.loads(a.manifest.read_text());symbol_file=a.manifest.parent/'symbols.txt';symbols={}
    for line in symbol_file.read_text().splitlines():
        s=line.split()
        if len(s)==3 and s[1].lower()=='t' and not s[2].startswith('$'):symbols.setdefault(int(s[0],16),s[2])
    result=dict(status='ANALYZED_NOT_ACCEPTED',elf_sha256=manifest['elf_sha256'],
        symbol_map_sha256=hashlib.sha256(symbol_file.read_bytes()).hexdigest(),windows=[analyze(f,manifest,symbols) for f in a.records],
        hardware_fix_accepted=False)
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
