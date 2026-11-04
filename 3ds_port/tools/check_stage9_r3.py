"""Run R1 audio/control and accepted CPU regressions without replacing R1 evidence."""
from pathlib import Path
import subprocess,sys,os,json,hashlib
p=Path(__file__).resolve().parents[1]
wrapper=r'''
from pathlib import Path
import sys,runpy
target=Path(sys.argv[1]);sys.path.insert(0,str(target.parent))
orig=Path.write_text
def write(path,*a,**k):
    if path.parent.name=='reports' and not path.name.startswith('stage9-r3-'):path=path.with_name(path.name.replace('stage9-','stage9-r3-'))
    return orig(path,*a,**k)
Path.write_text=write
if target.name=='test_stage9_audio_arm.py':
    import run_arm_game as g
    init=g.GameRunner.__init__
    def setup(self,*a,**k):
        init(self,*a,**k)
        for name in ('game_xa_lock','game_xa_unlock'):self.bridge(name,lambda *_:self.ret(0))
    g.GameRunner.__init__=setup
if target.name=='check_stage9.py':
    src=target.read_text().replace('stage9-','stage9-r3-')
    exec(compile(src,str(target),'exec'),{'__file__':str(target),'__name__':'__main__'})
elif target.name=='test_stage9_ndsp_arm.py':
    src=target.read_text().replace('calls=[]',"calls=[]\nfor name in ('game_xa_lock','game_xa_unlock'):m.hook(name,lambda *_:m.ret())")
    src=src.replace("put('worker',0x1234);", "put('xa_worker',0x5678);put('worker',0x1234);")
    src=src.replace("'ndspChnWaveBufClear','ndspChnReset'", "'game_xa_close','ndspChnWaveBufClear','ndspChnReset'")
    src=src.replace('report=dict(status=', "assert [c[1] for c in calls if c[0]=='threadJoin']==[0x1234,0x5678]\nassert names.index('game_xa_close')<names.index('ndspChnWaveBufClear')\nassert get('xa_worker')==0\nreport=dict(xa_worker_joined_before_disc_close=True,status=")
    exec(compile(src,str(target),'exec'),{'__file__':str(target),'__name__':'__main__'})
else:
    sys.argv=[str(target)];runpy.run_path(str(target),run_name='__main__')
'''
results=[]
scripts=sys.argv[1:] or ['test_stage9_audio_arm.py','test_stage9_ndsp_arm.py','check_stage9.py']
for script in scripts:
    run=subprocess.run([sys.executable,'-c',wrapper,str(p/'tools'/script)],cwd=p.parent,capture_output=True,text=True)
    (p/'reports'/('stage9-r3-'+script.removesuffix('.py')+'.log')).write_text(run.stdout+run.stderr)
    results.append(dict(test=script,exit_code=run.returncode))
    print(script,'PASS' if not run.returncode else 'FAIL',flush=True)
    if run.returncode:print((run.stdout+run.stderr)[-2500:]);break
report=dict(status='PASS' if len(results)==len(scripts) and all(not v['exit_code'] for v in results) else 'FAIL',
    elf_sha256=hashlib.sha256((p/'silenthill_game.elf').read_bytes()).hexdigest(),results=results)
(p/'reports'/('stage9-r3-compatibility.json' if len(scripts)==3 else 'stage9-r3-supplemental.json')).write_text(json.dumps(report,indent=2)+'\n')
assert report['status']=='PASS'
