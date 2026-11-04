"""Seeded real-BIN map updates for Resort/Boat; not a continuous playthrough."""
from pathlib import Path
import os,sys,struct,json,hashlib
port=Path(__file__).resolve().parents[1]
elf=port/'build/resort-probe/resort-probe.elf'
os.environ['SH_BLOCK3_ELF']=str(elf)
exec((port/'tools/test_block3_runtime.py').read_text().split('\ncases = [',1)[0])
class ResortEntry(Entry):
    def place(self,uc,*_):
        if not self.placed:
            self.placed=True
            uc.reg_write(UC_ARM_REG_R0,game.symbols[self.pose_map+'_MAP_POINTS']+self.point*12)
cases=[('resort',30,'map5_s00',31,(350,352,193,355,353,1371,354,1391,358)),('bar',31,'map5_s01',8,(350,352,193,355,358,378)),('indian_runner',31,'map5_s01',10,(350,352,193,355,358,371,379,380)),('motel',32,'map5_s01',16,(350,352,193,355,358,379,380,1377)),('motel_intermediate',32,'map5_s01',16,(350,352,193,355,358,379,380,394,386,389)),('motel_completed',32,'map5_s01',16,(350,352,193,355,358,379,380,394,386,389,390,391)),('lake_skipped',33,'map5_s01',24,(350,352,193,355,358,402,403)),('boat',34,'map6_s00',4,(350,352,193,355,358,402,403,423)),('boat_end',34,'map6_s00',4,(350,352,193,355,358,402,403,423,424))]
if len(sys.argv)>1:cases=[c for c in cases if c[0] in sys.argv[1:]]
results=[]
for label,wanted,pose,point,flags in cases:
    r=ResortEntry(wanted,pose,point,flags,require_control=label=='boat_end',walk=label=='boat_end')
    result=game.run(r,seconds=180)
    result.update(label=label,map=wanted,room=r.room,observed_map=r.map,update_calls=r.ticks,control_ticks=r.ready,walk_start=r.walk_start,walk_end=r.walk_end)
    results.append(result);print(json.dumps(result,indent=2),flush=True)
    if result['failure'] or result['invalid'] or result['exception'] or r.ticks<21:break
(elf.parent/('runtime-'+('-'.join(sys.argv[1:]) if len(sys.argv)>1 else 'all')+'.json')).write_text(json.dumps({'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'results':results},indent=2)+'\n')
print('fixtures run:',len(results),'/',len(cases),flush=True)
if len(results)!=len(cases) or any(x['failure'] or x['invalid'] or x['exception'] or x['update_calls']<21 or (x['label']=='boat_end' and (x['control_ticks']<60 or not x['walk_start'] or x['walk_start']==x['walk_end'])) for x in results):raise SystemExit(1)
