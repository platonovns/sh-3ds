#!/usr/bin/env python3
"""Conservative per-symbol triage of the frozen, pre-integration census.
Unknown symbols remain A/review: this is never a stub-generation list.
"""
import collections
import json
import os
from pathlib import Path
import re
import subprocess

port = Path(__file__).resolve().parents[1]
before = json.loads((port / 'reports/stage4-audit-before-fs.json').read_text())
nm = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-nm')
listing = subprocess.check_output([nm, '-g', str(port / 'silenthill_3ds.elf')], text=True)
linked = {f[2] for line in listing.splitlines() if len(f := line.split()) == 3 and f[1].upper() != 'U'}
symbols = sorted({s for g in before['groups'].values() for s in g['unresolved']})
output = {'scope': 'frozen partial ARM object census, not a full native boot/map link', 'symbols': {}}
for s in symbols:
    if s in linked:
        cls, reason = 'D', 'Defined in current linked ARM ELF; existing backend/runtime or S4.1 integration'
    elif re.match(r'(?:Pc_|g_Pc|Hires|TexPack|Texpack|Font_|Lang_|Nm_|NmScroll_|g_Sh|SH_Log|DbgOverlay|SDL_|gl[A-Z])', s) or s == 'PsyX_CaptureGteDepths':
        cls, reason = 'C', 'PC enhancement/instrumentation: exclude its producer; do not add desktop implementation'
    elif s in ('SD_Call', 'Sd_PlaySfx', 'Sd_SfxStop', 'Sfx_WithFalloffAndPitchPlay', 'Player_FootstepSfxPlay', 'open_main'):
        cls, reason = 'B', 'Output/presentation boundary only; preserve caller game state and completion semantics; not implemented in S4.1'
    else:
        cls, reason = 'A', 'Retain implementation/data or prove caller unreachable; unknown names must not become zero/no-op stubs'
    output['symbols'][s] = {'class': cls, 'reason': reason}
output['class_counts'] = dict(collections.Counter(v['class'] for v in output['symbols'].values()))
output['remaining_against_current_linked_elf'] = {name: {
    'before': group['unresolved_count'], 'remaining_count': len(remaining := [s for s in group['unresolved'] if s not in linked]),
    'now_satisfied': [s for s in group['unresolved'] if s in linked], 'remaining': remaining}
    for name, group in before['groups'].items()}
(port / 'reports/stage4-blockers.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'class_counts': output['class_counts'], 'counts': {k: v['remaining_count'] for k,v in
                  output['remaining_against_current_linked_elf'].items()}}, indent=2))
