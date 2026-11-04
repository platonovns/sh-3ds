"""Existing complete original XA/KDT test on the candidate ELF in F1."""
import hashlib,json,os,sys
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
sys.path.insert(0,str(ROOT.parent/'.toolchain/python-deps'))
elf=PORT/'build/stage11a-tracefix/silenthill_stage11a_tracefix.elf';os.environ['SH_GAME_ELF']=str(elf)
fixture=PORT/'tools/test_stage9_r6_xa_arm.py';source=fixture.read_text()
needle="r=ns['r'];g=ns['game'];out=0x24800000"
assert source.count(needle)==1
source=source.replace(needle,needle+"\nr.call('game_spu_silent_fast_toggle')")
source=source.replace('stage9-r6-xa-arm.json','stage11a-tracefix-xa-arm.json')
ns={'__file__':str(fixture),'__name__':'tracefix_xa_arm'};exec(compile(source,str(fixture),'exec'),ns)
report_path=PORT/'reports/stage11a-tracefix-xa-arm.json';result=json.loads(report_path.read_text())
baseline=json.loads((PORT/'reports/stage9-r6-xa-arm.json').read_text())
assert result['original_xa_requests_verified']==726 and result['playback']==baseline['playback']
result['F1_enabled']=True;result['PCM_matches_preserved_XA_KDT_fixture']=True
report_path.write_text(json.dumps(result,indent=2)+'\n')
