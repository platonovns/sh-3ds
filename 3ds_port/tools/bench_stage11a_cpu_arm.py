"""Executed ARM instructions, not elapsed ARM11 time. Real VAB/KDT fixture."""
import hashlib,json,os,subprocess,sys,struct
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
if len(sys.argv)>1:
 elf=PORT/sys.argv[1];os.environ['SH_GAME_ELF']=str(elf)
 from unicorn import UC_HOOK_CODE
 fixture=PORT/'tools/test_stage9_audio_arm.py'
 setup=fixture.read_text().split('out=0x24800000')[0]
 rows=[]
 for workload in ('idle24','sfx4','kdt','reverb_sfx','future_keyon'):
  ns={'__file__':str(fixture),'__name__':'cpu_arm_benchmark'};exec(compile(setup,str(fixture),'exec'),ns)
  r,g=ns['r'],ns['game'];out=0x24800000
  if not r.call('game_spu_silent_fast_enabled'):r.call('game_spu_silent_fast_toggle')
  if workload=='idle24':r.call('control_change',0,1,0)
  else:
   for sfx in (1281,1284,1300,1322):r.call('Sd_PlaySfx',sfx,0,0)
   if workload=='kdt':
    r.call('SD_Call',32)
    for _ in range(160):r.call('Sd_TaskPoolExecute')
    r.call('SD_Call',769)
    for frame in range(1,151):
     r.frames=frame;r.call('Sd_TaskPoolExecute')
     for ch in range(16):r.call('SdSetMidiVol',0,ch,127)
   if workload=='reverb_sfx':
    r.call('SpuSetReverb',1);r.call('SpuSetReverbVoice',1,0xffffff)
   if workload=='future_keyon':
    r.call('control_change',0,1,0)
    for _ in range(16):r.call('game_spu_render',out,512)
    r.call('Sd_PlaySfx',1322,0,0)
  for _ in range(4):r.call('game_spu_render',out,512)
  counts=[0]
  def instruction(*_):counts[0]+=1
  hook=r.uc.hook_add(UC_HOOK_CODE,instruction)
  r.call('game_spu_render',out,512);r.uc.hook_del(hook)
  pcm=bytes(r.uc.mem_read(out,2048))
  assert not r.failure and not r.invalid
  rows.append(dict(workload=workload,instructions=counts[0],pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                   nonzero=sum(v!=0 for v in struct.unpack('<1024h',pcm))))
  for f in r.handles.values():f.close()
 print(json.dumps(dict(elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),rows=rows)));raise SystemExit
results={}
for label,path in [('F1','build/stage11a-tracefix/silenthill_stage11a_tracefix.elf'),('CPU','build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf')]:
 results[label]=json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),path],text=True))
for a,b in zip(results['F1']['rows'],results['CPU']['rows'],strict=True):assert a['pcm_sha256']==b['pcm_sha256'],(a,b)
report=dict(status='PASS',scope=__doc__,results=results,not_hardware=True)
(PORT/'reports/stage11a-cpu-arm-bench.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
