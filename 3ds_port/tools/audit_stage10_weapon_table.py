"""Inspect retail weapon keyframes after the real ARM boot decrypts BODYPROG."""
import hashlib,json,os,shlex,struct,subprocess
from pathlib import Path
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN
from unicorn.mips_const import UC_MIPS_REG_SP,UC_MIPS_REG_RA
import run_arm_game as game
from retail_mips import initial_ram
class Runner(game.GameRunner):
    def vblank(self,*_):
        self.frames+=1
        if self.state==7:self.stopped=True;self.uc.emu_stop()
        self.ret(0)
r=Runner();run=game.run(r,seconds=120)
assert r.state==7 and not run['failure'] and not run['invalid'] and not run['exception'],run
ram=game.symbols['g_PsxRam']
retail=bytes(r.uc.mem_read(ram+0x294f4,88*8))
current=bytes(r.uc.mem_read(game.symbols['D_800294F4'],88*8))
report=dict(scope=__doc__,retail_address='0x800294f4',matching=retail==current,
    handgun_retail=[struct.unpack_from('<2h',retail,8*i+4) for i in range(39,49)],
    handgun_current=[struct.unpack_from('<2h',current,8*i+4) for i in range(39,49)])
(game.port/'build/stage10-retail-weapon-keyframes.bin').write_bytes(retail)
(game.port/'build/stage10-retail-weapon-update-mips.bin').write_bytes(r.uc.mem_read(ram+0x7ebbc,0x610))
p=game.port;prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=shlex.split((p/'build-game/flags').read_text().splitlines()[0])
obj=p/'build/stage10_weapon_probe.o';elf=obj.with_suffix('.elf')
subprocess.run([prefix+'gcc',*flags,'-c',str(p/'tests/stage10_weapon_probe.c'),'-o',str(obj)],check=True)
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE00000,--just-symbols='+str(game.game_elf),str(obj),'-o',str(elf)],check=True)
raw=elf.read_bytes();off=struct.unpack_from('<I',raw,28)[0];size,count=struct.unpack_from('<HH',raw,42)
for i in range(count):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw,off+i*size)
    if typ==1 and length:r.uc.mem_write(addr,raw[pos:pos+length])
for line in subprocess.check_output([prefix+'nm','-n',str(elf)],text=True).splitlines():
    s=line.split()
    if len(s)==3 and s[2]=='stage10_weapon_copy':game.symbols[s[2]]=int(s[0],16)
image=initial_ram();cases=[]
for weapon in (*range(8),32,33,34,35,8,255):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    u.mem_map(0,0x301000);u.mem_write(0,image)
    u.mem_write(0xb9fc0+0x47,bytes([weapon]));u.mem_write(0xaf224,bytes([weapon,0,0,0]))
    u.mem_write(0xc44f0,bytes([0xa5])*80)
    u.reg_write(UC_MIPS_REG_SP,0x801ff000);u.reg_write(UC_MIPS_REG_RA,0x300000)
    u.emu_start(0x8007ebbc,0x300000,count=100000)
    expected=bytes(u.mem_read(0xc44f0,80))
    r.uc.mem_write(game.symbols['D_800C44F0'],bytes([0xa5])*80)
    r.call('stage10_weapon_copy',weapon,0x20008000)
    actual=bytes(r.uc.mem_read(0x20008000,80))
    # First words are ignored 32-bit data, preserved byte-for-byte as well.
    assert actual==expected,(weapon,actual.hex(),expected.hex())
    original=[struct.unpack('<h',u.mem_read(a,2))[0] for a in (0xaf5c6,0xaf624,0xaf626)]
    native=list(struct.unpack('<3i',r.uc.mem_read(0x20008000+80,12)))
    # Unsupported IDs leave the previously selected table alone. This fixture
    # creates fresh MIPS RAM per case but reuses the native boot; only compare
    # aliases when the selector actually installed a weapon table.
    installed=expected!=bytes([0xa5])*80
    if installed:assert original==native,(weapon,'animation aliases',original,native)
    cases.append(dict(weapon=weapon,keyframes_sha256=hashlib.sha256(actual).hexdigest(),
        aim_reload_aliases=original if installed else 'unchanged'))
report.update(retail_mips_function='0x8007ebbc',original_mips_vs_native_weapon_copies=cases,
    elf_sha256=hashlib.sha256(game.game_elf.read_bytes()).hexdigest(),status='PASS')
assert retail==current and game.symbols['D_800294F4']==ram+0x294f4
(game.port/'reports/stage10-weapon-table-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
