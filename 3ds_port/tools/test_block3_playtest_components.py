"""Run the earlier component suite against the full playtest ELF."""
from pathlib import Path
import os

port = Path(__file__).resolve().parents[1]
os.environ.setdefault('SH_BLOCK3_ELF', str(port / 'silenthill_game.elf'))
(port / 'build/block3-compile-probe').mkdir(parents=True, exist_ok=True)
source_path = port / 'tools/test_block3_components.py'
source = source_path.read_text().replace(
    "*(str(p) for p in objects),'-o',str(probe)",
    "*(str(p) for p in objects), str(port/'build-game/memcard.o'), '-Wl,--allow-multiple-definition','-o',str(probe)")
exec(compile(source, str(source_path), 'exec'))
