"""Audit R2 against the immutable R1 source snapshot and accepted Stage 8 R2."""
from pathlib import Path
import hashlib,json,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
expected={
 '3ds_port/Makefile.game','3ds_port/source/game_native.c','3ds_port/source/game_audio_cd.c',
 '3ds_port/source/game_audio_ndsp.c','3ds_port/source/game_spu.cpp','3ds_port/include/game_audio.h',
 '3ds_port/tools/prepare_audio.py','3ds_port/tools/build_identity.py'}
assert sha(p/'baselines/stage9-audio-r1.zip')=='f1dea799457a6fa6f488d6d7135c2317477f3efbec5c41d01706167587e39613'
assert sha(p/'build/hardware-stage9-audio-r1/silenthill_game.3dsx')=='64fa06ea86ad82c7ad6ea5df7dbaddb24a5807a9d306db5ea15b2491d165e92c'
assert sha(p/'baselines/stage8-diagnostic-r2.zip')=='dffd08a195f33304f72c2abdb45784d9cfed7d410cfeca5eb66c88cbbc0911ee'
assert sha(p/'build/hardware-stage8-diagnostic-r2/silenthill_game.3dsx')=='0b1b71f2c0f55014e0768d237d29b045c98ce115b842205213463c290c626570'
with zipfile.ZipFile(p/'baselines/stage9-audio-r1.zip') as z:
    manifest=json.loads(z.read('manifest.json'))
    changed=[]
    for n,v in manifest.items():
        if n.startswith(('src/','include/','pc_port/','3ds_port/source/','3ds_port/include/','3ds_port/tools/')) or n=='3ds_port/Makefile.game':
            if not (root/n).is_file() or sha(root/n)!=v['sha256']:changed.append(n)
    assert set(changed)==expected,changed
    for n in ('PsyX_SPUCore.cpp','PsyX_SPUCore.h','smf_main.c','smf_io.c','smf_mid.c','smf_snd.c'):
        name='3ds_port/build/audio/'+n
        assert sha(root/name)==manifest[name]['sha256'],name
    # Preserve historical R1 reports if a legacy regression subprocess wrote
    # its old filename. Keep that run's output under the R2 prefix first.
    restored=[]
    for n,v in manifest.items():
        if n.startswith('3ds_port/reports/stage9-regression-') and (root/n).is_file() and sha(root/n)!=v['sha256']:
            f=root/n;copy=f.with_name(f.name.replace('stage9-','stage9-r2-'))
            if not copy.exists():copy.write_bytes(f.read_bytes())
            f.write_bytes(z.read(n));restored.append(n)
record=dict(status='PASS',R1_archive_preserved=True,R1_binary_preserved=True,
    accepted_Stage8_R2_preserved=True,changed_R1_sources=changed,
    original_game_renderer_maps_and_audio_sources_unchanged=True,
    generated_SPU_core_and_libsd_unchanged=True,historical_report_files_restored=restored)
(p/'reports/stage9-r2-baseline.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
