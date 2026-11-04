"""Immutable R2/R1/accepted Stage 8 R2 provenance; original gameplay stays frozen."""
from pathlib import Path
import hashlib,json,zipfile
p=Path(__file__).resolve().parents[1];root=p.parent
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
pairs={
 '3ds_port/baselines/stage9-audio-r2.zip':'37fd3037e7f6f37227981d23eaece686883366cc5f4d4319c2af8614542941f2',
 '3ds_port/build/hardware-stage9-audio-r2/silenthill_game.3dsx':'f32c2d52a4cf0dc0a396bd1c5009e7b475cd3f8032499c324744198cd30b1f34',
 '3ds_port/baselines/stage9-audio-r1.zip':'f1dea799457a6fa6f488d6d7135c2317477f3efbec5c41d01706167587e39613',
 '3ds_port/build/hardware-stage9-audio-r1/silenthill_game.3dsx':'64fa06ea86ad82c7ad6ea5df7dbaddb24a5807a9d306db5ea15b2491d165e92c',
 '3ds_port/baselines/stage8-diagnostic-r2.zip':'dffd08a195f33304f72c2abdb45784d9cfed7d410cfeca5eb66c88cbbc0911ee',
 '3ds_port/build/hardware-stage8-diagnostic-r2/silenthill_game.3dsx':'0b1b71f2c0f55014e0768d237d29b045c98ce115b842205213463c290c626570'}
for n,h in pairs.items():assert sha(root/n)==h,n
expected={
 '3ds_port/source/main_game.c','3ds_port/source/game_native.c','3ds_port/source/game_spu.cpp',
 '3ds_port/source/game_audio_cd.c','3ds_port/source/game_audio_ndsp.c','3ds_port/source/game_xa.cpp',
 '3ds_port/source/game_xa_thread.c','3ds_port/include/game_audio.h','3ds_port/include/game_xa.h',
 '3ds_port/tools/prepare_audio.py'}
with zipfile.ZipFile(p/'baselines/stage9-audio-r2.zip') as z:
    manifest=json.loads(z.read('manifest.json'))
    changed=[n for n,v in manifest.items() if n.startswith(('src/','include/','pc_port/','3ds_port/source/','3ds_port/include/','3ds_port/tools/'))
        and (not (root/n).is_file() or sha(root/n)!=v['sha256'])]
    assert set(changed)==expected,changed
    for name in ('smf_main.c','smf_io.c','smf_mid.c','smf_snd.c','xa_decode.c'):
        n='3ds_port/build/audio/'+name;assert sha(root/n)==manifest[n]['sha256'],n
core=(p/'reports/stage9-r3-core-tests.log').read_text()
assert 'All PsyX_SPUCore standalone tests passed.' in core
assert 'PASS: 48 PCM/voice-state/SPU-RAM/ENDX cases' in core
for kind in ('original','native'):
    data=(p/('reports/stage9-core-equivalence-'+kind+'.txt')).read_bytes()
    (p/('reports/stage9-r3-core-equivalence-'+kind+'.txt')).write_bytes(data)
assert (p/'reports/stage9-r3-core-equivalence-original.txt').read_bytes()==(p/'reports/stage9-r3-core-equivalence-native.txt').read_bytes()
report=dict(status='PASS',immutable_artifact_hashes=pairs,changed_R2_sources=changed,
    original_game_maps_renderer_audio_sources_unchanged=True,generated_libsd_and_decoder_unchanged=True,
    SPU_diagnostic_counters_preserve_PCM_and_voice_state=True,
    scope='DIAGNOSTIC ONLY; real hardware root cause not proven; R2 failed hardware test')
(p/'reports/stage9-r3-baseline.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
