"""Focused sequencer diagnostic, using the same real-bank ARM fixture."""
from pathlib import Path
test=Path(__file__).with_name('test_stage9_audio_arm.py')
exec(compile(test.read_text().split('out=0x24800000')[0],str(test),'exec'))
def word(n):return struct.unpack('<I',r.uc.mem_read(game.symbols[n],4))[0]
def state(label):
    print(label,{n:word(n) for n in ('sd_int_flag','sd_int_flag2','sd_interrupt_start_flag','smf_start_flag','g_Sd_CurrentTask','tick_last','tick_fraction')},
          'song',bytes(r.uc.mem_read(game.symbols['smf_song']+0x500,64)).hex(),
          'midi0',bytes(r.uc.mem_read(game.symbols['smf_midi'],16)).hex(),flush=True)
r.call('SD_Call',32)
for i in range(200):r.call('Sd_TaskPoolExecute')
state('loaded')
r.call('SD_Call',769)
for i in range(4):r.call('Sd_TaskPoolExecute')
state('started')
for frame in range(1,61):
    r.frames=frame;r.call('Sd_TaskPoolExecute')
state('one_second')
notes=[];keys=[]
for fn,events in (('set_note_on',notes),('SpuSetKeyOnWithAttr',keys)):
    if fn not in game.symbols:continue
    r.uc.hook_add(UC_HOOK_CODE,lambda *_,events=events:events.append(1),begin=game.symbols[fn],end=game.symbols[fn])
for channel in range(16):r.call('SdSetMidiVol',0,channel,127)
for frame in range(61,1801):
    r.frames=frame;r.call('Sd_TaskPoolExecute')
    for channel in range(16):r.call('SdSetMidiVol',0,channel,127)
state('30_seconds_unmuted')
print('notes',len(notes),'keys',len(keys),'track0',bytes(r.uc.mem_read(game.symbols['smf_song'],40)).hex(),flush=True)
