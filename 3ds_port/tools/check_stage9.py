"""Replay accepted CPU regressions, preserving all historical report files."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parents[1]
scripts=['test_stage8_gpu_arm.py','test_stage8_pause_arm.py','test_stage8_combat_arm.py',
         'test_stage7_gpu_arm.py','test_stage7_tmd_arm.py','test_stage7_save_arm.py',
         'test_stage6_contract.py','test_pose_arm.py','test_stage6_particle_hull.py',
         'run_arm_game.py','test_stage8_title_arm.py','test_stage8_warmboot_arm.py',
         'test_stage8_r2_gpu_arm.py','test_stage8_r2_reload.py']
runner='''import runpy,sys
from pathlib import Path
orig=Path.write_text
def write(path,*a,**k):
    if path.parent.name=='reports':
        path=path.with_name(path.name.replace('stage7-','stage9-regression-').replace('stage8-','stage9-regression-'))
    return orig(path,*a,**k)
Path.write_text=write
sys.path.insert(0,str(Path(sys.argv[1]).parent))
target=sys.argv[1]
sys.argv=[target]
runpy.run_path(target,run_name='__main__')
'''
results=[]
for script in scripts:
    run=subprocess.run([sys.executable,'-c',runner,str(p/'tools'/script)],cwd=p.parent,
                       env=dict(os.environ,SH_STAGE9_REGRESSION='1'),capture_output=True,text=True)
    log=p/'reports'/('stage9-regression-'+script.removesuffix('.py')+'.log')
    log.write_text(run.stdout+run.stderr)
    results.append(dict(test=script,exit_code=run.returncode))
    print(script,'PASS' if run.returncode==0 else 'FAIL',flush=True)
    if run.returncode:print((run.stdout+run.stderr)[-1800:]);break
report=dict(status='PASS' if len(results)==len(scripts) and all(r['exit_code']==0 for r in results) else 'FAIL',
            scope='Accepted gameplay/graphics CPU regressions with R2-equivalent silent audio fixture; audio tested separately',
            elf_sha256=hashlib.sha256((p/'silenthill_game.elf').read_bytes()).hexdigest(),results=results)
(p/'reports/stage9-regressions.json').write_text(json.dumps(report,indent=2)+'\n')
assert report['status']=='PASS'
