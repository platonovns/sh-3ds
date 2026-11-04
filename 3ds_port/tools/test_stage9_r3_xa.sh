#!/usr/bin/env bash
set -euo pipefail
p=3ds_port
a=pc_port/PsyCross/src/audio
python3 - <<'PY'
import re
from pathlib import Path
s=Path('src/bodyprog/sound/sound_data.c').read_text().split('s_XaItemData g_XaItemData[727] = {')[1].split('};')[0]
rows=re.findall(r'\{([^}]+)\}',s)
base=[0,0x99bf,0xa227,0xb377,0xd0bf,0xea57,0xf997,0x1096f,0x16f07,0x19797,0]
out=[]
for i,row in enumerate(rows):
    v=[int(n.strip(),0) for n in row.split(',') if n.strip()]
    if v[0]:out.append(f'{i} {base[v[0]]+v[4]} {v[6]} {v[7]} {v[5]}')
assert len(out)==726
Path('3ds_port/build/stage9-r3-xa-items.txt').write_text('\n'.join(out)+'\n')
PY
gcc -O2 -g -fwrapv -fsanitize=address,undefined -c $p/build/audio/xa_decode.c -o $p/build/xa_decode_host.o
g++ -std=c++17 -O2 -g -fwrapv -fsanitize=address,undefined -I$p/include -I$a \
    -Dfopen=xa_test_fopen -c $p/source/game_xa.cpp -o $p/build/game_xa_host.o
g++ -std=c++17 -O2 -g -fwrapv -fsanitize=address,undefined -I$p/include -I$a \
    $p/tests/stage9_r2_xa.cpp $p/build/game_xa_host.o $p/build/xa_decode_host.o \
    $a/PsyX_XAStream.cpp -pthread -o $p/build/stage9_r2_xa_test
SH_XA_BIN="$PWD/sh1_data/sh1.bin" ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 \
    $p/build/stage9_r2_xa_test $p/build/stage9-r3-xa-items.txt
g++ -std=c++17 -O2 -I$a $a/PsyX_XAStream.cpp \
    pc_port/PsyCross/tests/audio/PsyX_XAStream_fidelity_test.cpp -o $p/build/stage9_r2_xa_fidelity
$p/build/stage9_r2_xa_fidelity
