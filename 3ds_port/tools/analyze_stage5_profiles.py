#!/usr/bin/env python3
"""Compare bounded phase windows and event records, without scene equivalence claims."""
from pathlib import Path
import argparse,json,statistics
p=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('runs',nargs='+');args=parser.parse_args()
cats='update gte_sampled primitive cache decode upload_flush submit resource io sync vblank report'.split()
old_counts='gte_ops cache_probes decodes uploads upload_bytes reads read_bytes raw_reads raw_bytes primitives batches draws'.split()
new_counts=old_counts[:9]+['raw_seeks']+old_counts[9:]
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
result={'scope':'Azahar phase measurements; different player/camera histories can change cost. GTE is sampled; phases overlap.', 'runs':{}}
for run_name in args.runs:
    run=p/'build/azahar/runs'/run_name;samples=read(run/'stage5-samples.json')
    states=[s['status'] for s in samples if s['status'].get('profile')=='DETAILED' and s['status'].get('profile_frames')=='120']
    gameplay=[s for s in states if int(s['map_frames'])>700 and s['player_state']=='0']
    cutscenes=[s for s in states if int(s['map_frames'])>60 and s['player_state']!='0']
    events={}
    for status in states:
        for key,value in status.items():
            if not (key.startswith('profile_slow_') or key.startswith('profile_io_slow_')) or key=='profile_slow_schema':continue
            parts=value.split(',');version=int(status.get('profile_slow_schema','1'))
            counts=new_counts if version>=2 else old_counts
            base=7 if version>=2 else 6
            if len(parts)!=base+len(cats)+len(counts):continue
            event=dict(zip(['map','x','z','yaw','file','wall_ms'],map(float,parts[:6])))
            event['gte_sampled']=int(parts[6]) if version>=2 else None
            event.update({k+'_ms':float(v) for k,v in zip(cats,parts[base:base+len(cats)])})
            event.update({k:float(v) for k,v in zip(counts,parts[base+len(cats):])})
            events[tuple(parts)]=event
    decoded=[e for e in events.values() if e['decodes']>0]
    data={'build':read(run/'run.json')['build_identity'],'sha256':read(run/'run.json')['build_sha256'],
          'gameplay_windows':len(gameplay),'cutscene_windows':len(cutscenes),'groups':{},
          'decode_events':sorted(decoded,key=lambda x:x['decode_ms'],reverse=True),
          'io_events':sorted([e for e in events.values() if e['reads']>0],key=lambda x:x['resource_ms'],reverse=True),
          'top_slow':sorted(events.values(),key=lambda x:x['wall_ms'],reverse=True)[:12]}
    for label,rows in [('gameplay',gameplay),('cutscene',cutscenes)]:
        if rows:data['groups'][label]={'windows':len(rows),'means':{k:statistics.mean(float(s[k]) for s in rows)
            for k in rows[0] if k.startswith('profile_') and (k.endswith('_ms') or k.endswith('_per_frame')) and all(k in s for s in rows)}}
    if decoded:data['median_decode_ms_per_page_in_recorded_events']=statistics.median(e['decode_ms']/e['decodes'] for e in decoded)
    if gameplay:data['memory_ranges']={k:[min(int(s[k]) for s in gameplay),max(int(s[k]) for s in gameplay)] for k in ('heap_used','linear_free','cache_active')}
    result['runs'][run_name]=data
out=p/'reports/stage5-pass2-profile-comparison.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({r:{k:v for k,v in d.items() if k not in ('top_slow','decode_events','io_events')} for r,d in result['runs'].items()},indent=2))
