"""Exercise production card-image backing stores in an isolated temporary directory."""
from pathlib import Path
import subprocess, tempfile
p=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='sh-banks-') as temp:
    root=Path(temp); exe=root/'banks'
    subprocess.run(['cc','-std=gnu11','-O2','-I'+str(p/'include'),str(p/'tests/card_banks_test.c'),str(p/'source/game_card_image.c'),'-o',str(exe)],check=True)
    subprocess.run([str(exe),str(root/'memcard.mcr'),str(root/'memcard2.mcr')],check=True)
    assert (root/'memcard.mcr').read_bytes()!=(root/'memcard2.mcr').read_bytes()
