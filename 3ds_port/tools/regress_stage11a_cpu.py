"""Existing ARM regressions, isolated outputs and disposable cards. Never hardware acceptance."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
DEST=PORT/'build/stage11a-cpu-regression';DEST.mkdir(exist_ok=True)
REPORTS=PORT/'reports/stage11a-cpu-regression';REPORTS.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
CASES=[('boot','run_arm_game.py',None,{}),('gpu','test_game_gpu_arm.py',None,{}),
 ('packet','test_stage10_packet_arm.py',None,{}),('status','test_stage10_status_arm.py',None,{}),
 ('transition','test_stage10_transition_arm.py',None,{}),('particle','test_stage10_particle_arm.py',None,{}),
 ('polyline','test_stage10_polyline_arm.py',None,{}),('lens','test_stage10_lens_arm.py',None,{}),
 ('modern','test_stage10_modern_arm.py',None,{}),('pause','test_stage10_original_pause_arm.py',None,{}),
 ('menu_mapping','test_menu_mapping_arm.py',None,{}),('inventory','test_stage7_inventory_arm.py',3,{}),
 ('load_town','test_stage10_saved_load_runtime.py',None,{'SH_PROGRESS_SCOPE':'town'}),
 ('load_school','test_stage10_saved_load_runtime.py',None,{'SH_PROGRESS_SCOPE':'school'}),
 ('cafe','test_stage10_cafe_runtime_arm.py',1,{}),
 ('reload','test_stage10_reload_runtime.py',3,{}),('quick_reload','test_stage10_r6_quick_reload.py',3,{})]
if len(sys.argv)>1 and sys.argv[1]!='--resume':
 name,filename,scene,env=next(c for c in CASES if c[0]==sys.argv[1]);os.environ.update(env)
 os.environ['SH_GAME_ELF']=str(PORT/('build/stage11a-cpu-probe-'+str(scene)+'/probe.elf' if scene else 'build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf'))
 os.environ['SH_STAGE9_REGRESSION']='1'
 # Existing input artifacts remain read-only. Output probes get a private path;
 # reports are redirected even when the fixture executes another fixture.
 read_text,write_text,write_bytes=Path.read_text,Path.write_text,Path.write_bytes
 def redirect(path):
  try:return REPORTS/path.relative_to(PORT/'reports')
  except ValueError:return path
 def read(path,*a,**kw):
  value=read_text(path,*a,**kw)
  if path.parent==PORT/'tools':
   value=value.replace("p/'build/","p/'build/stage11a-cpu-regression/").replace("p/'build'","p/'build/stage11a-cpu-regression'")
   value=value.replace("str(p/'silenthill_game.elf')","os.environ['SH_GAME_ELF']")
   if path.name=='test_stage10_cafe_runtime_arm.py':
    value=value.replace('super().__init__();self.game_ticks=0;self.halt_packet=None',
      "super().__init__();self.game_ticks=0;self.halt_packet=None;self.map=None;self.bridge('game3ds_map_observe',self.map_observe)")
    value=value.replace('    def tick(self,*_):','    def map_observe(self,map,*_):self.map=map;self.ret()\n    def tick(self,*_):')
    value+='\nassert r.map==1, ("Expected Cafe",r.map)\n'
  return value
 def write(path,data,*a,**kw):
  target=redirect(path);target.parent.mkdir(parents=True,exist_ok=True);return write_text(target,data,*a,**kw)
 def write_b(path,data,*a,**kw):
  target=redirect(path);target.parent.mkdir(parents=True,exist_ok=True);return write_bytes(target,data,*a,**kw)
 Path.read_text=read;Path.write_text=write;Path.write_bytes=write_b
 for folder in ('stage10-r5-progression-town','stage10-r5-progression-school','stage10-r5-road-school'):
  source=PORT/'build'/folder/'memcard.mcr';dest=DEST/folder/'memcard.mcr'
  if source.exists():dest.parent.mkdir(exist_ok=True);shutil.copyfile(source,dest)
 fixture=PORT/'tools'/filename
 exec(compile(fixture.read_text(),str(fixture),'exec'),{'__file__':str(fixture),'__name__':'__main__','Path':Path})
 write_text(REPORTS/(name+'.proof.json'),json.dumps(dict(case=name,status='PASS',internal_scene=scene,
   elf_sha256=hashlib.sha256((PORT/'build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf').read_bytes()).hexdigest()),indent=2)+'\n')
 raise SystemExit
golden=ROOT/'sh1_data/memcard.mcr';before=hashlib.sha256(golden.read_bytes()).hexdigest();cases=[]
prior={}
if '--resume' in sys.argv:
 previous=json.loads((PORT/'reports/stage11a-cpu-regression.json').read_text())
 assert previous['elf_sha256']==hashlib.sha256((PORT/'build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf').read_bytes()).hexdigest()
 prior={c['case']:c for c in previous['cases']}
for name,filename,scene,env in CASES:
 if name in prior and prior[name]['status']=='PASS':cases.append(prior[name]);continue
 proof=REPORTS/(name+'.proof.json')
 if '--resume' in sys.argv and proof.exists():
  trial=json.loads(proof.read_text())
  if trial['elf_sha256']==previous['elf_sha256'] and trial['internal_scene']==scene and trial['status']=='PASS':
   cases.append(dict(case=name,status='PASS',exit=0,internal_scene=scene,verified_retry=str(proof)));continue
 start=time.monotonic();run=subprocess.run([sys.executable,str(Path(__file__).resolve()),name],capture_output=True,text=True,timeout=1200)
 (REPORTS/(name+'.stdout.txt')).write_text(run.stdout);(REPORTS/(name+'.stderr.txt')).write_text(run.stderr)
 row=dict(case=name,status='PASS' if run.returncode==0 else 'FAIL',exit=run.returncode,seconds=round(time.monotonic()-start,3),internal_scene=scene)
 cases.append(row);print(json.dumps(row),flush=True)
 report=dict(scope=__doc__,cases=cases,elf_sha256=hashlib.sha256((PORT/'build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf').read_bytes()).hexdigest(),golden_card_unchanged=hashlib.sha256(golden.read_bytes()).hexdigest()==before,hardware_accepted=False)
 (PORT/'reports/stage11a-cpu-regression.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(c['status']=='PASS' for c in cases),cases
assert hashlib.sha256(golden.read_bytes()).hexdigest()==before
report=dict(status='PASS',scope=__doc__,cases=cases,
 elf_sha256=hashlib.sha256((PORT/'build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf').read_bytes()).hexdigest(),
 golden_card_unchanged=True,golden_card_sha256=before,hardware_accepted=False)
(PORT/'reports/stage11a-cpu-regression.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status='PASS',groups=len(cases))),flush=True)
