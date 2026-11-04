"""Original CD task machine and real linked ARM XA/SPU with host stdio only."""
import struct,hashlib,json
from unicorn import UC_HOOK_CODE
from pathlib import Path
fixture=Path(__file__).with_name('test_stage9_audio_arm.py')
src=fixture.read_text().split('out=0x24800000')[0]
src=src.replace("r.call(ctor)","\nfor name in ('game_xa_lock','game_xa_unlock'):r.bridge(name,lambda *_:r.ret(0))\nr.call(ctor)")
ns={'__file__':str(fixture),'__name__':'xa_arm_fixture'}
exec(compile(src,str(fixture),'exec'),ns)
r=ns['r'];g=ns['game'];out=0x24800000
# Execute every original XA command through original stop/mode/filter/seek/read
# states. Capture starts at the platform boundary to check authored metadata.
items=[]
for line in (g.port/'build/stage9-r2-xa-items.txt').read_text().splitlines():items.append(tuple(map(int,line.split())))
starts=[]
real_start=g.symbols['game_xa_start']
r.bridge('game_xa_start',lambda lba,file,channel,ticks:(starts.append((lba,file,channel,ticks)),r.ret(0)))
for idx,lba,ticks,file,channel in items:
    r.call('SD_Call',4096+idx)
    for _ in range(20):r.call('Sd_TaskPoolExecute')
    assert starts[-1]==(lba,file,channel,ticks),(idx,starts[-1])
    r.call('SD_Call',19)
    for _ in range(15):r.call('Sd_TaskPoolExecute')
    assert r.call('game_audio_xa_pending')==0,idx
assert len(starts)==726
# Remove only our start hook so actual ARM transport now reads the BIN.
r.uc.hook_del(r.named_hooks.pop('game_xa_start'))
# Original KDT driver emits zero-volume layer CCs; enable layers through the
# original MIDI API, as in R1's fixture, then leave music running under dialogue.
r.call('SD_Call',32)
for _ in range(160):r.call('Sd_TaskPoolExecute')
r.call('SD_Call',769)
music_keys=[]
hook=r.uc.hook_add(UC_HOOK_CODE,lambda *_:music_keys.append(1),begin=g.symbols['SpuSetKeyOnWithAttr'],end=g.symbols['SpuSetKeyOnWithAttr'])
for frame in range(1,601):
    r.frames=frame;r.call('Sd_TaskPoolExecute')
    for channel in range(16):r.call('SdSetMidiVol',0,channel,127)
    if music_keys:break
assert music_keys
r.uc.hook_del(hook)
rows=[]
for cap in (30,60):
    r.call('SD_Call',4097)
    for _ in range(20):r.call('Sd_TaskPoolExecute')
    assert r.call('game_audio_xa_pending')==1
    for _ in range(4):r.call('game_xa_step')
    before=r.call('game_xa_elapsed60')
    r.call('game_spu_render',out,4096)
    pcm=bytes(r.uc.mem_read(out,4096*4))
    assert any(pcm)
    assert 5<=r.call('game_xa_elapsed60')-before<=6
    r.call('game_xa_pause',1)
    elapsed=r.call('game_xa_elapsed60');r.call('game_spu_render',out,1024)
    assert elapsed==r.call('game_xa_elapsed60')
    r.call('game_xa_pause',0)
    r.call('Sd_PlaySfx',1322,0,0)
    r.call('game_xa_step');r.call('game_spu_render',out,4096)
    mixed=bytes(r.uc.mem_read(out,4096*4));assert any(mixed)
    rows.append(dict(cap=cap,xa_pcm_sha256=hashlib.sha256(pcm).hexdigest(),mixed_pcm_sha256=hashlib.sha256(mixed).hexdigest()))
    if cap==60:
        # Drain source PCM on the mixer clock, with infrequent game updates,
        # and let the original length+32 watchdog perform natural cleanup.
        for step in range(800):
            r.call('game_xa_step');r.call('game_xa_pull',out,512)
            if step%7==0:r.call('Sd_TaskPoolExecute')
            if not r.call('game_audio_xa_pending'):break
        assert not r.call('game_audio_xa_pending'),step
    # Original explicit stop must remove audio immediately at the PCM source.
    r.call('SD_Call',19);assert r.call('game_xa_pull',out,512)==0
    for _ in range(15):r.call('Sd_TaskPoolExecute')
    assert not r.call('game_audio_xa_pending')
# Skip while the original driver is still seeking, before ReadN.
r.call('SD_Call',4098)
for _ in range(9):r.call('Sd_TaskPoolExecute')
r.call('SD_Call',19)
for _ in range(30):r.call('Sd_TaskPoolExecute');r.call('game_xa_step')
assert not r.call('game_audio_xa_pending') and not r.call('game_xa_pull',out,512)
assert not r.failure and not r.invalid,(r.failure,r.invalid)
r.call('game_xa_close');r.call('game_audio_cd_close')
for f in r.handles.values():f.close()
report=dict(status='PASS',scope=__doc__,original_xa_requests_verified=len(starts),playback=rows,
    simultaneous_KDT_keyons=len(music_keys),KDT_layer_fixture='Original MIDI API enables layers, as in R1 audio test',
    natural_completion_via_original_watchdog=True,
    skip_during_seek_cancels_pending_start=True,stop_clears_source_immediately=True,
    elf_sha256=hashlib.sha256(g.game_elf.read_bytes()).hexdigest())
(g.port/'reports/stage9-r2-xa-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
