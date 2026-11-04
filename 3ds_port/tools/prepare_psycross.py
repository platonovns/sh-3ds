#!/usr/bin/env python3
"""Stage only the software GTE closure; never modify the pinned submodule."""
from pathlib import Path
import hashlib
import json
import subprocess

port = Path(__file__).resolve().parent.parent
upstream = port.parent / 'pc_port/PsyCross'
stage = port / 'build/psycross'
sources = (
    'src/gte/PsyX_GTE.cpp', 'src/gte/PsyX_GTE.h',
    'src/gte/rcossin_tbl.h', 'src/gte/ratan_tbl.h', 'src/gte/sqrt_tbl.h',
    'src/psx/libgte.c', 'src/psx/inline_c.c', 'include/psx/inline_c.h', 'include/psx/libgpu.h',
)
hashes = {}
expected = json.loads((port / 'patches/psycross-inputs.json').read_text())
for name in sources:
    data = (upstream / name).read_bytes()
    normalized = data.decode().replace('\r\n', '\n').rstrip('\n')+'\n'
    hashes[name] = hashlib.sha256(normalized.encode()).hexdigest()
    assert hashes[name] == expected[name], 'Pinned PsyCross input changed: '+name
    dest = stage / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(normalized)
subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i',
                str(port / 'patches/psycross-arm11.patch')], cwd=stage, check=True)
gpu = stage / 'include/psx/libgpu.h'
gpu.write_text(gpu.read_text().replace('#ifdef SH_PC_PORT',
    '#if defined(SH_PC_PORT) && !defined(SH_3DS_PORT)'))
text=gpu.read_text()
needle='#define addPrim(ot, p)\t\tsetaddr(p, getaddr(ot)), setaddr(ot, p)'
assert text.count(needle)==1
text=text.replace(needle,'''#ifdef SH_3DS_GAME
void Game3ds_PacketCheck(const void *packet,unsigned bytes);
#define addPrim(ot,p) (Game3ds_PacketCheck((p),sizeof(OT_TAG)+getlen(p)*4),setaddr(p,getaddr(ot)),setaddr(ot,p))
#else
'''+needle+'\n#endif')
gpu.write_text(text)
(stage / 'upstream-sha256.json').write_text(json.dumps(hashes, indent=2)+'\n')
gte=stage/'src/gte/PsyX_GTE.cpp'
text=gte.read_text()
text='#ifdef SH_3DS_GAME\n#include "game_profile.h"\n#endif\n'+text
needle='int GTE_operator(int op)\n{'
assert text.count(needle)==1
text=text.replace(needle,needle+'\n#ifdef SH_3DS_GAME\n GameProfileGteScope profile_scope;\n#endif')
gte.write_text(text)
(stage / '.prepared').touch()
