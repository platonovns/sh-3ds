#!/usr/bin/env python3
"""Replay the captured ARM particle contour inputs, with a bounded instruction count."""
import argparse,json,struct
from pathlib import Path
import run_arm_game as game
from unicorn.arm_const import UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2

p=argparse.ArgumentParser();p.add_argument('--expect-hang',action='store_true');a=p.parse_args()
fixture=game.port/'tests/fixtures/stage6-particle-hang'
r=game.GameRunner();r.call('PsxMemory_Init')
r.uc.mem_write(game.symbols['g_SysWork'],(fixture/'syswork.dat').read_bytes())
r.uc.mem_write(game.symbols['g_PsxRam']+0xE0C4C,(fixture/'particle-vectors.dat').read_bytes())
u=r.uc;u.reg_write(UC_ARM_REG_SP,0x1001ffc0);u.reg_write(UC_ARM_REG_LR,0x30000000)
for reg,address in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),(0x20000000,0x20001000,0x20002000)):
    u.reg_write(reg,address)
u.emu_start(game.symbols['func_800CC8FC'],0x30000000,timeout=2_000_000,count=250_000)
pc=u.reg_read(UC_ARM_REG_PC);returned=pc==0x30000000
report={'execution':'actual linked ARM particle contour routine, captured real-hang inputs',
        'capture_build':'stage6.0-src-a3fea5e1b8d030dd','returned':returned,'pc':hex(pc),
        'instruction_limit':250000,'halt':r.failure,'invalid':r.invalid}
if returned:
    count=u.reg_read(UC_ARM_REG_R0);data=bytes(u.mem_read(0x20002000,64))
    nodes=[struct.unpack_from('<hh4B',data,i*8) for i in range(8)]
    indices=[];index=0
    for _ in range(9):
        if index in indices:break
        assert index<8,(index,nodes)
        indices.append(index);index=nodes[index][3]
    assert index==0 and len(indices)==count and 3<=count<=8,(count,indices,nodes)
    hull=[nodes[i][:2] for i in indices]
    cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    assert all(cross(hull[i-1],hull[i],hull[(i+1)%count])>=0 for i in range(count)),hull
    report.update({'vertices':count,'hull':hull,'closed_convex_contour':True})
print(json.dumps(report,indent=2))
assert not r.failure and not r.invalid,report
assert returned!=a.expect_hang,report
