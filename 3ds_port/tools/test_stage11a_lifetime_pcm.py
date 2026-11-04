"""Reuse the complete byte/state oracle against the private lifetime SPU."""
from pathlib import Path
p=Path(__file__).resolve().parent
fixture=p/'test_stage11a_spu.py'
source=fixture.read_text()
source=source.replace("DEST = PORT / 'build/stage11a-tests'", "DEST = PORT / 'build/stage11a-lifetime-pcm-tests'")
source=source.replace("candidate = prepare(DEST / 'candidate')", "candidate = PORT / 'build/stage11a-lifetime/audio'")
source=source.replace("[('frozen', reference, 0), ('timing', candidate, 0), ('profile', candidate, 1)]",
                      "[('frozen', reference, 0), ('lifetime', candidate, 0)]")
source=source.replace('stage11a-spu-oracle.json','stage11a-lifetime-pcm.json')
exec(compile(source,str(fixture),'exec'),{'__file__':str(fixture),'__name__':'lifetime_pcm_oracle'})
