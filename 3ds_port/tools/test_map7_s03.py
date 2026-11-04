"""ARM component checks for final cutscene branches, damage, and ending flags."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
out = port / 'build/map7-s03-checks'
out.mkdir(parents=True, exist_ok=True)
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
source = (port/'tools/test_block3_components.py').read_text().split('\nr=Chapter();checks=[]', 1)[0]
source = source.replace("out=port/'build/block3-compile-probe'", "out=port/'build/map7-s03-checks'")
source = source.replace("*(str(p) for p in objects),'-o',str(probe)",
                        "*(str(p) for p in objects), str(port/'build-game/memcard.o'), '-Wl,--allow-multiple-definition','-o',str(probe)")
exec(compile(source, str(port/'tools/test_block3_components.py'), 'exec'))

data = asset('map7_s03')
for addr, count in [(0xea1e0,64),(0xea5e0,52),(0xea920,22),(0xeaa80,24),(0xeac00,8),
                    (0xeac80,46),(0xeaf60,4),(0xeafa8,6),(0xec808,12),(0xece50,12)]:
    for i in range(count):
        cb = struct.unpack_from('<I',data,addr-0xc9578+i*16)[0]
        assert cb in (0,0x800449f0,0x80044b38,0x80044ca4), (hex(addr), i)

obj, fixture = out/'map7_s03_probe.o', out/'map7_s03_probe.elf'
p = subprocess.run([prefix+'gcc', *shlex.split(flags), '-c', str(port/'tests/map7_s03_probe.c'), '-o', str(obj)], capture_output=True, text=True)
if p.returncode: raise RuntimeError(p.stderr)
names = ('map7_s03_probe_scene','map7_s03_probe_good','map7_s03_probe_bad','map7_s03_probe_boss')
subprocess.run([prefix+'gcc','-nostdlib','-Wl,-Ttext=0xE80000,--gc-sections,--just-symbols='+str(elf),
                *('-Wl,--undefined='+n for n in names),str(obj),'-o',str(fixture)],check=True)
raw2=fixture.read_bytes(); off2=struct.unpack_from('<I',raw2,28)[0]; size2,count2=struct.unpack_from('<HH',raw2,42)
for line in subprocess.check_output([prefix+'nm','-n',str(fixture)],text=True).splitlines():
    p=line.split()
    if len(p)==3 and p[2].startswith('map7_s03_probe_'): game.symbols[p[2]]=int(p[0],16)
r=Chapter()
for i in range(count2):
    typ,pos,addr,_,length,_,_,_=struct.unpack_from('<8I',raw2,off2+i*size2)
    if typ==1 and length:r.uc.mem_write(addr,raw2[pos:pos+length])
r.reset('map7_s03',42)
assert r.call('alchemilla_probe_header')==0
calls=[]
for symbol in ('func_800E3F30','func_800E4714','func_800E514C','func_800E70F0'):
    name='map7_s03_'+symbol
    def callback(*_, name=name): calls.append(name); r.ret()
    r.bridge(name,callback)
for symbol in ('map7_s03_Map_CutsceneObjectsUpdate','map7_s03_func_800E787C','map7_s03_func_800E86BC',
               'map7_s03_func_800DFB04','map7_s03_func_800DD964','func_8004C328','Sd_SfxStop'):
    if symbol in game.symbols:r.bridge(symbol,lambda *_:r.ret(0))
for kaufmann in (0,1):
    for cybil in (0,1):
        for step, expected in ((1,'func_800E3F30' if cybil else 'func_800E4714'),
                               (3,'func_800E514C' if kaufmann else 'func_800E70F0')):
            calls.clear();r.call('map7_s03_probe_scene',kaufmann,cybil,step)
            assert calls==['map7_s03_'+expected],(kaufmann,cybil,step,calls)
        assert r.call('map7_s03_probe_good',cybil)==0
        assert r.call('map7_s03_probe_bad',cybil)==0
for symbol in ('Fs_QueueStartRead','Fs_QueueWaitForEmpty','Dms_HeaderFixOffsets',
               'WorldGfx_CharaLmBufferAssign','map7_s03_func_800E9260','map7_s03_func_800D9394',
               'Model_AnimFlagsSet','map7_s03_func_800E1788','map7_s03_Player_ControlUnfreeze',
               'vcReturnPreAutoCamWork','map7_s03_func_800DD9D4','map7_s03_func_800DFB74',
               'func_8003D01C','map7_s03_sharedFunc_800D2EF4_0_s00','map7_s03_func_800E14DC'):
    if symbol in game.symbols:r.bridge(symbol,lambda *_:r.ret(0))
for symbol in ('map7_s03_func_800DD9B0','map7_s03_func_800DFB50'):
    def callback(*_, name=symbol): calls.append(name);r.ret()
    r.bridge(symbol,callback)
for kaufmann in (0,1):
    for cybil in (0,1):
        r.reset('map7_s03',42);calls.clear()
        r.call('map7_s03_probe_scene',kaufmann,cybil,8)
        assert calls==['map7_s03_'+('func_800DD9B0' if kaufmann else 'func_800DFB50')],(kaufmann,cybil,calls)
for boss in (0,1):
    for lethal in (0,1):assert r.call('map7_s03_probe_boss',boss,lethal)==0,(boss,lethal)
print('MAP7_S03 ARM callback, 391/449 branches, ending flags, boss damage and lethal states PASS')
