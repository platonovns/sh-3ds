"""Synthetic validation of four-window sequence and honest attribution flags."""
import copy
import json
from pathlib import Path
from analyze_stage11a_lifetime import read,compare
PORT=Path(__file__).resolve().parents[1]
a=read(PORT/'build/stage11a-lifetime-tests/cpu_audit_001.txt')
b=copy.deepcopy(a);b['end']['spu'][8]=24;b['end']['spu'][4]=24;b['fps']=12
w=copy.deepcopy(b);w['begin']['context'][0:3]=[11,0,0];w['end']['context'][0:3]=[11,0,0]
c=copy.deepcopy(w);c['session']='another-launch';c['end']['spu'][8]=6;c['end']['spu'][4]=6;c['fps']=30
result=compare([a,b,w,c])
assert result['early_to_degraded_changes']['silent_nonzero_pitch_voices']==18
assert result['warm_minus_cold']['silent_nonzero_pitch_voices']==18
assert not result['owner_confirmed'] and not result['true_memory_leak_proven'] and not result['diagnostic_causality_proven']
assert result['leads']
try:
    c['session']=w['session'];compare([a,b,w,c])
except AssertionError:pass
else:raise AssertionError('Process restart was not checked')
record=dict(status='PASS',scope='SYNTHETIC_NOT_HARDWARE',
            checks=['raw recorder schema','four-window process sequence','warm vs cold retained state',
                    'growth vs stable fields','no false leak/owner/diagnostics attribution'])
(PORT/'reports/stage11a-lifetime-analysis-tests.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
