"""Seal an isolated, reproducible source/content checkpoint without promotion."""
from pathlib import Path
import hashlib,json,os,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2];PORT=ROOT/'3ds_port'
BUILD=PORT/'build/post-school';OUT=ROOT.parent/'post-school-checkpoints/20261028'
BASE='44997c1f3';SCHOOL_BASE='6679d655a';FMV_BASE='518c44a9e';FMV='e94a90a6b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
git_prefix=['git','-C',str(ROOT)]
# A worktree created by Windows Git records an absolute C:/ gitdir. Linux Git
# cannot parse that .git indirection; explicit directories preserve both hosts'
# metadata unchanged and avoid changing the active Stage 11B repository.
if os.name!='nt' and (ROOT/'.git').is_file():
    directory=(ROOT/'.git').read_text().removeprefix('gitdir:').strip()
    if re.match(r'^[A-Za-z]:/',directory):
        directory=subprocess.check_output(['wslpath','-u',directory],text=True).strip()
        git_prefix=['git','--git-dir='+directory,'--work-tree='+str(ROOT)]
def git(*args):return subprocess.check_output([*git_prefix,*args],cwd=ROOT)
def changed(a,b):return git('diff','--name-only',a,b).decode().splitlines()
build=read(BUILD/'manifest.json');arm=read(PORT/'reports/post-school-arm.json')
runtime=read(PORT/'reports/post-school-runtime-arm.json')
assert build['status']==arm['status']==runtime['status']=='PASS'
assert build['elf_sha256']==arm['elf_sha256']==runtime['elf_sha256']==sha(BUILD/'post-school-content.elf')
assert not list(BUILD.rglob('*.3dsx'))
assert all(sha(ROOT/n)==h for n,h in build['sources'].items())
assert all(sha(ROOT/n)==h for n,h in build['linked_objects'].items())
paths=changed(BASE,'HEAD');assert paths
assert not any(n.startswith('3ds_port/source/'+stem) for n in paths
    for stem in ('render_3ds','game_gpu','game_texture','game_gte','game_spu','game_xa','game_cpu','stage11a','main_game'))
assert not any(n.startswith('src/screens/stream') for n in paths)
assert not git('diff','--name-only','HEAD').decode().strip(),'Commit content before sealing'
overlap_school=sorted(set(paths)&set(changed(SCHOOL_BASE,BASE)))
overlap_fmv=sorted(set(paths)&set(changed(FMV_BASE,FMV)))
original=ROOT.parent/'silent-hill-decomp'
live_changes=[]
for name in paths:
    p=original/name
    if not p.is_file():continue
    old=subprocess.run([*git_prefix,'show',SCHOOL_BASE+':'+name],capture_output=True,cwd=ROOT)
    if old.returncode==0 and old.stdout.replace(b'\r\n',b'\n')!=p.read_bytes().replace(b'\r\n',b'\n'):
        live_changes.append(name)
frozen=original/'3ds_port/baselines/stage11a-hardware-accepted-20261028.zip'
assert sha(frozen)=='0007523284e2c5a57fbf9bb4104d498e5f7baa7b4de409a6e1916ee87b6f20a5'
OUT.mkdir(parents=True,exist_ok=True)
patch=OUT/'content.patch';assert not patch.exists(),'Never replace a sealed checkpoint'
patch.write_bytes(git('diff','--binary',BASE,'HEAD'))
files={ROOT/n for n in build['sources']}
files.update(ROOT/n for n in build['linked_objects'])
files.update(ROOT/n for n in build['school_objects'])
files.update(ROOT/n for n in paths)
files.update([BUILD/'manifest.json',BUILD/'post-school-content.elf',BUILD/'post-school.map',BUILD/'symbols.txt',
    PORT/'build-game/flags',PORT/'build/stage11a-cpu-B/manifest.json',PORT/'build/stage11a-cpu-B/main_game.c',
    PORT/'build/school-completion/manifest.json',PORT/'native_map_data.ld'])
files.update(PORT/'build-game'/(n+'.native.ld') for n in ('map0_s01','map2_s00','map0_s02','map1_s00'))
files.update(PORT/'build/school-completion'/(f'map1_s{i:02}.native.ld') for i in range(1,7))
files.update(BUILD.glob('*.native.ld'));files.update(BUILD.rglob('*.log'))
files.update([BUILD/'post_school_identity.h',BUILD/'main_game.c'])
inventory={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)}
report=dict(status='INTEGRATION_READY_OFFLINE_CHECKPOINT',
    branch=git('branch','--show-current').decode().strip(),content_commit=git('rev-parse','HEAD').decode().strip(),
    patch_base_commit=git('rev-parse',BASE).decode().strip(),
    source_id=build['build'],accepted_cpu_base=build['accepted_cpu_base'],school_dependency=build['base'],
    internal_elf_sha256=build['elf_sha256'],hardware_candidate_created=False,hardware_accepted=False,published=False,
    start='MAP2_S00 after school: original flags 132/134 and K. Gordon Key handoff',
    end='MAP2_S02 normal control across drawbridge, arrival pose copied from MAP2_S00 point 56; room 12 in runtime fixture',
    maps_added=build['maps'],maps_reused=['map2_s00','map0_s02'],unused_map2_s03_added=False,
    content_events_added=95,chapter_item_use='Existing K. Gordon and Drawbridge Key dispatcher; preserved later AntiqueShopKey Use in complete MAP2_S02',
    enemies_added=['Romper: original compiled AI, native dispatch and 44-entry animation table'],bosses_added=[],
    actors_added=['Dahlia: original church event/AI and 52-entry native animation table'],
    fmv_dependency=build['fmv_dependency'],arm_component_checks=len(arm['checks']),
    runtime_checks=[dict(map=x['map'],room=x['room'],stable_control_ticks=x['stable_control_ticks']) for x in runtime['results']],
    save_model='Original 636-byte s_Savegame, flags/inventory/maps/enemy states; bridge geometry reconstructed on init',
    files_changed=paths,overlap_school=overlap_school,overlap_native_fmv=overlap_fmv,
    active_stage11b_changed_paths_vs_frozen_B=sorted(live_changes),
    stage11b_overlap_method='Read-only normalized source comparison at sealing time, not prediction of final 11B changes',
    unresolved=['Hardware graphics/audio/performance and continuous playthrough deferred',
        'Original FMV call needs existing Native-FMV checkpoint at integration; this isolated base still has the inherited presentation boundary',
        'Hospital and later chapter exits intentionally remain outside this content closure'],
    patch_sha256=sha(patch),frozen_11a_archive_sha256=sha(frozen),frozen_11a_unchanged=True,
    snapshot_files=len(inventory),scope='No Stage 11B merge, renderer/GTE/SPU redesign, hardware release or launcher publication')
receipt=OUT/'checkpoint.json';receipt.write_text(json.dumps(report,indent=2)+'\n')
archive=OUT/'post-school-checkpoint.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in inventory:
        assert not name.endswith('.3dsx'),name
        z.write(ROOT/name,'snapshot/'+name)
    z.write(patch,'content.patch');z.write(receipt,'checkpoint.json')
    z.writestr('inventory.json',json.dumps(inventory,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for name,row in inventory.items():
        data=z.read('snapshot/'+name)
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],name
report.update(archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive))
(PORT/'reports/post-school-checkpoint.json').write_text(json.dumps(report,indent=2)+'\n')
archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
print(json.dumps(report,indent=2))
