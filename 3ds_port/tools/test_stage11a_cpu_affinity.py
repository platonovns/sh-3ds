"""ABI-level requested core and exact object difference; no scheduler/hardware claim."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
if len(sys.argv)>1:
 label=sys.argv[1];elf=PORT/('build/stage11a-cpu-'+label+'/silenthill_stage11a_cpu_'+label+'.elf');os.environ['SH_GAME_ELF']=str(elf)
 fixture=PORT/'tools/test_stage9_r4_ndsp_format_arm.py'
 source=fixture.read_text().split('render=[];flush=[];queued=[]')[0]
 source=source.replace("str(p/'silenthill_game.elf')","os.environ['SH_GAME_ELF']")
 source=source.replace("m.hook('threadCreate',record('threadCreate',0x1234))",'''thread_args=[]
from unicorn.arm_const import UC_ARM_REG_SP
def create_spu(entry,arg,stack,priority):
    core,detached=struct.unpack('<iI',m.uc.mem_read(m.uc.reg_read(UC_ARM_REG_SP),8))
    thread_args.append(dict(entry=entry,arg=arg,stack=stack,priority=priority,core=core,detached=detached));ret(0x1234)
m.hook('threadCreate',create_spu)''')
 ns={'__file__':str(fixture),'__name__':'affinity_fixture'};exec(compile(source,str(fixture),'exec'),ns)
 args=ns['thread_args'];assert len(args)==1
 assert args[0]['core']==(2 if label=='B' else -2) and args[0]['stack']==32768 and args[0]['priority']==24 and args[0]['detached']==0,args
 print(json.dumps(dict(label=label,requested=args,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())));raise SystemExit
results=[json.loads(subprocess.check_output([sys.executable,str(Path(__file__).resolve()),label],text=True)) for label in ('A','B')]
a,b=[PORT/('build/stage11a-cpu-'+label) for label in ('A','B')]
different=[];same=[]
for f in sorted(a.glob('*.o')):
 (same if f.read_bytes()==(b/f.name).read_bytes() else different).append(f.name)
assert different==['game_audio_ndsp.o','main_game.o'],different
ma,mb=[json.loads((folder/'internal-elf.json').read_text()) for folder in (a,b)]
assert ma['source_provenance']['sources']==mb['source_provenance']['sources']
assert ma['source_provenance']['base_objects']==mb['source_provenance']['base_objects']
report=dict(status='PASS',scope=__doc__,requested_cores=results,identical_objects=same,different_objects=different,
 only_semantic_difference='Complete SPU worker threadCreate core argument -2 inherited (A), 2 (B); embedded ID differs.',hardware_accepted=False)
(PORT/'reports/stage11a-cpu-affinity.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
