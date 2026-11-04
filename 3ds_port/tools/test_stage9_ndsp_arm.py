"""Linked native pause/sleep/worker/shutdown control with SDK calls recorded."""
import hashlib,json,struct,os,subprocess
from pathlib import Path
fixture=Path(__file__).with_name('test_game_gpu_arm.py')
ns={'__file__':str(fixture),'__name__':'stage9_ndsp_fixture'}
exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
m=ns['Machine']();symbols=ns['symbols'];p=ns['port']
table=subprocess.check_output([str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-readelf'),'-sW',str(p/'silenthill_game.elf')],text=True)
owner=None
for line in table.splitlines():
    fields=line.split()
    if len(fields)<8:continue
    if fields[3]=='FILE':owner=fields[-1]
    elif owner=='game_audio_ndsp.c' and fields[3] in ('OBJECT','FUNC'):
        symbols[fields[-1]]=int(fields[1],16)
from unicorn.arm_const import UC_ARM_REG_R0
def put(name,value):m.uc.mem_write(symbols[name],struct.pack('<I',value))
def get(name):return struct.unpack('<I',m.uc.mem_read(symbols[name],4))[0]
calls=[]
def thread_id(out,*_):
    m.uc.mem_write(out,struct.pack('<I',42))
    m.uc.reg_write(UC_ARM_REG_R0,0);m.ret()
# CPU inventory reads the real worker's ID at entry. Model only this SDK query;
# execute the linked audit code with its production default (timing disabled).
if 'game_cpu_audit_enter' in symbols:m.hook('svcGetThreadId',thread_id)
def record(name):
    def fn(*args):calls.append((name,*args));m.uc.reg_write(UC_ARM_REG_R0,0);m.ret()
    return fn
for name in ('ndspChnSetPaused','LightEvent_Signal'):m.hook(name,record(name))
put('started',1)
m.call('apt_callback',2,0) # sleep
assert get('paused')==2
m.call('game_audio_pause',1)
assert get('paused')==3
m.call('apt_callback',3,0) # waking must preserve the explicit game pause
assert get('paused')==1
m.call('game_audio_pause',0)
assert get('paused')==0
pause_values=[c[2] for c in calls if c[0]=='ndspChnSetPaused']
assert pause_values==[1,1,1,0],pause_values
assert get('pause_requests')==get('resume_requests')==1
# A paused worker must yield without advancing the SPU or submitting PCM.
put('paused',1);put('running',1)
renders=[];waits=[]
m.hook('game_spu_render',lambda *_:(renders.append(1),m.ret()))
m.hook('ndspChnWaveBufAdd',lambda *_:(renders.append(2),m.ret()))
def wait(*_):
    waits.append(1)
    if len(waits)==2:put('running',0)
    m.uc.reg_write(UC_ARM_REG_R0,0);m.ret()
m.hook('LightEvent_WaitTimeout',wait)
m.call('audio_thread',0)
assert len(waits)==2 and not renders,(waits,renders)
# A normal close must join the worker before clearing/freeing DSP buffers.
put('worker',0x1234);put('pcm',0x2345);put('hook_installed',1)
for name in ('aptUnhook','threadJoin','threadFree','ndspSetCallback',
             'ndspChnWaveBufClear','ndspChnReset','ndspExit','linearFree'):
    m.hook(name,record(name))
m.hook('ndspGetDroppedFrames',lambda *_:(m.uc.reg_write(UC_ARM_REG_R0,7),m.ret()))
m.call('game_audio_shutdown')
names=[c[0] for c in calls]
assert names.index('threadJoin')<names.index('ndspChnWaveBufClear')<names.index('linearFree')
assert get('started')==get('worker')==get('pcm')==0 and get('saved_dropped')==7
report=dict(status='PASS',scope=__doc__,nested_pause_values=pause_values,
    paused_worker_waits=len(waits),paused_worker_renders=len(renders),
    shutdown_joins_before_free=True,dropped_frame_diagnostic_survives_shutdown=True,
    elf_sha256=hashlib.sha256((p/'silenthill_game.elf').read_bytes()).hexdigest())
(p/'reports/stage9-ndsp-arm.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
