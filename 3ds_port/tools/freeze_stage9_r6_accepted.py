"""Archive the exact R6 snapshot after explicit user hardware acceptance.

No compiler, game, profiler, network or launcher tooling is invoked. Runtime
sources and binary bytes come from the already frozen, verified R6 archive.
"""
from pathlib import Path, PurePosixPath
import hashlib,json,re,shutil,zipfile

p=Path(__file__).resolve().parents[1];root=p.parent
BUILD='stage9.0-src-b1645a424e58cb44'
BINARY_SHA='dafee0513d08e841e34bbe177a7a1e8d02d365bd307dc184999c95acefd0f3ed'
ELF_SHA='3306e6252fd020ffb1d77053853e798c21e03292f2cc99054b7937b00041a18a'
BASE_SHA='a22694e2df8f8160d5502c841fe04fc5c5f7e8c7c2582dd81c8a553e2e878289'
def digest(data):return hashlib.sha256(data).hexdigest()
def sha(path):return digest(path.read_bytes())
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

base=p/'baselines/stage9-audio-r6.zip'
accepted=p/'build/hardware-stage9-audio-r6-accepted'
archive=p/'baselines/stage9-audio-r6-accepted.zip'
report=p/'reports/stage9-r6-accepted.json'
receipt=p/'reports/stage9-r6-accepted-freeze.json'
assert not any(f.exists() for f in (accepted,archive,report,receipt)), 'Never overwrite an accepted baseline'
assert sha(base)==BASE_SHA
with zipfile.ZipFile(base) as z:
    manifest=json.loads(z.read('manifest.json'))
    assert len(manifest)==939
    assert len(z.namelist())==len(set(z.namelist()))==len(manifest)+1
    data={name:z.read(name) for name in manifest}
for name,v in manifest.items():
    assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts,name
    assert len(data[name])==v['bytes'] and digest(data[name])==v['sha256'],name

native=[n for n in data if n.startswith(('src/','include/','pc_port/','3ds_port/source/',
    '3ds_port/include/','3ds_port/build/audio/')) and n.endswith(('.c','.cpp','.h','.inc'))]
assert all((root/n).is_file() and sha(root/n)==manifest[n]['sha256'] for n in native)
# Evaluate only the archived path-list declarations, never the generator's write.
prefix=data['3ds_port/tools/build_identity.py'].decode().split('digest = hashlib.sha256()')[0]
ns={'__file__':str(p/'tools/build_identity.py')}
exec(compile(prefix,'archived-R6-identity-paths','exec'),ns)
# pathlib on Linux sorts path components, not flat strings. Preserve that order
# even when this archival utility is run on Windows.
paths=sorted({f.relative_to(root).as_posix() for f in ns['paths']},key=lambda n:PurePosixPath(n).parts)
assert len(paths)==659 and all(n in data for n in paths)
identity_hash=hashlib.sha256()
for n in paths:
    assert sha(root/n)==manifest[n]['sha256'],n
    identity_hash.update(n.encode()+b'\0'+data[n]+b'\0')
assert 'stage9.0-src-'+identity_hash.hexdigest()[:16]==BUILD
assert re.search(r'"(stage9[^\"]+)"',data['3ds_port/build/build_identity.h'].decode())[1]==BUILD

old_prefix='3ds_port/build/hardware-stage9-audio-r6/'
for ext in ('.3dsx','.elf','.map','.smdh'):
    n=old_prefix+'silenthill_game'+ext
    assert sha(root/n)==manifest[n]['sha256'],n
assert len(data[old_prefix+'silenthill_game.3dsx'])==1014484
assert digest(data[old_prefix+'silenthill_game.3dsx'])==BINARY_SHA
assert digest(data[old_prefix+'silenthill_game.elf'])==ELF_SHA
assert BUILD.encode() in data[old_prefix+'silenthill_game.elf']
frozen=read(p/'reports/stage9-r6-audit.json')['frozen_hashes_preserved']
for n,value in frozen.items():assert sha(p/n)==value,n
memcard_sha=sha(root/'sh1_data/memcard.mcr')
assert memcard_sha=='69f5d3e396493d43f49e46590addba4e775436fb0d923362f14aeeda2790eb96'
test_names=('audio-arm','ndsp-arm','xa-arm','diagnostics-arm','supplemental')
for name in test_names:
    result=read(p/f'reports/stage9-r6-{name}.json')
    assert result['status']=='PASS' and result['elf_sha256']==ELF_SHA
raw=p/'reports/stage9-r6-hardware-cheryl/stage4_status.txt'
assert sha(raw)=='4ad0629b727a549ceb5526d0e20c4ed1bd4e11be8044f577fe85046dcbe6f7c8'

record=dict(status='HARDWARE ACCEPTED',hardware_accepted=True,stage_closed=True,
    date='2026-10-26',authority='Прямая финальная приёмка пользователем на реальной New Nintendo 3DS',
    user_statement='Stage 9 is closed and HARDWARE ACCEPTED.',
    baseline='Stage 9 R6 — принятый audio baseline поверх принятого gameplay Stage 8 R2',
    build=BUILD,binary=(accepted/'silenthill_game.3dsx').relative_to(root).as_posix(),
    bytes=1014484,sha256=BINARY_SHA,elf_sha256=ELF_SHA,
    archive=archive.relative_to(root).as_posix(),archive_receipt=receipt.relative_to(root).as_posix(),
    original_candidate_archive=base.relative_to(root).as_posix(),original_candidate_archive_sha256=BASE_SHA,
    source_snapshot=dict(provenance='Исходный замороженный R6; runtime-файлы взяты из архива, без пересборки',
        original_manifest_files=len(manifest),native_files_compared=len(native),identity_input_files=len(paths),
        identity_recomputed=BUILD,current_runtime_matches_accepted_snapshot=True),
    hardware_confirmed=dict(original_SFX_VAB=True,surface_footsteps=True,collision_impact=True,
        KDT_music=True,monster_audio=True,early_Cheryl_Harry_XA=True,Cafe_Harry_Cybil_XA=True,
        speech_pitch_speed_correct=True,compared_against_original_game_playback=True,
        no_audible_gaps_or_starvation=True,START_Skip_stops_active_voice=True,subsequent_audio_functional=True),
    final_hardware_counters_reported_by_user=dict(XA_underflows=0,lost_PCM_frames=0,
        maximum_speech_gap=0,NDSP_drops=0,XA_errors=0),
    evidence=dict(final_authority='Прямое итоговое сообщение пользователя; отдельный сырой Cafe-отчёт не приложен',
        preserved_early_Cheryl_report=raw.relative_to(root).as_posix(),early_Cheryl_report_sha256=sha(raw)),
    diagnostics=dict(preserved=True,removal_policy='Только после доказательства существенной runtime-стоимости будущим профилированием',
        retained=['underflows','requested/supplied frames','missing frames','ring occupancy/in/out',
            'startup reserve/waits','EOF padding','gap/short blocks','cancel/completion reasons',
            'IO/batch/worker timing','CD/SPU/NDSP counters and errors']),
    deferred=dict(S9_PERF_01=dict(id='S9-PERF-01',status='DEFERRED — отдельная стадия performance/profiling',
        hardware_Cafe_FPS='10–12',between_line_pauses='Медленное продвижение игры/катсцены при низком FPS по наблюдению пользователя',
        individual_lines_correct_speed_pitch=True,audio_correctness_failure=False,
        accepted_audio_must_not_compensate_for_slow_game_execution=True),
        FMV_video_playback='Вне Stage 9; отложено',separate_FMV_audio_path='Вне Stage 9; отложено'),
    validation_boundary='Hardware gameplay/audio — только до Cafe включительно; более позднее содержимое не заявляется проверенным',
    supplemental_automated_tests={name:'PASS на точном принятом ELF' for name in test_names},
    no_runtime_changes=True,no_rebuild=True,no_performance_work=True,memory_card_unchanged=True,
    preserved_prior_baseline_hashes=frozen,
    supersedes='Прежние pending-статусы кандидатов R1–R6; исторические файлы сохраняются неизменными')
accepted.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):
    name='silenthill_game'+ext
    (accepted/name).write_bytes(data[old_prefix+name])
    assert sha(accepted/name)==manifest[old_prefix+name]['sha256']
shutil.copy2(root/'docs/3ds-stage9-r6-accepted.md',accepted/'README.md')
write(report,record)

# Retain the original snapshot verbatim, overlay only closure documentation,
# and add the accepted copies and acceptance record. Old candidate reports
# remain explicitly historical; no current untested runtime files are added.
overlays=[root/'docs'/name for name in ('3ds-stage9-r6-accepted.md','3ds-stage9-r6-handoff.md',
    '3ds-stage9-handoff.md','3ds-stage9-r6-hardware-feedback.md',
    '3ds-stage9-r6-hardware-starvation.md','3ds-backlog.md','3ds-port.md')]
overlays += [report,p/'reports/stage9-r6-freeze.json',Path(__file__).resolve()]
overlays += [f for f in accepted.iterdir() if f.is_file()]
overlays += [f for f in (p/'reports/stage9-r6-hardware-cheryl').iterdir() if f.is_file()]
for f in overlays:data[f.relative_to(root).as_posix()]=f.read_bytes()
for n in native+paths:assert digest(data[n])==manifest[n]['sha256'],n
assert all(PurePosixPath(n).suffix.lower() not in ('.bin','.cue','.mcr','.cdc','.wav','.pcm') for n in data)
final_manifest={n:dict(bytes=len(b),sha256=digest(b)) for n,b in sorted(data.items())}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for n,b in sorted(data.items()):z.writestr(n,b)
    z.writestr('manifest.json',json.dumps(final_manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    assert len(z.namelist())==len(set(z.namelist()))==len(final_manifest)+1
    for n,v in final_manifest.items():
        b=z.read(n);assert len(b)==v['bytes'] and digest(b)==v['sha256'],n
    for n in native+paths:assert digest(z.read(n))==manifest[n]['sha256'],n
assert sha(base)==BASE_SHA and sha(raw)==record['evidence']['early_Cheryl_report_sha256']
assert sha(root/'sh1_data/memcard.mcr')==memcard_sha
for n,value in frozen.items():assert sha(p/n)==value,n
write(receipt,dict(status='PASS',hardware_accepted=True,stage_closed=True,authority=record['authority'],
    build=BUILD,bytes=record['bytes'],sha256=BINARY_SHA,elf_sha256=ELF_SHA,
    archive=record['archive'],archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
    manifest_files_verified=len(final_manifest),original_R6_manifest_files_verified=len(manifest),
    native_files_preserved=len(native),source_identity_inputs_preserved=len(paths),
    original_R6_archive_unchanged=True,accepted_binary_matches_hardware_tested_candidate=True,
    diagnostics_byte_identical=True,prior_accepted_baselines_unchanged=True,
    memory_card_unchanged=True,no_rebuild=True,no_performance_work=True))
print(json.dumps(read(receipt),indent=2,ensure_ascii=True))
