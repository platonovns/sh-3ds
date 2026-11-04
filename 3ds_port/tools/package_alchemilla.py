"""Seal Alchemilla's own diff and hash-verified offline inputs; never promote."""
from pathlib import Path
import hashlib,json,os,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2];PORT=ROOT/'3ds_port'
BUILD=PORT/'build/alchemilla';OUT=ROOT.parent/'alchemilla-checkpoints/20261028'
BASE='2782aeb20';SCHOOL_BASE='6679d655a';SCHOOL='65ab73346'
POST_BASE='44997c1f3';POST='6ae58172b';FMV_BASE='518c44a9e';FMV='e94a90a6b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
git_prefix=['git','-C',str(ROOT)]
if os.name!='nt' and (ROOT/'.git').is_file():
    directory=(ROOT/'.git').read_text().removeprefix('gitdir:').strip()
    if re.match(r'^[A-Za-z]:/',directory):
        directory=subprocess.check_output(['wslpath','-u',directory],text=True).strip()
        git_prefix=['git','--git-dir='+directory,'--work-tree='+str(ROOT)]
def git(*args):return subprocess.check_output([*git_prefix,*args],cwd=ROOT)
def changed(a,b):return git('diff','--name-only',a,b).decode().splitlines()
build=read(BUILD/'manifest.json')
reports={n:read(PORT/'reports'/('alchemilla-'+n+'.json')) for n in ('arm','actors-arm','runtime-arm','closure')}
assert build['status']=='PASS' and all(r['status']=='PASS' for r in reports.values())
assert reports['actors-arm']['full_game_checks']=='PASS'
assert all(r['elf_sha256']==build['elf_sha256'] for r in reports.values())
assert sha(BUILD/'alchemilla-content.elf')==build['elf_sha256']
assert not list(BUILD.rglob('*.3dsx'))
assert all(sha(ROOT/n)==h for n,h in build['sources'].items())
assert all(sha(ROOT/n)==h for n,h in build['linked_objects'].items())
assert not git('diff','--name-only','HEAD').decode().strip(),'Commit content before sealing'
paths=changed(BASE,'HEAD');assert paths
for name in paths:
    assert not any(name.startswith('3ds_port/source/'+stem) for stem in
        ('render_3ds','game_gpu','game_texture','game_gte','game_spu','game_xa','game_cpu','stage11a','main_game'))
    assert not name.startswith('src/screens/stream')
original=ROOT.parent/'silent-hill-decomp';live_changes=[]
for name in paths:
    p=original/name
    if not p.is_file():continue
    old=subprocess.run([*git_prefix,'show',SCHOOL_BASE+':'+name],capture_output=True,cwd=ROOT)
    if old.returncode==0 and old.stdout.replace(b'\r\n',b'\n')!=p.read_bytes().replace(b'\r\n',b'\n'):
        live_changes.append(name)
OUT.mkdir(parents=True,exist_ok=True)
patch=OUT/'content.patch';assert not patch.exists(),'Never overwrite a sealed checkpoint'
patch.write_bytes(git('diff','--binary',BASE,'HEAD'))
subprocess.run([*git_prefix,'apply','--reverse','--check',str(patch)],cwd=ROOT,check=True)
files={ROOT/n for n in build['sources']}
files.update(ROOT/n for n in build['linked_objects'])
files.update(ROOT/n for n in paths)
files.update([BUILD/'manifest.json',BUILD/'alchemilla-content.elf',BUILD/'alchemilla.map',BUILD/'symbols.txt',
    PORT/'build-game/flags',PORT/'build/stage11a-cpu-B/manifest.json',PORT/'build/stage11a-cpu-B/main_game.c',
    PORT/'build/school-completion/manifest.json',PORT/'build/post-school/manifest.json',PORT/'native_map_data.ld',
    BUILD/'alchemilla_identity.h',BUILD/'main_game.c'])
files.update(PORT/'build-game'/(n+'.native.ld') for n in ('map0_s01','map2_s00','map0_s02','map1_s00'))
files.update(PORT/'build/school-completion'/(f'map1_s{i:02}.native.ld') for i in range(1,7))
files.update(PORT/'build/post-school'/(n+'.native.ld') for n in ('map2_s01','map2_s02','map2_s04'))
files.update(BUILD.glob('*.native.ld'));files.update(BUILD.rglob('*.log'))
inventory={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)}
for name in inventory:
    assert not name.startswith(('sh1_data/','assets/','asm/')),name
    assert Path(name).suffix.lower() not in ('.bin','.cue','.3dsx','.sav','.mcr'),name
graph=read(PORT/'reports/alchemilla-content-graph.json')
report=dict(status='INTEGRATION_READY_OFFLINE_CHECKPOINT',branch=git('branch','--show-current').decode().strip(),
    content_commit=git('rev-parse','HEAD').decode().strip(),patch_base_commit=git('rev-parse',BASE).decode().strip(),
    source_id=build['build'],accepted_cpu_base=build['accepted_cpu_base'],post_school_dependency=build['base'],
    internal_elf_sha256=build['elf_sha256'],hardware_candidate_created=False,hardware_accepted=False,published=False,
    start='MAP2_S02 normal post-drawbridge control; hospital entry event19 uses source S02 point19',
    end='MAP3_S06 original exit event8 to MAP2_S02 using S06 point1; stable control before Antique Shop',
    maps_added=build['maps'],maps_reused=['map2_s02','map2_s04'],content_events_added=485,
    fmv_dependency=build['fmv_dependency'],validation_reports={n:'3ds_port/reports/alchemilla-'+n+'.json' for n in reports},
    files_changed=paths,overlap_school=sorted(set(paths)&set(changed(SCHOOL_BASE,SCHOOL))),
    overlap_post_school=sorted(set(paths)&set(changed(POST_BASE,POST))),
    overlap_native_fmv=sorted(set(paths)&set(changed(FMV_BASE,FMV))),
    active_stage11b_changed_paths_vs_frozen_B=sorted(live_changes),
    likely_stage11b_overlap=sorted(set(live_changes)|set(paths)&{
        '3ds_port/Makefile.game','3ds_port/source/game_map.c','3ds_port/source/game_native.c',
        '3ds_port/tools/build_identity.py','3ds_port/tools/native_overlay.py'}),
    stage11b_overlap_method='Read-only normalized source comparison at sealing time plus build/dispatch integration paths',
    unresolved=['Continuous hardware playthrough, graphics/audio/performance deferred to combined accepted Stage 11B',
        'Original FMV API preserved; Native-FMV e94a90a6b required for playback',
        'MAP4 Antique Shop is intentionally outside checkpoint'],
    patch_sha256=sha(patch),snapshot_files=len(inventory),reverse_patch_check='PASS',
    scope='Original Alchemilla content and minimal native ABI compatibility; no renderer/audio architecture changes')
receipt=OUT/'checkpoint.json';receipt.write_text(json.dumps(report,indent=2)+'\n')
archive=OUT/'alchemilla-checkpoint.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in inventory:z.write(ROOT/name,'snapshot/'+name)
    z.write(patch,'content.patch');z.write(receipt,'checkpoint.json')
    z.writestr('inventory.json',json.dumps(inventory,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for name,row in inventory.items():
        data=z.read('snapshot/'+name)
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],name
report.update(archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),archive_byte_verification='PASS')
(PORT/'reports/alchemilla-checkpoint.json').write_text(json.dumps(report,indent=2)+'\n')
archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
print(json.dumps(report,indent=2))
