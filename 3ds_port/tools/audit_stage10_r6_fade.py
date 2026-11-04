"""Presented fade timeline, excluding unrecorded ordinary-gameplay gaps."""
import argparse,json,statistics
from pathlib import Path
p=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('name');args=ap.parse_args()
folder=p/'reports'/('stage10-r6-'+args.name+'-pica')
s=dict(line.split('=',1) for line in (folder/'status.txt').read_text().splitlines() if '=' in line)
rows=[]
for i in range(192):
    if f'fade_present_{i}' not in s:break
    rows.append((list(map(int,s[f'fade_present_{i}'].split(','))),list(map(int,s[f'fade_cost_{i}'].split(',')))))
intervals=[]
for i in range(1,len(rows)):
    before,_=rows[i-1];now,cost=rows[i]
    if now[0]-before[0]!=1 or now[1]-before[1]!=1:continue
    intervals.append(dict(present=now[1],state=now[4],progress=now[5],progress_delta=now[5]-before[5],
        wall_ms=(now[3]-before[3])/4.096,vblanks=now[2]-before[2],source_generation=now[6],
        update_ms=cost[0]/1000,decode_ms=cost[3]/1000,resource_ms=cost[5]/1000,io_ms=cost[6]/1000,
        sync_ms=cost[7]/1000,vblank_ms=cost[8]/1000,report_ms=cost[9]/1000,reads=cost[12],bytes=cost[13]))
assert intervals and s['first_failure']=='0'
def summary(values):
    return dict(count=len(values),median_ms=statistics.median(values),mean_ms=statistics.mean(values),max_ms=max(values)) if values else None
report=dict(status='PASS',scope=__doc__,build=s['build'],name=args.name,rows=len(rows),
    intervals=intervals,all_intervals=summary([r['wall_ms'] for r in intervals]),
    no_resource_or_report=summary([r['wall_ms'] for r in intervals if r['resource_ms']<.1 and r['report_ms']<.1]),
    visible_fade_steps=summary([r['wall_ms'] for r in intervals if (r['state']&7) in (2,3,6,7) and r['progress_delta']]),
    slowest=sorted(intervals,key=lambda r:r['wall_ms'],reverse=True)[:12],
    note='Categories are inclusive/nested. Source RGB5 modulation and one final LCD presentation are unchanged.',hardware_accepted=False)
(p/'reports'/('stage10-r6-'+args.name+'-analysis.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='intervals'},indent=2))
