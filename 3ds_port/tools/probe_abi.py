#!/usr/bin/env python3
"""Export sizes/alignments/offsets from an ARM object, without executing host C."""
from pathlib import Path
import json
import shlex
import struct
import subprocess

port = Path(__file__).resolve().parent.parent
out = port / 'build/abi-probe'
out.mkdir(exist_ok=True)
command = subprocess.check_output(['make', '-s', '--no-print-directory', '-C', str(port),
    '--eval=print-engine-flags:;@echo $(CC) $(ENGINE_CFLAGS)', 'print-engine-flags'], text=True)
flags = shlex.split(command)
types = [('void*', None), ('int', None), ('long', None), ('bool', None),
    ('MATRIX', 't'), ('SVECTOR', 'vz'), ('VECTOR', None), ('VECTOR3', None),
    ('s_Pose', 'rotation'), ('s_AnmBindPose', None), ('s_AnmHeader', 'bindPoses'),
    ('OT_TAG', None), ('POLY_F3', 'x0'), ('s_Primitive', 'field_6'),
    ('s_MeshHeader', 'primitives'), ('s_ModelHeader', 'meshHdrs'),
    ('s_LmHeader', 'modelHdrs'), ('s_IpdCollSurface', 'tiltAngleX'),
    ('s_IpdCollSubcell', 'surfaceIdx0'), ('s_IpdHeader', 'collisionData'),
    ('s_FsMemState', None), ('s_GteScratchData', None), ('s_GteScratchData2', None)]
values = []
for typ, field in types:
    values += ['sizeof('+typ+')', '_Alignof('+typ+')', 'offsetof('+typ+','+field+')' if field else '0']
source = out / 'probe.c'
source.write_text('#include "common.h"\n#include "bodyprog/bodyprog.h"\n#include "main/fsmem.h"\n'
                  'const unsigned int abi_values[] = {'+', '.join(values)+'};\n')
obj = out / 'probe.o'
subprocess.run([*flags, '-c', str(source), '-o', str(obj)], check=True)
binary = out / 'values.bin'
subprocess.run([flags[0].replace('gcc', 'objcopy'), '-O', 'binary', '-j', '.rodata.abi_values',
                str(obj), str(binary)], check=True)
words = struct.unpack('<'+'I'*(3*len(types)), binary.read_bytes())
result = {}
for i, (typ, field) in enumerate(types):
    size, align, offset = words[i*3:i*3+3]
    result[typ] = {'sizeof': size, 'alignof': align}
    if field:
        result[typ]['offsetof_'+field] = offset
(port / 'reports/abi-layout.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
