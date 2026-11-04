"""Actual linked ARM GTE normalization/division; integer result oracle, instruction counts."""
import hashlib,json,os,struct,subprocess,sys
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
if len(sys.argv)>1:
 elf=PORT/sys.argv[1];os.environ['SH_GAME_ELF']=str(elf)
 fixture=PORT/'tools/test_game_gpu_arm.py';ns={'__file__':str(fixture),'__name__':'gte_arm'}
 exec(compile(fixture.read_text().split('results={}')[0],str(fixture),'exec'),ns)
 m=ns['Machine']();symbols=ns['symbols'];data=[];seed=0x11a
 for x in [0,0xffffffff,*[1<<i for i in range(32)]]:
  data.append(m.call('gte_leadingzerocount',x))
 for i in range(4096):
  seed=(seed*1664525+1013904223)&0xffffffff;data.append(m.call('gte_leadingzerocount',seed))
  n=seed&65535;d=seed>>16
  data.append(m.call('_Z10gte_dividett',n,d))
 for n in (0,1,32767,32768,65535):
  for d in (0,1,2,16383,16384,32767,32768,65534,65535):data.append(m.call('_Z10gte_dividett',n,d))
 from unicorn import UC_HOOK_CODE
 count=[0]
 def instruction(*_):count[0]+=1
 hook=m.uc.hook_add(UC_HOOK_CODE,instruction);m.call('gte_leadingzerocount',0x8000);m.uc.hook_del(hook)
 assert not m.failure
 print(json.dumps(dict(sha256=hashlib.sha256(struct.pack('<'+'I'*len(data),*data)).hexdigest(),values=len(data),
  clz_instructions_including_return=count[0],elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())));raise SystemExit
results={label:json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),path],text=True)) for label,path in
 [('F1','build/stage11a-tracefix/silenthill_stage11a_tracefix.elf'),('CPU','build/stage11a-cpu-A/silenthill_stage11a_cpu_A.elf')]}
assert results['F1']['sha256']==results['CPU']['sha256']
assert results['CPU']['clz_instructions_including_return']<results['F1']['clz_instructions_including_return']
report=dict(status='PASS',scope=__doc__,results=results,not_hardware_timing=True)
(PORT/'reports/stage11a-cpu-gte-arm.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
