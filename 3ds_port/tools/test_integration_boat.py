"""Run the existing Boat skip fixture against the integrated ELF."""
from pathlib import Path
import sys
path = Path(__file__).with_name('test_resort_boat_scene.py')
source = path.read_text().replace("port/'build/resort-probe/resort-probe.elf'", "port/'silenthill_game.elf'")
sys.argv = [str(path), '--skip']
exec(compile(source, str(path), 'exec'), {'__file__': str(path)})
