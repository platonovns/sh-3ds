#!/usr/bin/env python3
"""Execute retail MIPS SetPriority to establish its packet contract."""
from pathlib import Path
import hashlib,json,struct
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn.mips_const import UC_MIPS_REG_A0,UC_MIPS_REG_A1,UC_MIPS_REG_A2,UC_MIPS_REG_RA
port=Path(__file__).resolve().parents[1];root=port.parent
reference=json.loads((port/'reports/disc-reference.json').read_text())
meta=reference['executable']
with (root/'sh1_data/sh1.bin').open('rb') as f:
    data=[]
    for i in range((meta['bytes']+2047)//2048):
        f.seek((meta['lba']+i)*2352+24);data.append(f.read(2048))
exe=b''.join(data)[:meta['bytes']]
assert hashlib.sha1(exe).hexdigest()==reference['exe_sha1']
base=struct.unpack_from('<I',exe,24)[0];address=0x800192fc
results=[]
for a,b in ((0,0),(0,1),(1,0),(1,1)):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    # MIPS KSEG0 fetches are translated to the physical low-RAM alias.
    u.mem_map(base&0x1fffffff,0x20000);u.mem_write(base&0x1fffffff,exe[2048:])
    u.mem_map(0x200000,0x1000);u.mem_map(0x300000,0x1000)
    for reg,value in ((UC_MIPS_REG_A0,0x200000),(UC_MIPS_REG_A1,a),(UC_MIPS_REG_A2,b),(UC_MIPS_REG_RA,0x300000)):
        u.reg_write(reg,value)
    u.emu_start(address,0x300000,count=1000)
    packet=bytes(u.mem_read(0x200000,12))
    results.append({'a':a,'b':b,'length':packet[3],
        'commands':[hex(v) for v in struct.unpack('<2I',packet[4:12])]})
print(json.dumps({'context':'original retail MIPS function, packet contract only',
    'exe_sha1':reference['exe_sha1'],'function':'SetPriority','address':hex(address),'cases':results},indent=2))
