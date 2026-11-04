"""Reconcile every live SDK linear allocation and repeated room/menu stress."""
import bisect,json,os,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1]
folder=p/'reports/stage10-r6-memory-stress-pica'
s=dict(line.split('=',1) for line in (folder/'status.txt').read_text().splitlines() if '=' in line)
q=json.loads((folder/'qualification.json').read_text(encoding='utf-8-sig'))
assert q['status']=='PASS' and s['r6_stress_laps']=='6' and int(s['r6_stress_rooms'])>=12
assert s['r6_linear_overflow']=='0'
elf=p/'build/stage10-dev-scene-5-memory-stress/diagnostic.elf'
nm=subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-nm'),'-n',str(elf)],text=True)
symbols=[]
for line in nm.splitlines():
    v=line.split()
    if len(v)==3 and v[1] in ('T','t'):symbols.append((int(v[0],16),v[2]))
addresses=[v[0] for v in symbols];allocations=[]
for k,v in s.items():
    if not k.startswith('r6_linear_allocation_'):continue
    caller,requested,actual=v.split(',');pc=int(caller,16)&~1
    symbol=symbols[max(0,bisect.bisect_right(addresses,pc-1)-1)][1]
    allocations.append(dict(index=int(k.rsplit('_',1)[1]),caller=caller,owner=symbol,requested=int(requested),bytes=int(actual)))
allocations.sort(key=lambda a:a['index'])
groups={}
for a in allocations:
    key=(a['owner'],a['requested'],a['bytes'])
    if key not in groups:groups[key]=dict(owner=a['owner'],requested_each=a['requested'],bytes_each=a['bytes'],count=0,total=0)
    groups[key]['count']+=1;groups[key]['total']+=a['bytes']
total=sum(a['bytes'] for a in allocations);free=int(s['linear_free']);capacity=int(s['linear_total'])
assert total==int(s['r6_linear_live_bytes']) and total+free==capacity
samples=[int(s[f'r6_stress_free_{i}']) for i in range(6)]
assert len(set(samples[1:]))==1,'Linear memory keeps declining after cache warm-up'
assert int(s['cache_active'])<=96
report=dict(status='PASS',scope=__doc__,diagnostic=q['diagnostic'],cycles=6,door_transitions=int(s['r6_stress_rooms']),
    status_map_cycles=6,free_after_cycles=samples,stable_after_warmup=True,leak_observed=False,
    linear_capacity=capacity,live_bytes=total,free_bytes=free,minimum_free=int(s['r6_linear_min_free']),
    cache_active=int(s['cache_active']),cache_limit=96,groups=list(groups.values()),allocations=allocations,
    stage7_used=28491008,r5_full_cache_used=31112448,delta=2621440,
    delta_explanation=dict(readback_color_mask=2097152,feedback_texture=524288),
    projected_full_cache_free=free-(96-int(s['cache_active']))*262144,
    limitation='Diagnostic DSP output can be unavailable; active hardware PCM requires an additional 8192 linear bytes. No claim of all possible future routes.',
    hardware_accepted=False)
(p/'reports/stage10-r6-memory-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('allocations','diagnostic')},indent=2))
