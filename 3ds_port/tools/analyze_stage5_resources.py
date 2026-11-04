#!/usr/bin/env python3
"""Resource metadata/working-set report; never extracts or ships game assets."""
from pathlib import Path
import json,re,sys
p=Path(__file__).resolve().parents[1];root=p.parent
table={}
for line in (root/'src/main/filetable.c.USA.inc').read_text().splitlines():
    m=re.search(r'/\*\s*(\d+)\s*\*/\s*\{\s*(0x\w+),\s*(\d+),.*// (.*)',line)
    if m:
        i,lba,blocks,name=m.groups();size=int(blocks)*256
        table[int(i)]={'id':int(i),'lba':int(lba,16),'bytes':size,'rounded_bytes':(size+2047)&~2047,'name':name}
thr=[v for v in table.values() if v['name'].startswith('BG/THR')]
report={'THR_background_library':{'files':len(thr),'rounded_bytes':sum(v['rounded_bytes'] for v in thr),
        'lba_begin':min(v['lba'] for v in thr),'lba_end':max(v['lba']+v['rounded_bytes']//2048 for v in thr),
        'scope':'Entire original THR background library, a conservative superset of current map traversal'},'runs':{}}
fields='map state player file x z yaw lba requested actual raw_requested raw_actual reads seeks sequential status ms io_ms'.split()
for run in sys.argv[1:]:
    directory=p/'build/azahar/runs'/run
    samples=json.loads((directory/'stage5-samples.json').read_text(encoding='utf-8-sig'));last=samples[-1]['status']
    resources=[];events={}
    for key,value in last.items():
        if key.startswith('io_file_'):
            i=int(key[8:]);calls,requested,maximum,game_calls,game_max=map(int,value.split(','))
            resources.append({**table[i],'calls':calls,'requested':requested,'maximum':maximum,'game_calls':game_calls,'game_max':game_max})
    for sample in samples:
        for key,value in sample['status'].items():
            if key.startswith(('io_request_','io_slow_')):
                parts=value.split(',')
                if len(parts)!=len(fields):continue
                e=dict(zip(fields,map(float,parts)));e['name']=table[int(e['file'])]['name']
                events[value]=e
    report['runs'][run]={'build':last['build'],'resources':resources,'events':sorted(events.values(),key=lambda e:e['map']),
        'unique_rounded_resource_bytes':sum(r['maximum'] for r in resources),
        'gameplay_unique_rounded_resource_bytes':sum(r['game_max'] for r in resources),
        'repeated_requests':sum(r['calls']-1 for r in resources),'normal_heap_total':last.get('normal_heap_total'),
        'normal_heap_used':last.get('normal_heap_used'),'normal_heap_free':last.get('normal_heap_free'),
        'linear_total':last.get('linear_total'),'linear_free':last['linear_free']}
out=p/'reports/stage5-final-resource-analysis.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'THR':report['THR_background_library'],'runs':{k:{x:v[x] for x in ('build','unique_rounded_resource_bytes','gameplay_unique_rounded_resource_bytes','repeated_requests','normal_heap_total','normal_heap_free')} for k,v in report['runs'].items()}},indent=2))
