"""Audit R5 evidence with exact ELF/diagnostic identities; never hardware acceptance."""
import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
def read(name):return json.loads((p/'reports'/name).read_text(encoding='utf-8-sig'))
def sha(file):return hashlib.sha256(file.read_bytes()).hexdigest()
def status(folder):return dict(line.split('=',1) for line in (p/'reports'/folder/'status.txt').read_text().splitlines() if '=' in line)
elfsha=sha(p/'silenthill_game.elf')
foundation=read('stage10-foundation-regressions.json')
assert foundation['status']=='PASS' and foundation['elf_sha256']==elfsha
assert len(foundation['tests'])==31 and all(t['status']=='PASS' for t in foundation['tests'])
air=read('stage10-r5-air-directions.json')
assert air['status']=='PASS' and air['diagnostic']['base_elf_sha256']==elfsha
assert len(air['cases'])==3 and all(r['health_before']>r['health_min']>0 for r in air['cases'])
mips=read('stage10-r5-air-state-comparison.json')
assert mips['status']=='PASS' and mips['elf_sha256']==elfsha and len(mips['cases'])==20
controls=read('stage10-r5-control-runtime.json')
variant=json.loads((p/'build/stage10-dev-scene-5/manifest.json').read_text())
assert variant['base_elf_sha256']==elfsha and variant['elf_sha256']==controls['elf_sha256']
assert len(controls['cases'])==10 and all(r['alignment']>.9 and r['updates']==75 and not r['error'] and not r['failure'] and not r['invalid'] for r in controls['cases'])
road=read('stage10-r5-road-school.json');town=read('stage10-r5-progression-town.json')
assert road['status']==town['status']=='PASS'
last=road['completed'][-1]['save']
assert last['map']==3 and last['room']==9 and last['location']==4 and all(last['route_flags'])
loaded=read('stage10-r5-loaded-road-school.json')
assert loaded['status']=='PASS' and loaded['elf_sha256']==elfsha and loaded['loaded_gameplay_updates']>=20
assert loaded['final']['map']==3 and loaded['final']['room']==9 and loaded['final']['location']==4
pica=[]
for label,mapidx,room,folder in [('school',3,14,'stage10-dev-scene-7-world'),
    ('interiors',2,2,'stage10-dev-scene-9-world'),('infirmary',3,9,'stage10-dev-scene-7-world-infirmary'),
    ('cafe',10,3,'stage10-dev-scene-6-exit')]:
    s=status('stage10-r5-'+label+'-pica');v=json.loads((p/'build'/folder/'manifest.json').read_text())
    run=read('stage10-r5-'+label+'-pica/run.json')
    assert v['base_elf_sha256']==elfsha and v['build']==s['build'] and v['sha256']==run['build_sha256']
    assert s['checkpoint']=='EXIT' and s['first_failure']=='0' and s['report_complete']=='1'
    assert int(s['map_idx'])==mapidx and int(s['map_room'])==room
    assert s['readback_direct_mismatches']==s['gpu_duplicate_presents']=='0'
    assert int(s['map_frames'])>=120 and int(s['packet_peak'])<int(s['packet_capacity'])
    pica.append(dict(scene=label,diagnostic=v,map=mapidx,room=room,map_frames=int(s['map_frames']),
        packet_peak=int(s['packet_peak']),direct_mismatches=0,duplicate_presents=0))
cafe=status('stage10-r5-cafe-pica')
rows=[list(map(int,v.split(','))) for k,v in cafe.items() if k.startswith('fade_present_')]
assert rows and all(len(row)==10 for row in rows)
fade=dict(scope='Azahar cadence evidence; New 3DS smoothness pending',rows=len(rows),
    columns=['sim_tick','present','vblank','q12_clock','fade_state','progress','snapshot_generation','modulation','sim_dt','native_parts'],
    sampling='Only fade/feedback-active presentations are recorded; gaps can contain ordinary gameplay',
    recorded_simulation_steps=sorted(set(rows[i][0]-rows[i-1][0] for i in range(1,len(rows)))),
    recorded_logical_present_steps=sorted(set(rows[i][1]-rows[i-1][1] for i in range(1,len(rows)))),
    matching_simulation_presentation_deltas=all(rows[i][0]-rows[i-1][0]==rows[i][1]-rows[i-1][1] for i in range(1,len(rows))),
    snapshot_steps=sorted(set(rows[i][6]-rows[i-1][6] for i in range(1,len(rows)))),
    vblank_intervals=sorted(set(rows[i][2]-rows[i-1][2] for i in range(1,len(rows)))),
    modulation=sorted(set(r[7] for r in rows)),hardware_accepted=False)
(p/'reports/stage10-r5-fade-cadence.json').write_text(json.dumps(fade,indent=2)+'\n')
card=sha(root/'sh1_data/memcard.mcr');assert card=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
renderer=sha(p/'build-game/render_3ds.o');assert renderer=='2651e36fe37932734a97d7953997b48eb0bb6d5a1f946a0abcdcc431d75882ed'
report=dict(status='PASS',normal_elf_sha256=elfsha,foundation_tests=31,air_directions=air['cases'],mips_cases=20,
    movement_cases=10,pica=pica,original_progression_and_school_save_load=True,
    progression_scope='Original pickups, keys, locks, doors, darkness, school and save/load; nearby hops replace long walks. Not a continuous route or hardware acceptance.',
    progression_elf_sha256=road['elf_sha256'],town_elf_sha256=town['elf_sha256'],
    final_normal_load_elf_sha256=loaded['elf_sha256'],memory_card_unchanged=True,card_sha256=card,
    accepted_renderer_object_unchanged=True,renderer_sha256=renderer,hardware_accepted=False,stage10_complete=False)
(p/'reports/stage10-r5-runtime-qualification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
