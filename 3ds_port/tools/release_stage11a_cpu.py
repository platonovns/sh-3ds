"""Package the exact correctness-verified production ELF, immediately publish each game 3DSX."""
import hashlib,json,os,subprocess
from pathlib import Path
from stage11a_baseline import verify
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def report(name):return json.loads((PORT/'reports'/name).read_text())
verify()
affinity=report('stage11a-cpu-affinity.json');assert affinity['status']=='PASS'
regression=report('stage11a-cpu-regression.json');assert all(c['status']=='PASS' for c in regression['cases']) and len(regression['cases'])==17 and regression['golden_card_unchanged']
for name in ('stage11a-cpu-pcm.json','stage11a-cpu-host.json','stage11a-cpu-scissor.json','stage11a-cpu-gte.json'):
 assert report(name)['status']=='PASS',name
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
for label in ('A','B'):
 dest=PORT/('build/stage11a-cpu-'+label);record=json.loads((dest/'internal-elf.json').read_text())
 elf=dest/('silenthill_stage11a_cpu_'+label+'.elf');binary=elf.with_suffix('.3dsx')
 assert sha(elf)==record['elf_sha256'] and record['build'].encode() in elf.read_bytes()
 provenance=record['source_provenance']
 assert all(sha(ROOT/p)==h for p,h in provenance['sources'].items())
 assert all(sha(Path(p))==h for p,h in provenance['base_objects'].items())
 assert affinity['requested_cores'][0 if label=='A' else 1]['elf_sha256']==sha(elf)
 if label=='A':
  for name in ('stage11a-cpu-A-arm.json','stage11a-cpu-A-xa-arm.json'):
   proof=report(name);assert proof['status']=='PASS' and proof['elf_sha256']==sha(elf),name
  for name in ('stage11a-cpu-gte-arm.json','stage11a-cpu-submit-arm.json','stage11a-cpu-arm-bench.json'):
   proof=report(name);assert proof['status']=='PASS' and proof['results']['CPU']['elf_sha256']==sha(elf),name
  assert regression['elf_sha256']==sha(elf)
 assert 'Game3ds_DevEnter' not in (dest/'symbols.txt').read_text()
 subprocess.run(['3dsxtool',str(elf),str(binary),'--smdh='+str(PORT/'silenthill_game.smdh')],check=True)
 subprocess.run(['python3',str(PORT/'dev_server/after_build.py'),str(binary)],check=True)
 size=subprocess.check_output([prefix+'size',str(elf),str(PORT/'build/stage11a-tracefix/silenthill_stage11a_tracefix.elf')],text=True)
 result=dict(build=record['build'],variant='STAGE11A_CPU_'+label,sha256=sha(binary),size=binary.stat().st_size,
  elf_sha256=sha(elf),source_provenance=provenance,elf_size=size,stage10_preserved=True,normal_objects_unchanged=True,
  silent_candidate_default=1,F0_available=True,spu_affinity=2 if label=='B' else -2,spu_priority=24,block_frames=512,
  further_spu='paired_nibbles_and_ARM_ssat',gte_cleanup='guarded_CLZ',partial_texture_tiles=True,
  submission_texture_memo=True,scissor_cache=True,internal_spu_sampled_profiling=False,
  new_heap_linear_vram_allocations=0,new_threads=0,stage11a_accepted=False,hardware_reproduction_pending=True)
 (dest/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
 (PORT/('reports/stage11a-cpu-'+label+'-candidate.json')).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='source_provenance'},indent=2),flush=True)
