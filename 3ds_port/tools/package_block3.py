"""Seal a validated, committed Block 3 patch without game data or binaries."""
from pathlib import Path
import hashlib, json, os, re, subprocess, tempfile, zipfile

root = Path(__file__).resolve().parents[2]
port = root / '3ds_port'
build = port / 'build/block3'
probe = port / 'build/block3-compile-probe'
out = root.parent / 'otherworld-central-checkpoints/20261028'
base_commit = '06a13a05a8f242c3478cf9d4ef19920c885af9fe'
prerequisite = root.parent / 'alchemilla-checkpoints/20261028/alchemilla-checkpoint.zip'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(p.read_text())

git = ['git', '-C', str(root)]
if os.name != 'nt' and (root / '.git').is_file():
    directory = (root / '.git').read_text().removeprefix('gitdir:').strip()
    if re.match(r'^[A-Za-z]:/', directory):
        directory = subprocess.check_output(['wslpath', '-u', directory], text=True).strip()
        git = ['git', '--git-dir='+directory, '--work-tree='+str(root)]

def run(*args):
    return subprocess.check_output([*git, *args], cwd=root)

manifest = read(build / 'manifest.json')
reports = {
    'closure': read(build / 'closure.json'),
    'tables': read(build / 'tables.json'),
    'components': read(probe / 'components.json'),
    'runtime': read(probe / 'runtime-all.json'),
    'dynamic': read(probe / 'runtime-twinfeeler.json'),
    'return_control': read(probe / 'runtime-returned_walk.json'),
}
assert manifest['status'] == 'PASS' and not manifest['published'] and not manifest['hardware_accepted']
assert sha(build / 'block3-content.elf') == manifest['elf_sha256']
assert all(r['status'] == 'PASS' and r['elf_sha256'] == manifest['elf_sha256'] for r in reports.values())
assert {r['label'] for r in reports['runtime']['results']} == {
    'antique','otherworld','mall','twinfeeler','lisa','lisa_story','floatstinger','floatstinger_arena','returned_city'}
dynamic = reports['dynamic']['results']
assert len(dynamic) == 1 and dynamic[0]['boss_update_calls'] > 1 and dynamic[0]['bad_dynamic_callbacks'] == []
walk = reports['return_control']['results']
assert len(walk) == 1 and walk[0]['control_ticks'] >= 60 and walk[0]['walk_start'] != walk[0]['walk_end']
assert all(sha(root / name) == digest for name, digest in manifest['sources'].items())
assert (root / 'docs/3ds-block3-integration.md').is_file()
assert not run('diff', '--name-only', 'HEAD').strip(), 'Commit content before sealing'
assert not run('diff', '--cached', '--name-only').strip(), 'Commit staged content before sealing'
commit = run('rev-parse', 'HEAD').decode().strip()
assert run('branch', '--show-current').decode().strip() == 'codex/otherworld-central-content'
paths = run('diff', '--name-only', base_commit, commit).decode().splitlines()
assert paths
for name in paths:
    p = Path(name)
    assert p.suffix.lower() not in ('.bin','.cue','.3dsx','.elf','.o','.sav','.mcr')
    assert not name.startswith(('sh1_data/','assets/','pc_port/build_gen/extracted_data/'))
    assert not name.startswith(('3ds_port/source/render_','3ds_port/source/game_gpu',
                                '3ds_port/source/game_texture','3ds_port/source/game_gte',
                                '3ds_port/source/game_spu','src/screens/stream/'))

out.mkdir(parents=True, exist_ok=True)
final_patch = out / 'content.patch'
final_archive = out / 'block3-checkpoint.zip'
assert not final_patch.exists() and not final_archive.exists(), 'Never overwrite a sealed checkpoint'
temporary = tempfile.TemporaryDirectory(prefix='.sealing-', dir=out)
patch = Path(temporary.name) / 'content.patch'
archive = Path(temporary.name) / 'block3-checkpoint.zip'
patch.write_bytes(run('diff', '--binary', base_commit, commit))
subprocess.run([*git, 'apply', '--reverse', '--check', str(patch)], cwd=root, check=True)
for result in reports['runtime']['results'] + reports['dynamic']['results'] + reports['return_control']['results']:
    result.pop('last_packets', None)
receipt = dict(status='INTEGRATION_READY_OFFLINE_CHECKPOINT', branch='codex/otherworld-central-content',
    commit=commit, patch_base=base_commit, source_id=manifest['build'], elf_sha256=manifest['elf_sha256'],
    patch_sha256=sha(patch), alchemilla_archive_sha256=sha(prerequisite),
    prerequisite='Alchemilla checkpoint, its frozen toolchain and local original USA game data; supplied separately',
    native_fmv=manifest['fmv_dependency'], hardware_candidate_created=False, hardware_accepted=False,
    published=False, files_changed=paths, reverse_patch_check='PASS')
arm = Path(os.environ['DEVKITARM'])
devkitpro = Path(os.environ['DEVKITPRO'])
tools = [arm/'bin/arm-none-eabi-gcc', arm/'bin/arm-none-eabi-g++', arm/'bin/arm-none-eabi-ld',
         arm/'bin/arm-none-eabi-nm', devkitpro/'libctru/lib/libctru.a', devkitpro/'libctru/lib/libcitro3d.a']
receipt['toolchain_sha256'] = {p.name: sha(p) for p in tools}
receipt['compiler_version'] = subprocess.check_output([str(tools[0]), '-dumpfullversion'], text=True).strip()
for label, start, end in [('school','6679d655a','65ab73346'),('post_school','44997c1f3','6ae58172b'),
                          ('alchemilla','2782aeb20',base_commit),('native_fmv','518c44a9e','e94a90a6b')]:
    changed = set(run('diff','--name-only',start,end).decode().splitlines())
    receipt['overlap_'+label] = sorted(set(paths) & changed)
expected_base_sha = prerequisite.with_suffix('.zip.sha256').read_text().split()[0]
assert receipt['alchemilla_archive_sha256'] == expected_base_sha
inventory = {}
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    def write(name, data):
        info = zipfile.ZipInfo(name, date_time=(1980,1,1,0,0,0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        z.writestr(info, data, compresslevel=6)
    def add(name, data):
        inventory[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        write(name, data)
    add('content.patch', patch.read_bytes())
    add('checkpoint.json', (json.dumps(receipt, indent=2)+'\n').encode())
    add('build-manifest.json', (json.dumps(manifest, indent=2)+'\n').encode())
    for name, report in reports.items():
        add('validation/'+name+'.json', (json.dumps(report, indent=2)+'\n').encode())
    for name in paths:
        p = root / name
        if p.is_file():
            add('changed-source/'+name, p.read_bytes())
    write('inventory.json', (json.dumps(inventory, indent=2)+'\n').encode())
with zipfile.ZipFile(archive) as z:
    for name, row in inventory.items():
        data = z.read(name)
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256'], name
archive_sha = sha(archive)
archive_bytes = archive.stat().st_size
patch.replace(final_patch)
archive.replace(final_archive)
temporary.cleanup()
(out / 'checkpoint.json').write_text(json.dumps(receipt, indent=2)+'\n')
(out / 'block3-checkpoint.zip.sha256').write_text(archive_sha+'  '+final_archive.name+'\n')
print(json.dumps(dict(**receipt, archive=str(final_archive), archive_sha256=archive_sha,
                      archive_bytes=archive_bytes, archive_byte_verification='PASS'), indent=2))
