"""Original VAB -> libsd -> linked ARM SPU -> PCM. No NDSP/hardware claim."""
import hashlib,json,struct
import run_arm_game as game
from unicorn import UC_HOOK_CODE

r=game.GameRunner()
r.uc.mem_map(0x24000000,0x1000000)
next_heap=[0x24000000]
def alloc(size,*_):
    ptr=next_heap[0];next_heap[0]+=(size+31)&~31
    assert next_heap[0]<0x25000000
    r.ret(ptr)
for name in ('malloc','_Znwj','_Znaj'):
    if name in game.symbols:r.bridge(name,alloc)
for name in ('free','_ZdlPv','_ZdlPvj','_ZdaPv','_ZdaPvj','__aeabi_atexit','game_audio_lock','game_audio_unlock'):
    if name in game.symbols:r.bridge(name,lambda *_:r.ret(0))
ctor=next(n for n in game.symbols if n.startswith('_GLOBAL__sub_I_g_PsyX_SfxOverride'))
r.call(ctor)
r.call('PsxMemory_Init')
r.call('SD_Init')
for command in (160,162,163,170):
    r.call('SD_Call',command)
    for _ in range(80):r.call('Sd_TaskPoolExecute')
    assert r.call('Sd_AudioStreamingCheck')==0,(command,r.failure)

out=0x24800000
cases=[]
for sfx in (1281,1282,1283,1284,1300,1301,1317,1321,1322):
    r.call('SD_Call',16)
    voice=r.call('Sd_PlaySfx',sfx,0,0)
    r.call('game_spu_render',out,4096)
    data=bytes(r.uc.mem_read(out,4096*4));pcm=struct.unpack('<8192h',data)
    cases.append(dict(sfx=sfx,voice=voice,nonzero=sum(x!=0 for x in pcm),peak=max(abs(x) for x in pcm),sha256=hashlib.sha256(data).hexdigest()))
assert not r.failure and not r.invalid,(r.failure,r.invalid)
assert sum(c['nonzero']>0 for c in cases)>=6,cases
# Original option gain and per-SFX attenuation; test a looping base-bank voice.
gain=[]
for volume in (127,64,0):
    r.call('SD_Call',16)
    r.call('Sd_SetVolume',127,127,volume)
    r.call('Sd_PlaySfx',1322,0,0)
    r.call('game_spu_render',out,8192)
    data=struct.unpack('<16384h',bytes(r.uc.mem_read(out,8192*4)))
    gain.append(dict(option=volume,energy=sum(abs(x) for x in data[8192:])))
assert gain[0]['energy']>gain[1]['energy']>gain[2]['energy'],gain
r.call('Sd_SetVolume',127,127,127)
# BGM uses original KDT events and VAB samples; no XA/desktop decoder.
r.call('SD_Call',16)
r.call('SpuClearReverbWorkArea',1)
r.call('SD_Call',32)
for _ in range(160):r.call('Sd_TaskPoolExecute')
assert r.call('Sd_AudioStreamingCheck')==0
r.call('SD_Call',769)
music_nonzero=0
music_keys=[]
music_hook=r.uc.hook_add(UC_HOOK_CODE,lambda *_:music_keys.append(1),
    begin=game.symbols['SpuSetKeyOnWithAttr'],end=game.symbols['SpuSetKeyOnWithAttr'])
for frame in range(1,601):
    r.frames=frame
    r.call('Sd_TaskPoolExecute')
    # KDT emits initial volume-zero CCs. Gameplay layer events normally restore
    # these gains. This component fixture explicitly enables the channels.
    for channel in range(16):r.call('SdSetMidiVol',0,channel,127)
    if music_keys:
        r.call('game_spu_render',out,4096)
        music_nonzero=sum(x!=0 for x in struct.unpack('<8192h',bytes(r.uc.mem_read(out,16384))))
        if music_nonzero:break
assert music_nonzero>0 and music_keys,(music_nonzero,len(music_keys))
r.uc.hook_del(music_hook)
# The PSX timer uses elapsed Q12 time rather than render frame count.
timer_counts={}
timer_calls=[]
r.bridge('smf_timer',lambda *_:(timer_calls.append(1),r.ret(0)))
for step in (1,2):
    timer_calls.clear()
    r.uc.mem_write(game.symbols['tick_last'],struct.pack('<I',1))
    r.uc.mem_write(game.symbols['tick_fraction'],bytes(4))
    for frame in range(step,601,step):
        r.frames=frame;r.call('game_audio_tick')
    timer_counts[60//step]=len(timer_calls)
assert timer_counts[30]==timer_counts[60] and 5770<timer_counts[30]<5785,timer_counts
r.call('game_audio_cd_close')
for f in r.handles.values():f.close()
report=dict(status='PASS',scope=__doc__,cases=cases,original_volume_options=gain,
            KDT_music_nonzero=music_nonzero,KDT_keyons=len(music_keys),timer_ticks_10_seconds=timer_counts,
            KDT_layer_fixture='Original MIDI volume API unmutes all channels; not a full scene layer-mix validation',
            elf_sha256=hashlib.sha256(game.game_elf.read_bytes()).hexdigest())
(game.port/'reports/stage9-audio-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
