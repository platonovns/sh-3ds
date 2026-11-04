#!/usr/bin/env python3
"""Reuse the existing PC GS packet producers without desktop instrumentation."""
from pathlib import Path
import re, hashlib, json
p=Path(__file__).resolve().parents[1]
source=p.parent/'pc_port/src/stubs/libgs_stub.c'
s=source.read_text()
text=s[s.index('void GsTMDfastF3LFG(void* op, VERT* vp, VERT* np, PACKET* pk, int n, int shift, GsOT* ot, unsigned long* scratch)\n{'):s.index('\nvoid GsSortObject4(GsDOBJ2')]
# Only one guarded block in these producers: desktop diagnostic reads.
text=re.sub(r'#ifdef SH_PC_PORT\n.*?\n#endif\n','',text,flags=re.S)
text='''/* Generated from PC libgs_stub.c; GPL-3.0-or-later. */
#define TMD_PGXP3(...) ((void)0)
#define TMD_PGXP4(...) ((void)0)
#define ITEM_PRECISE_SZ(...) ((void)0)
#define ITEM_PROBE_SORT(...) ((void)0)
#define ITEMDIM(c) (c)
'''+text
# Check before writing, rather than discovering a packet overrun after the fact.
text=re.sub(r'(        poly = \(POLY_\w+\*\)GsOUT_PACKET_P;)',r'        game_tmd_packet_check(64);\n\1',text)
text=text.replace('            poly = (POLY_F3*)GsOUT_PACKET_P;','            game_tmd_packet_check(64);\n            poly = (POLY_F3*)GsOUT_PACKET_P;')
out=p/'build-game/tmd_emit.inc'
if not out.exists() or out.read_text()!=text:out.write_text(text)
reports=p/'build/reports'
reports.mkdir(parents=True,exist_ok=True)
(reports/'stage7-tmd-provenance.json').write_text(json.dumps({'source':str(source.relative_to(p.parent)), 'sha256':hashlib.sha256(source.read_bytes()).hexdigest(), 'adaptation':'existing 16 packet producers, desktop instrumentation removed, pre-write packet bound added'},indent=2)+'\n')
