"""Internal PICA itinerary: real recorder chord, OFF/ON files, HUD and final dump."""
import hashlib,json,os,re,shlex,subprocess
from pathlib import Path
p=Path(__file__).resolve().parents[1];d=p/'build/cpu-recorder-pica';d.mkdir(exist_ok=True)
candidate=p/'build/stage10-cpu-recorder'
fixture=p/'build/stage10-r6-benchmark-8-off'
flags=(p/'build-game/flags').read_text().splitlines()
engine,sdk,ld=map(shlex.split,flags[:3]);prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
raw=subprocess.check_output(['make','-C',str(p),'-f','Makefile.game','-pn'],text=True,stderr=subprocess.DEVNULL)
objects=dict(re.findall(r'^(\w+) := (.*)$',raw,re.M))['OFILES'].split()
frozen={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in objects}
main=(p/'source/main_game.c').read_text().replace('"build_identity.h"','"recorder_test_identity.h"')
injection=r'''
    extern unsigned Game3ds_DevBenchmarkPad(void);
    extern void CpuRecorder_TestCapture(void);
    fps_limit=60;
    unsigned test_pad=Game3ds_DevBenchmarkPad();
    if(test_pad&(1u<<28))CpuRecorder_TestCapture();
    if(test_pad&(1u<<30))game3ds_halt(0,"CPU recorder test complete",0);
    held|=test_pad&65535;
'''
main=main.replace('uint32_t held = hidKeysHeld();','uint32_t held = hidKeysHeld();'+injection)
# Old benchmark objects preserve the proven direct town start/fixed camera.
diagnostic=(fixture/'game_diagnostics.c').read_text()
diagnostic=diagnostic.replace('if(SH_STAGE10_FLASHLIGHT_BENCH)Game_TurnFlashlightOn();else Game_TurnFlashlightOff();',
                            'if(bench_age>=260)Game_TurnFlashlightOn();else Game_TurnFlashlightOff();')
diagnostic=diagnostic.replace('if(bench_age==430){vwGetViewAngle(&bench_view_end);return 1u<<28;}',
    'if(bench_age==150 || bench_age==230 || bench_age==290 || bench_age==390 || bench_age==410)return (1u<<2)|(1u<<7);\n'
    '    if(bench_age==190)return 1u<<28;')
capture=r'''
#include <3ds.h>
#include <stdio.h>
#include <string.h>
void CpuRecorder_TestCapture(void)
{
    u16 w,h;u8 *raw=gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,&w,&h);
    FILE *f=fopen("sdmc:/3ds/silenthill/cpu_recorder_hud.bmp","wb");if(!f)return;
    unsigned char header[54]={0x42,0x4d};u32 v=54+320*240*3;memcpy(header+2,&v,4);
    v=54;memcpy(header+10,&v,4);v=40;memcpy(header+14,&v,4);
    v=320;memcpy(header+18,&v,4);v=240;memcpy(header+22,&v,4);header[26]=1;header[28]=24;
    fwrite(header,1,54,f);
    for(int y=239;y>=0;y--)for(unsigned x=0;x<320;x++) {
        u16 pixel;memcpy(&pixel,raw+2*(x*240+239-y),2);
        unsigned char bgr[3]={(pixel&31)*255/31,((pixel>>5)&63)*255/63,((pixel>>11)&31)*255/31};
        fwrite(bgr,1,3,f);
    }
    fclose(f);
}
'''
digest=hashlib.sha256((main+diagnostic+capture).encode())
for f in (candidate/'silenthill_cpu_recorder.elf',p/'source/game_cpu_recorder.c'):digest.update(f.read_bytes())
identity='stage10.0-dev8-src-'+digest.hexdigest()[:16]
(d/'recorder_test_identity.h').write_text('#define SH_BUILD_ID "'+identity+'"\n')
(d/'main_game.c').write_text(main);(d/'game_diagnostics.c').write_text(diagnostic);(d/'capture.c').write_text(capture)
extra=['-DSH_CPU_AUDIT_RECORDER=1','-I'+str(d)]
subprocess.run([prefix+'gcc',*sdk,*extra,'-c',str(d/'main_game.c'),'-o',str(d/'main_game.o')],check=True)
subprocess.run([prefix+'gcc',*engine,'-DSH_3DS_DEV_SCENE=8','-DSH_STAGE10_FLASHLIGHT_BENCH=0',
    '-c',str(d/'game_diagnostics.c'),'-o',str(d/'game_diagnostics.o')],check=True)
subprocess.run([prefix+'gcc',*sdk,'-c',str(d/'capture.c'),'-o',str(d/'capture.o')],check=True)
replace={str(p/'build-game'/n):str(candidate/n) for n in ('game_native.o','game_profile.o','game_cpu_audit.o')}
replace[str(p/'build-game/main_game.o')]=str(d/'main_game.o')
for n in ('game_boot/game_boot.o','events/game_sys_states.o','events/title.o','sys/game_main.o',
          'bodyprog_8005E0DC.o','game_gpu.o','game_texture_cache.o','render_3ds.o','view/vw_main.o'):
    replace[str(p/'build-game'/n)]=str(fixture/(Path(n).stem+'.o'))
objects=[replace.get(n,n) for n in objects]+[str(candidate/'game_cpu_recorder.o'),str(d/'game_diagnostics.o'),str(d/'capture.o')]
ld=[s.replace(str(p/'silenthill_game.map'),str(d/'diagnostic.map')) for s in ld]
ctrulib=Path(next(v[2:] for v in sdk if v.startswith('-I') and v.endswith('/libctru/include'))).parent
elf=d/'diagnostic.elf'
subprocess.run([prefix+'g++',*ld,*objects,'-L'+str(ctrulib/'lib'),'-lcitro3d','-lctru','-lm','-o',str(elf)],check=True)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in frozen.items())
binary=d/'diagnostic.3dsx'
subprocess.run(['3dsxtool',str(elf),str(binary),'--smdh='+str(p/'silenthill_game.smdh')],check=True)
record=dict(variant='DEVELOPMENT_ONLY',build=identity,size=binary.stat().st_size,
    sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),hardware_accepted=False)
(d/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
