"""Create a Block 5 offline checkpoint only after the recorded checks pass."""
from pathlib import Path
import hashlib,json,os,re,subprocess,tempfile,zipfile
root=Path(__file__).resolve().parents[2];port=root/'3ds_port';build=port/'build/resort-probe'
base='9e02278c28d49d9e0043c9990334fc70e042edb0';out=root.parent/'resort-boat-checkpoints/20261028'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
git=['git','-C',str(root)]
if os.name!='nt' and (root/'.git').is_file():
 d=(root/'.git').read_text().removeprefix('gitdir:').strip()
 if re.match(r'^[A-Za-z]:/',d):d=subprocess.check_output(['wslpath','-u',d],text=True).strip()
 git=['git','--git-dir='+d,'--work-tree='+str(root)]
def run(*args):return subprocess.check_output([*git,*args],cwd=root)
m=read(build/'build-manifest.json');elf=build/'resort-probe.elf'
assert sha(elf)==m['elf_sha256'] and all(sha(root/n)==h for n,h in m['sources'].items())
assert m['base']=='sewer1-content-src-021e998524bc2f2c'
logs={n:(build/(n+'.log')).read_text() for n in ('tables','callbacks','components')}
for s in ('errors: []','AI dispatch tables PASS','Air Screamer animation callbacks PASS'):assert s in logs['tables']
for n in ('map5_s02','map5_s03','map6_s00','map6_s01'):
 assert n+' header and event callbacks' in logs['callbacks']
 assert n+' retail and native event function targets PASS' in logs['tables']
for s in ('save roundtrip 7 PASS','map5_s03 declined pickup 115 PASS','motorcycle ending flag 391; key retained PASS','Indian Runner code 473 accepted','Groaner damage/death 1','Romper damage/death 1','Stalker damage 1'):assert s in logs['components']
runtime=read(build/'runtime-resort-bar-indian_runner-motel_intermediate-motel_completed-lake_skipped-boat_end.json')
assert runtime['elf_sha256']==m['elf_sha256']
expected=['resort','bar','indian_runner','motel_intermediate','motel_completed','lake_skipped','boat_end']
assert [r['label'] for r in runtime['results']]==expected
assert all(not r['failure'] and not r['invalid'] and not r['exception'] and r['update_calls']>=21 for r in runtime['results'])
end=runtime['results'][-1];assert end['control_ticks']>=60 and end['walk_start']!=end['walk_end']
boat=read(build/'boat-skip.json');assert boat['elf_sha256']==m['elf_sha256'] and boat['stable']>=21 and 0 in boat['steps'] and 55 in boat['steps']
lake=read(build/'lake-skip.json');assert lake['elf_sha256']==m['elf_sha256'] and lake['stable']>=21 and 0 in lake['steps'] and 20 in lake['steps']
actual=read(build/'boat-advance-dialogue-fast.json');assert actual['elf_sha256']==m['elf_sha256']
full=read(build/'boat-mock-dialogue-fast.json');assert full['elf_sha256']==m['elf_sha256'] and full['stable']>=21 and 19 in full['steps'] and 55 in full['steps']
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
unresolved=subprocess.check_output([prefix+'nm','-u',str(elf)],text=True);assert all(x.split()[0]=='w' for x in unresolved.splitlines() if x.split())
size=subprocess.check_output([prefix+'size',str(root.parent/'sewer1-content/3ds_port/build/sewer1-compile-probe/sewer1-probe.elf'),str(elf)],text=True).splitlines();before=list(map(int,size[1].split()[:3]));after=list(map(int,size[2].split()[:3]))
assert not run('diff','--name-only','HEAD').strip() and not run('diff','--cached','--name-only').strip()
assert run('branch','--show-current').decode().strip()=='codex/resort-boat-content'
commit=run('rev-parse','HEAD').decode().strip();paths=run('diff','--name-only',base,commit).decode().splitlines();assert paths
for n in paths:
 assert Path(n).suffix.lower() not in ('.bin','.cue','.3dsx','.elf','.o','.sav','.mcr')
 assert not n.startswith(('sh1_data/','assets/','pc_port/build_gen/extracted_data/','3ds_port/source/render_','3ds_port/source/game_gpu','3ds_port/source/game_texture','3ds_port/source/game_gte','3ds_port/source/game_spu'))
out.mkdir(parents=True,exist_ok=True);patch=out/'content.patch';archive=out/'block5-checkpoint.zip';assert not patch.exists() and not archive.exists()
patchbytes=run('diff','--binary',base,commit)
with tempfile.NamedTemporaryFile(dir=out,delete=False) as f:f.write(patchbytes);tmp=Path(f.name)
try:subprocess.run([*git,'apply','--reverse','--check',str(tmp)],cwd=root,check=True)
finally:tmp.unlink()
receipt=dict(status='OFFLINE_CHECKPOINT',branch='codex/resort-boat-content',commit=commit,base=base,source_id=m['source_id'],elf_sha256=m['elf_sha256'],patch_sha256=hashlib.sha256(patchbytes).hexdigest(),hardware_candidate=False,published=False,hardware_accepted=False,files=paths,weak_unresolved=unresolved.splitlines(),sections_baseline=before,sections_current=after,sections_growth=[b-a for a,b in zip(before,after)],limitations='Fixtures seed nearby states. Boat full callback run accelerates time and simulates text completion; skip and movement checks use original game updates. The unmocked dialog run reached step 10 and timed out; audio and visual hardware acceptance remain outstanding.')
inventory={}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 def add(name,data):
  inventory[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest());info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data,compresslevel=6)
 add('content.patch',patchbytes);add('checkpoint.json',(json.dumps(receipt,indent=2)+'\n').encode());add('build-manifest.json',(json.dumps(m,indent=2)+'\n').encode())
 for n,v in logs.items():add('validation/'+n+'.log',v.encode())
 for n,v in [('runtime',runtime),('boat-skip',boat),('lake-skip',lake),('boat-mock-dialogue-fast',full),('boat-advance-dialogue-fast',actual)]:
  v=json.loads(json.dumps(v))
  for row in v.get('results',[]):row.pop('last_packets',None)
  if 'result' in v:v['result'].pop('last_packets',None)
  add('validation/'+n+'.json',(json.dumps(v,indent=2)+'\n').encode())
 for n in paths:
  p=root/n
  if p.is_file():add('changed-source/'+n,p.read_bytes())
 z.writestr('inventory.json',json.dumps(inventory,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for n,v in inventory.items():
  data=z.read(n);assert len(data)==v['bytes'] and hashlib.sha256(data).hexdigest()==v['sha256']
 assert all(Path(n).suffix.lower() not in ('.bin','.cue','.3dsx','.elf','.o','.sav','.mcr') for n in z.namelist())
patch.write_bytes(patchbytes);(out/'content.patch.sha256').write_text(receipt['patch_sha256']+'  '+patch.name+'\n');digest=sha(archive);(out/'block5-checkpoint.zip.sha256').write_text(digest+'  '+archive.name+'\n');(out/'checkpoint.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(receipt,archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=digest),indent=2))
