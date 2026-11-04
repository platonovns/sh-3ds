"""Actual linked SDK adapter: rate ABI, PCM layout, buffer and frame units.

SDK services are recorders; this is not DSP firmware or hardware validation.
"""
from pathlib import Path
import struct,subprocess,os,json
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_S0
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
ns={'__file__':str(fixture),'__name__':'ndsp_format_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
m=ns['Machine']();symbols=ns['symbols'];p=ns['port'];calls=[]
table=subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-readelf'),'-sW',str(p/'silenthill_game.elf')],text=True)
owner=None
for line in table.splitlines():
    f=line.split()
    if len(f)<8:continue
    if f[3]=='FILE':owner=f[-1]
    elif owner=='game_audio_ndsp.c' and f[3] in ('OBJECT','FUNC'):symbols[f[-1]]=int(f[1],16)
def ret(v=0):m.uc.reg_write(UC_ARM_REG_R0,v);m.ret()
def record(name,value=0):
    def fn(*a):calls.append((name,*a));ret(value)
    return fn
for name in ('game_spu_init','game_xa_thread_init','ndspInit','ndspSetOutputMode','ndspSetClippingMode',
             'ndspChnReset','ndspChnSetInterp','ndspChnSetFormat','ndspSetCallback','aptHook'):
    m.hook(name,record(name))
if 'LightEvent_Init' in symbols:m.hook('LightEvent_Init',record('LightEvent_Init'))
m.hook('linearAlloc',record('linearAlloc',0x10008000))
m.hook('threadCreate',record('threadCreate',0x1234))
rate=[];mix=[]
def set_rate(*a):rate.append((a[0],struct.unpack('<f',struct.pack('<I',m.uc.reg_read(UC_ARM_REG_S0)))[0]));ret()
def set_mix(ch,ptr,*_):mix.append((ch,struct.unpack('<12f',m.uc.mem_read(ptr,48))));ret()
m.hook('ndspChnSetRate',set_rate);m.hook('ndspChnSetMix',set_mix)
assert m.call('game_audio_init')==0
assert rate==[(0,44100.0)],rate
assert mix==[(0,(1.0,1.0)+(0.0,)*10)],mix
assert next(c[2] for c in calls if c[0]=='ndspChnSetFormat')==6 # stereo PCM16
assert next(c[1] for c in calls if c[0]=='linearAlloc')==8192
render=[];flush=[];queued=[]
def render_pcm(ptr,frames,*_):render.append((ptr,frames));ret()
def flushed(ptr,size,*_):flush.append((ptr,size));ret()
def queued_buffer(ch,ptr,*_):
    data,frames=struct.unpack('<2I',m.uc.mem_read(ptr,8));queued.append((ch,data,frames))
    m.uc.mem_write(ptr+17,b'\1');ret() # NDSP_WBUF_QUEUED
def clock(*_):m.uc.reg_write(UC_ARM_REG_R1,0);ret(0)
def wait(*_):m.uc.mem_write(symbols['running'],bytes(4));ret()
m.hook('game_spu_render',render_pcm);m.hook('DSP_FlushDataCache',flushed)
m.hook('ndspChnWaveBufAdd',queued_buffer);m.hook('game_spu_xa_submitted',record('submitted'))
m.hook('svcGetSystemTick',clock);m.hook('LightEvent_WaitTimeout',wait)
m.call('audio_thread',0)
assert render==[(0x10008000+i*2048,512) for i in range(4)],render
assert flush==[(ptr,frames*4) for ptr,frames in render],flush
assert queued==[(0,ptr,frames) for ptr,frames in render],queued
assert struct.unpack('<I',m.uc.mem_read(symbols['rendered'],4))[0]==2048
report=dict(status='PASS',rate=rate,format='NDSP_FORMAT_STEREO_PCM16',channel_mix=mix,
    frame_count_per_buffer=512,interleaved_s16_values_per_buffer=1024,bytes_per_buffer=2048,
    total_queued_frames=2048,scope=__doc__)
(p/'reports/stage9-r4-ndsp-format-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
