#!/usr/bin/env python3
"""Correlate bounded request/frame records; never infer hardware FPS from Azahar."""
from pathlib import Path
import json,re,statistics,sys
p=Path(__file__).resolve().parents[1];root=p.parent
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
names={}
for line in (root/'src/main/filetable.c.USA.inc').read_text().splitlines():
    m=re.search(r'/\*\s*(\d+)\s*\*/.*// (.*)',line)
    if m:names[int(m[1])]=m[2]
request_fields='map state player file x z yaw lba requested actual raw_requested raw_actual reads seeks sequential status ms io_ms'.split()
cats='update gte_sampled primitive cache decode upload_flush submit resource io sync vblank report'.split()
counts='gte_ops cache_probes decodes uploads upload_bytes reads read_bytes raw_reads raw_bytes raw_seeks primitives batches draws'.split()
def group(x,z,player):
    if player:return 'C_cutscene'
    if abs(x/4096+62)<8 and 55<z/4096<105:return 'B_garage'
    return 'A_street_approach'
def summary(values):
    return {'count':len(values),'min':min(values),'median':statistics.median(values),'max':max(values)} if values else None
result={'scope':'Azahar only. Original pad route, per-request identical LBA/byte comparisons. Phases overlap; sampled GTE has overhead. Report/VBlank remain visible in wall time.',
        'route':'Street approach then original x=-62 alley, repeated z=62..92, stops before the gate/later-map transition.', 'runs':{}}
for arg in sys.argv[1:]:
    label,name=arg.split('=',1);run=p/'build/azahar/runs'/name;samples=read(run/'stage5-samples.json');last=samples[-1]['status']
    events={};slow={};windows=[]
    for sample in samples:
        s=sample['status']
        for key,value in s.items():
            if key.startswith(('io_request_','io_slow_')):
                parts=value.split(',')
                if len(parts)!=len(request_fields):continue
                e=dict(zip(request_fields,map(float,parts)));e['name']=names[int(e['file'])]
                e['raw_offset']=int(e['lba'])*2352;e['scene']=group(e['x'],e['z'],int(e['player']))
                if e['map']>700:events[value]=e
            if key.startswith(('profile_slow_','profile_io_slow_')):
                parts=value.split(',')
                if len(parts)!=7+len(cats)+len(counts):continue
                e=dict(zip('map x z yaw file wall_ms sampled'.split(),map(float,parts[:7])))
                e.update({k+'_ms':float(v) for k,v in zip(cats,parts[7:19])})
                e.update({k:float(v) for k,v in zip(counts,parts[19:])})
                e['work_ms']=max(0,e['wall_ms']-e['vblank_ms']);e['work_without_report_ms']=max(0,e['work_ms']-e['report_ms'])
                e['scene']=group(e['x'],e['z'],0);slow[value]=e
        if int(s['map_frames'])>700:
            detailed=s.get('profile_frames')=='120'
            w={'elapsed':sample['elapsed'],'map':int(s['map_frames']),'x':int(s['player_x']),'z':int(s['player_z']),
               'yaw':int(s['player_yaw']),'scene':group(int(s['player_x']),int(s['player_z']),int(s['player_state'])),
               'primitives':float(s['profile_primitives_per_frame'] if detailed else s['recent_primitives']),
               'wall_ms':float(s['profile_wall_ms'] if detailed else s['recent_frame_ms']),
               'work_ms':float(s['profile_work_ms']) if detailed else float(s['recent_frame_ms'])-float(s['recent_wait_ms']),
               'report_ms':float(s.get('profile_report_ms','0')),'cache_evictions':int(s['cache_evictions']),
               'heap':int(s['heap_used']),'linear':int(s['linear_free'])}
            if detailed:w['phases']={c:float(s['profile_'+c+'_ms']) for c in cats}
            windows.append(w)
    ev=sorted(events.values(),key=lambda e:e['map']);groups={}
    for scene in ('A_street_approach','B_garage','C_cutscene'):
        rows=[e for e in ev if e['scene']==scene];ws=[w for w in windows if w['scene']==scene]
        groups[scene]={'requests':len(rows),'request_ms':summary([e['ms'] for e in rows]),'raw_io_ms':summary([e['io_ms'] for e in rows]),
            'raw_reads':sum(int(e['reads']) for e in rows),'raw_seeks':sum(int(e['seeks']) for e in rows),
            'logical_bytes':sum(int(e['requested']) for e in rows),'raw_actual_bytes':sum(int(e['raw_actual']) for e in rows),
            'windows':len(ws),'window_wall_ms':summary([w['wall_ms'] for w in ws]),'window_work_ms':summary([w['work_ms'] for w in ws])}
    pose={}
    for w in windows:
        if w['map']<3000 or w['scene']!='B_garage' or w['report_ms']>.1:continue
        key=(round(w['x']/4096/8),int(w['z']/4096/16),int(((w['yaw']+256)%4096)/512))
        pose.setdefault(key,[]).append(w)
    matched=[]
    for key,rows in pose.items():
        first,last_pose=rows[0],rows[-1]
        if len(rows)<2 or last_pose['elapsed']-first['elapsed']<120:continue
        if abs(first['primitives']-last_pose['primitives'])>max(50,first['primitives']*.05):continue
        matched.append({'pose_bin':key,'samples':len(rows),'first':first,'last':last_pose,'work_change_ms':last_pose['work_ms']-first['work_ms']})
    resources=[]
    for k,v in last.items():
        if k.startswith('io_file_'):
            i=int(k[8:]);calls,requested,maximum,game_calls,game_max=map(int,v.split(','))
            resources.append({'file':i,'name':names[i],'calls':calls,'requested':requested,'maximum':maximum,'game_calls':game_calls,'game_max':game_max})
    result['runs'][label]={'directory':name,'build':last['build'],'sha256':read(run/'run.json')['build_sha256'],
        'profile':last['profile'],'route_laps':int(last.get('route_laps','0')),'groups':groups,'requests':ev,
        'slow_frames':sorted(slow.values(),key=lambda e:e['work_without_report_ms'],reverse=True),
        'windows':windows,'matched_pose_windows':matched,'resources':resources,
        'unique_resource_bytes':sum(r['maximum'] for r in resources),'gameplay_unique_bytes':sum(r['game_max'] for r in resources),
        'repeated_requests':sum(r['calls']-1 for r in resources),
        'memory':{k:last.get(k) for k in ('normal_heap_total','normal_heap_used','normal_heap_free','normal_heap_peak','linear_total','linear_used','linear_free','linear_min','texture_bytes','psx_ram_bytes','psx_vram_bytes','renderer_vertex_bytes','renderer_color_bytes','renderer_depth_stencil_bytes','psx_surface_color_vram','psx_surface_stencil_vram','presentation_vertices_linear','resource_cache_bytes','resource_cache_peak_bytes','resource_cache_budget')},
        'cache':{k:v for k,v in last.items() if k.startswith(('resource_cache_','resource_preload_','resource_common_'))}}
if 'before' in result['runs'] and 'after' in result['runs']:
    pairs=[]
    for i in sorted({int(e['file']) for e in result['runs']['before']['requests']}):
        a=[e for e in result['runs']['before']['requests'] if e['file']==i]
        b=[e for e in result['runs']['after']['requests'] if e['file']==i]
        if not a or not b:continue
        assert len({(e['lba'],e['requested']) for e in a+b})==1
        pairs.append({'file':i,'name':names[i],'lba':int(a[0]['lba']),'requested':int(a[0]['requested']),
            'before_ms':summary([e['ms'] for e in a]),'after_ms':summary([e['ms'] for e in b]),
            'before_raw_reads':sum(e['reads'] for e in a),'after_raw_reads':sum(e['reads'] for e in b)})
    result['identical_request_pairs']=pairs
out=p/'reports/stage5-final-performance.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:{f:v[f] for f in ('directory','build','profile','route_laps','unique_resource_bytes','gameplay_unique_bytes','repeated_requests','groups')} for k,v in result['runs'].items()},indent=2))
