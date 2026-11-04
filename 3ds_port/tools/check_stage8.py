"""Focused Stage 8 diagnostic-candidate checks; preserve Stage 7 reports."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
parser=argparse.ArgumentParser();parser.add_argument('group',choices=['pc','arm']);parser.add_argument('--only',nargs='+');a=parser.parse_args()
commands=[]
if a.group=='pc':
    for name in ('game_screen','game_clock','stage8_timing'):
        exe=p/'build'/name
        commands.append((name,['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
            '-I'+str(p/'include'),str(p/'tests'/(name+'_test.c')),'-o',str(exe)]))
        commands.append((name+'-run',[str(exe)]))
    commands.append(('pc-port',['bash',str(p/'tools/test_stage7_pc.sh')]))
    scripts=['test_stage7_card.py']
else:
    scripts=['test_stage8_gpu_arm.py','test_stage8_pause_arm.py','test_stage8_combat_arm.py','test_stage7_gpu_arm.py',
        'test_stage7_tmd_arm.py','test_stage7_save_arm.py','test_stage6_contract.py',
        'test_pose_arm.py','test_stage6_particle_hull.py','run_arm_game.py','test_stage8_title_arm.py','test_stage8_warmboot_arm.py',
        'test_stage8_r2_gpu_arm.py','test_stage8_r2_reload.py']
# Redirect only historical report filenames, retaining the actual test code,
# relative fixture directory and imports. Accepted archive/evidence stays intact.
runner="""import sys
from pathlib import Path
p=Path(sys.argv[1]);sys.path.insert(0,str(p.parent))
sys.argv=[str(p)]
s=p.read_text().replace('reports/stage7-','reports/stage8-')
exec(compile(s,str(p),'exec'),{'__file__':str(p),'__name__':'__main__'})
"""
for script in scripts:commands.append((script,[sys.executable,'-c',runner,str(p/'tools'/script)]))
env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1')
results=[]
current_sha=hashlib.sha256((p/'silenthill_game.elf').read_bytes()).hexdigest()
previous=p/'reports'/('stage8-final-'+a.group+'.json')
if a.only:
    old=json.loads(previous.read_text());assert old['elf_sha256']==current_sha
    results=[r for r in old['results'] if r['test'] not in a.only]
    commands=[c for c in commands if c[0] in a.only]
for name,cmd in commands:
    run=subprocess.run(cmd,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log=p/'reports'/('stage8-final-'+name.replace('.py','')+'.log');log.write_text(run.stdout)
    results.append(dict(test=name,exit_code=run.returncode,log=str(log.relative_to(root))))
    print(name,'PASS' if run.returncode==0 else 'FAIL',flush=True)
    if run.returncode:print(run.stdout[-4000:]);break
report=dict(status='PASS' if all(r['exit_code']==0 for r in results) else 'FAIL',
    group=a.group,elf_sha256=current_sha,results=results)
(p/'reports'/('stage8-final-'+a.group+'.json')).write_text(json.dumps(report,indent=2)+'\n')
assert report['status']=='PASS',report
