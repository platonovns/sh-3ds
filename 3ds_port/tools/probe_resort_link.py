"""Resort and Boat relocatable overlay diagnostic; no game ELF or 3dsx is produced."""
import os
from pathlib import Path
import subprocess
import sys

port = Path(__file__).resolve().parents[1]
build = port / 'build/resort-probe'
prefix = str(Path(os.environ['DEVKITARM']) / 'bin/arm-none-eabi-')
failed = []
for name in ('map5_s02', 'map5_s03', 'map6_s00', 'map6_s01'):
    folder = build / name
    objects = sorted(folder.glob('*.o'))
    sources = list((port.parent / 'src/maps' / name).glob('*.c'))
    sources.append(port.parent / 'pc_port/build_gen/extracted_data' / (name + '_extracted_data.c'))
    expected = {p.stem + '.o' for p in sources}
    if {p.name for p in objects} != expected:
        print(f'{name}: missing or unexpected compiler objects')
        failed.append(name)
        continue
    target = build / (name + '.native.o')
    cmd = [prefix + 'g++', '-r', '-nostdlib', '-march=armv6k', '-mtune=mpcore',
           '-mfloat-abi=hard', '-mtp=soft', *(str(p) for p in objects), '-o', str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    (folder / 'relocatable.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        print(f'{name}: relocatable link failed: {result.stderr}')
        failed.append(name)
        continue
    result = subprocess.run([sys.executable, str(port / 'tools/native_overlay.py'),
                             '--object', str(target), '--map', name], capture_output=True, text=True)
    (folder / 'symbols.log').write_text(result.stdout + result.stderr)
    print(name + ': ' + (result.stdout + result.stderr).strip())
    if result.returncode:
        failed.append(name)
raise SystemExit(bool(failed))
