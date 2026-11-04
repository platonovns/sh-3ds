"""Compare EARLY/DEGRADED/warm New Game/cold restart without inventing an owner."""
import argparse
import hashlib
import json
from pathlib import Path

GROUPS = {'memory':9,'render':40,'cache':24,'profile':48,'spu':16,'xa':16,'audio':14,'resource':10}


def read(path):
    raw=path.read_bytes();data={}
    for line in raw.decode('utf-8-sig').splitlines():
        if '=' not in line:continue
        key,value=line.split('=',1)
        if key in data and key.startswith(('lifetime_','sample_')):raise ValueError('Duplicate '+key)
        data[key]=value
    assert data['sample_complete']=='1' and data['report_complete']=='1' and data['lifetime_schema']=='1'
    assert data['build_variant'] in ('STAGE11A_LIFETIME_INVESTIGATION','STAGE11A_LIFETIME_TRACE_FIX_CANDIDATE','STAGE11A_CPU_CANDIDATE')
    def snap(label):
        prefix='lifetime_'+label+'_'
        stamp=data[prefix+'stamp'].split(',');assert len(stamp)==7
        row=dict(serial=int(stamp[0]),reason=int(stamp[1]),uptime_ms=float(stamp[2]),probe_ms=float(stamp[3]),
                 mode=int(stamp[4]),thread_result=int(stamp[5],0),threads=int(stamp[6]),
                 context=list(map(int,data[prefix+'context'].split(','))))
        for group,n in GROUPS.items():
            row[group]=list(map(int,data[prefix+group].split(',')));assert len(row[group])==n
        row['voices']=[list(map(int,data[prefix+f'voice_{i:02}'].split(','))) for i in range(24)]
        assert all(len(v)==10 for v in row['voices'])
        row['allocator']={key.removeprefix(prefix+'alloc_'):list(map(int,val.split(',')))
                          for key,val in data.items() if key.startswith(prefix+'alloc_')}
        return row
    begin,end=snap('begin'),snap('end')
    assert begin['mode']==end['mode'], 'A mode change inside a window is not a valid timing trial'
    assert end['uptime_ms']>=begin['uptime_ms']
    history=[snap(f'history_{i:02}') for i in range(int(data['lifetime_history_used']))]
    assert len(history)<=int(data['lifetime_history_capacity'])==32
    counters={name:(end['render'][index]-begin['render'][index])&0xffffffff for name,index in
              [('hits',9),('misses',10),('probes',11),('invalidations',12),('uploads',13),('evictions',14)]}
    frames=int(data['sample_lcd_frames']);assert frames>0
    return dict(file=str(path),sha256=hashlib.sha256(raw).hexdigest(),build=data['build'],session=data['lifetime_session'],
                fps=float(data['sample_lcd_fps']),duration_ms=float(data['sample_duration_ms']),frames=frames,
                pose_changed=int(data['sample_context_changed_mask'],0),first=snap('first'),begin=begin,end=end,history=history,
                cache_delta=counters,cache_per_frame={k:v/frames for k,v in counters.items()},
                frame_cost_ms={key.removeprefix('sample_profile_'):float(value) for key,value in data.items()
                               if key.startswith('sample_profile_') and key.endswith('_mean_ms')},
                spu_block=data.get('stage11a_metric_spu_block'),
                profiling_enabled=bool(begin['mode']), memory_largest_available=False)


def state(row):
    s=row['end'];m=s['memory'];r=s['render'];p=s['spu']
    return dict(heap_used=m[1],heap_free_chunks=m[2],free_chunks=m[3],top_chunk=m[4],linear_free=m[6],vram_free=m[8],
                cache_entries=r[2],cache_pinned=r[3],cache_dirty=r[4],cache_allocations=r[7],renderer_textures=r[32],
                pending_draws=r[17],pending_primitives=r[18],pending_vertices=r[19],packet_peak=r[20],
                silent_nonzero_pitch_voices=p[8],ever_keyed_voices=p[4],envelope_nonzero=p[6],frozen_voices=p[7],spu_resets=p[0],
                xa_queue=s['xa'][3],cd_queue=p[9],threads=s['threads'])


def compare(rows):
    assert len(rows)==4
    a,b,w,c=rows
    assert a['session']==b['session']==w['session'] and c['session']!=w['session'], 'Wrong process sequence'
    assert a['build']==b['build']==w['build']==c['build'], 'Different binaries'
    states=list(map(state,rows))
    growth={k:states[1][k]-states[0][k] for k in states[0] if states[1][k]!=states[0][k]}
    stable=[k for k in states[0] if states[1][k]==states[0][k]]
    warm_vs_cold={k:states[2][k]-states[3][k] for k in states[0] if states[2][k]!=states[3][k]}
    warnings=[]
    if a['pose_changed'] or b['pose_changed'] or a['begin']['context']!=b['begin']['context']:
        warnings.append('EARLY/DEGRADED player/camera/context is not matched; attribution limited')
    if w['begin']['context']!=c['begin']['context']:
        warnings.append('Warm/cold New Game context differs; attribution limited')
    if len(set(r['profiling_enabled'] for r in rows))!=1:
        warnings.append('Profiling modes differ; use this as diagnostics-overhead evidence, not a game optimization A/B')
    leads=[]
    if states[1]['silent_nonzero_pitch_voices']>states[0]['silent_nonzero_pitch_voices']:
        leads.append('SPU decoder work can grow while voices are silent; correlate block cost and retained warm/cold voice state')
    if states[1]['renderer_textures']>states[0]['renderer_textures']:
        leads.append('Texture allocations/list grew; distinguish capped warm-up from continued growth across repeated cycles')
    if states[1]['linear_free']<states[0]['linear_free'] or states[1]['heap_used']>states[0]['heap_used']:
        leads.append('Memory use rose; bounded caches and allocator retention do not by themselves prove a leak')
    if states[1]['free_chunks']>states[0]['free_chunks']:
        leads.append('More free heap chunks; fragmentation is possible, largest block is unavailable')
    return dict(status='ANALYZED_NOT_HARDWARE_ACCEPTED',labels=['EARLY','DEGRADED','WARM_NEW_GAME','COLD_RESTART'],
                windows=rows,states=states,early_to_degraded_changes=growth,early_to_degraded_stable=stable,
                warm_minus_cold=warm_vs_cold,warnings=warnings,leads=leads,
                owner_confirmed=False,true_memory_leak_proven=False,diagnostic_causality_proven=False,
                note='Use profile costs and matched repeated windows; lifetime high-water counters are not live allocations. No automatic fix or reset.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records',nargs=4,type=Path)
    parser.add_argument('--source',choices=('hardware','emulator','synthetic'),default='hardware')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();rows=[read(p) for p in args.records];result=compare(rows);result['measurement_source']=args.source
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('early_to_degraded_changes','early_to_degraded_stable','warm_minus_cold','warnings','leads')},indent=2))
