"""Scoped CPU-audit regressions; keep frozen R6 evidence immutable."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
p=Path(__file__).resolve().parents[1]
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
elfsha=sha(p/'silenthill_game.elf');rows=[]
tests=[('test_stage10_cpu_audit.py',False),('test_stage10_host_profile.py',False),
       ('test_stage10_r6_readback.py',False),('test_stage10_r6_decode.py',False),
       ('test_stage10_r6_feedback_decode.py',False),('test_stage9_ndsp_arm.py',False),
       ('test_stage10_profile_pcm_arm.py',False),('test_stage10_packet_arm.py',True),
       ('test_stage10_transition_arm.py',True),('test_stage8_combat_arm.py',True)]
for name,isolated in tests:
    env=dict(os.environ)
    env['PYTHONPATH']=str(p.parent.parent/'.toolchain/python-deps')
    if isolated:env['SH_STAGE9_REGRESSION']='1'
    else:env.pop('SH_STAGE9_REGRESSION',None)
    log=p/'reports'/('stage10-r6-cpu-'+name.removesuffix('.py')+'.log')
    begin=time.monotonic()
    with log.open('w') as out:
        run=subprocess.run([sys.executable,str(p/'tools'/name)],env=env,stdout=out,stderr=subprocess.STDOUT)
    row=dict(test=name,status='PASS' if run.returncode==0 else 'FAIL',
             seconds=round(time.monotonic()-begin,2),log=log.name)
    rows.append(row);print(json.dumps(row),flush=True)
assert elfsha==sha(p/'silenthill_game.elf'),'ELF changed during CPU audit tests'
record=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
            normal_elf_sha256=elfsha,tests=rows,hardware_accepted=False)
(p/'reports/stage10-r6-cpu-tests.json').write_text(json.dumps(record,indent=2)+'\n')
sys.exit(record['status']!='PASS')
