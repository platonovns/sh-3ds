"""Run the existing 636-byte save fixtures against the production ELF."""
from pathlib import Path
port = Path(__file__).resolve().parents[1]
(port/'build/resort-probe').mkdir(parents=True, exist_ok=True)
source = (port/'tools/test_resort_components.py').read_text()
source = source.replace("port/'build/resort-probe/resort-probe.elf'", "port/'silenthill_game.elf'")
source = source.replace("source=source.replace(\"out=port/'build/block3-compile-probe'\", \"out=port/'build/resort-probe'\")", "source=source.replace(\"out=port/'build/block3-compile-probe'\", \"out=port/'build/resort-probe'\"); source=source.replace(\"*(str(p) for p in objects),'-o',str(probe)\", \"*(str(p) for p in objects),str(port/'build-game/memcard.o'),'-o',str(probe)\")")
source = source.replace("str(obj),'-o',str(fixture)", "str(obj),str(port/'build-game/memcard.o'),'-o',str(fixture)")
source = source.split("for seq,(name,index,event)", 1)[0]
exec(compile(source, str(port/'tools/test_resort_components.py'), 'exec'))
