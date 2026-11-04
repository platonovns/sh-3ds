"""Seal only after the committed content and same-ELF offline evidence pass."""
from pathlib import Path
import hashlib, json, os, re, subprocess, tempfile, zipfile

root=Path(__file__).resolve().parents[2]; port=root/'3ds_port'; build=port/'build/sewer1-compile-probe'
output=root.parent/'sewer1-checkpoints/20261028'; base='0ba6376979fcd5dcf021713a42f28c5d18472cd6'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
git=['git','-C',str(root)]
if os.name!='nt' and (root/'.git').is_file():
    directory=(root/'.git').read_text().removeprefix('gitdir:').strip()
    if re.match(r'^[A-Za-z]:/',directory): directory=subprocess.check_output(['wslpath','-u',directory],text=True).strip()
    git=['git','--git-dir='+directory,'--work-tree='+str(root)]
def run(*args):return subprocess.check_output([*git,*args],cwd=root)
manifest=read(build/'build-manifest.json'); elf=build/'sewer1-probe.elf'
assert sha(elf)==manifest['elf_sha256']
assert all(sha(root/name)==digest for name,digest in manifest['sources'].items())
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
unresolved=subprocess.check_output([prefix+'nm','-u',str(elf)],text=True)
assert all(line.split()[0]=='w' for line in unresolved.splitlines() if line.split()),unresolved
size_out=subprocess.check_output([prefix+'size',str(root.parent/'otherworld-central-content/3ds_port/build/block3/block3-content.elf'),str(elf)],text=True).splitlines()
baseline=list(map(int,size_out[1].split()[:3]));current=list(map(int,size_out[2].split()[:3]))
reports={'tables':read(build/'sewer1-tables.json'),'components':read(build/'sewer1-components.json')}
labels=('waterworks','sewer_entry','early','mid_key','hanged','creeper','exit','resort')
for label in labels: reports['runtime-'+label]=read(build/('runtime-'+label+'.json'))
assert all(x['status']=='PASS' and x['elf_sha256']==manifest['elf_sha256'] for x in reports.values())
assert all(len(reports['runtime-'+label]['results'])==1 and reports['runtime-'+label]['results'][0]['label']==label for label in labels)
cases={x['case'] for x in reports['components']['checks']}
assert {'header_and_event_callbacks','inventory_use_and_consume','wrong_location','sewer_key_pickup','sewer_key_declined','sewer_exit_key_pickup','ladder_completion','save_checksum_roundtrip','hanged_damage','creeper_damage_and_death','enemy_animation_reload','enemy_attack_and_collision_dispatch'} <= cases
assert reports['runtime-hanged']['results'][0]['hanged_updates']>0
assert reports['runtime-creeper']['results'][0]['creeper_updates']>0
assert reports['runtime-resort']['results'][0]['control_ticks']>=60
assert not run('diff','--name-only','HEAD').strip() and not run('diff','--cached','--name-only').strip()
assert run('branch','--show-current').decode().strip()=='codex/sewer1-content'
commit=run('rev-parse','HEAD').decode().strip(); paths=run('diff','--name-only',base,commit).decode().splitlines()
assert paths
for name in paths:
    assert Path(name).suffix.lower() not in ('.bin','.cue','.3dsx','.elf','.o','.sav','.mcr')
    assert not name.startswith(('sh1_data/','assets/','pc_port/build_gen/extracted_data/','3ds_port/source/render_',
                                '3ds_port/source/game_gpu','3ds_port/source/game_texture','3ds_port/source/game_gte','3ds_port/source/game_spu'))
output.mkdir(parents=True,exist_ok=True)
patch=output/'content.patch'; archive=output/'block4-checkpoint.zip'
assert not patch.exists() and not archive.exists(),'Sealed output already exists'
patch_bytes=run('diff','--binary',base,commit)
with tempfile.NamedTemporaryFile(dir=output,delete=False) as f: f.write(patch_bytes); tmp=Path(f.name)
try: subprocess.run([*git,'apply','--reverse','--check',str(tmp)],cwd=root,check=True)
finally: tmp.unlink()
receipt=dict(status='OFFLINE_CHECKPOINT',branch='codex/sewer1-content',commit=commit,base=base,
    source_id=manifest['source_id'],elf_sha256=manifest['elf_sha256'],patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
    hardware_candidate=False,published=False,hardware_accepted=False,files=paths,
    weak_unresolved=unresolved.splitlines(),sections_baseline=baseline,sections_current=current,
    sections_growth=[b-a for a,b in zip(baseline,current)])
inventory={}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    def add(name,data):
        inventory[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        z.writestr(info,data,compresslevel=6)
    add('content.patch',patch_bytes);add('checkpoint.json',(json.dumps(receipt,indent=2)+'\n').encode())
    add('build-manifest.json',(json.dumps(manifest,indent=2)+'\n').encode())
    for name,report in reports.items():
        for row in report.get('results',[]):row.pop('last_packets',None)
        add('validation/'+name+'.json',(json.dumps(report,indent=2)+'\n').encode())
    for name in paths:
        p=root/name
        if p.is_file():add('changed-source/'+name,p.read_bytes())
    z.writestr('inventory.json',json.dumps(inventory,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for name,row in inventory.items():
        data=z.read(name);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
    assert all(Path(name).suffix.lower() not in ('.bin','.cue','.3dsx','.elf','.o','.sav','.mcr') for name in z.namelist())
patch.write_bytes(patch_bytes);digest=sha(archive)
(output/'block4-checkpoint.zip.sha256').write_text(digest+'  '+archive.name+'\n')
(output/'checkpoint.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(receipt,archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=digest),indent=2))
