"""Execute the actual lifetime ARM ELF with the existing retail/NDSP fixtures."""
from pathlib import Path
p=Path(__file__).resolve().parent
fixture=p/'test_stage11a_arm.py'
source=fixture.read_text()
source=source.replace("build/stage11a-control-profile/silenthill_stage11a_control.elf",
                      "build/stage11a-lifetime/silenthill_stage11a_lifetime.elf")
source=source.replace('stage11a-ndsp','stage11a-lifetime-ndsp').replace('stage11a-arm.json','stage11a-lifetime-arm.json')
# The gated SDK measurement branch needs a nonzero synthetic system clock.
source=source.replace("source = source.replace(\"m.call('audio_thread',0)\",", '''source = source.replace("def clock(*_):m.uc.reg_write(UC_ARM_REG_R1,0);ret(0)",
    "clock_tick=[1]\\ndef clock(*_):\\n    clock_tick[0]+=100;m.uc.reg_write(UC_ARM_REG_R1,0);ret(clock_tick[0])")
source = source.replace("m.call('audio_thread',0)",''')
source=source.replace("m.call('stage11a_perf_start')\nm.call('audio_thread',0)",
                      "m.call('game_prof_enable',16)\nm.call('stage11a_perf_start')\nm.call('audio_thread',0)")
exec(compile(source,str(fixture),'exec'),{'__file__':str(fixture),'__name__':'lifetime_arm'})
