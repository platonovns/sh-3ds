"""Package a built game ELF with the accepted HOME artwork and supplied WAV."""
import argparse, hashlib, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser()
source=Path(__file__).resolve().parent
assets=source.parent/'packaging'
for name in ('elf','output'):
    p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--panel',type=Path,default=assets/'banner.cgfx')
p.add_argument('--icon',type=Path,default=assets/'icon.png')
p.add_argument('--audio',type=Path,default=assets/'banner.wav')
p.add_argument('--bannertool',default='bannertool')
p.add_argument('--makerom',default='makerom')
a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
smdh=a.output/'SH-3DS.smdh'; banner=a.output/'SH-3DS.bnr'; cia=a.output/'SH-3DS-v0.9.1.cia'
def run(*args): subprocess.run([str(x) for x in args],check=True)
run(a.bannertool,'makesmdh','-s','SH-3DS','-l','SH-3DS','-p','SH-3DS','-i',a.icon,'-o',smdh)
run(a.bannertool,'makebanner','-ci',a.panel,'-a',a.audio,'-o',banner)
run(a.makerom,'-f','cia','-o',cia,'-elf',a.elf,'-rsf',source/'game.rsf','-icon',smdh,'-banner',banner,'-target','t','-major','0','-minor','9','-micro','0')
run(sys.executable,source/'set_version.py',cia)
run(sys.executable,source/'verify.py',cia,a.elf,banner,smdh,a.audio)
print('CIA',cia,'bytes',cia.stat().st_size,'sha256',hashlib.sha256(cia.read_bytes()).hexdigest(),flush=True)
