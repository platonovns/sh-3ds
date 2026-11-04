"""Build an emulator-only observer from the frozen/current audio implementation.

Production sources are untouched. NDSP's own capture API records DSP output;
fixed-size memory counters observe pulls, never perform IO in realtime paths.
"""
from pathlib import Path
import os,subprocess,shlex,re,sys,json
p=Path(__file__).resolve().parents[1];root=p.parent
label=sys.argv[1] if len(sys.argv)>1 else 'observe'
dest=p/f'build/stage9-r5-{label}-probe';dest.mkdir(exist_ok=True)
sdk=(p/'source/game_audio_ndsp.c').read_text()
sdk=sdk.replace('static LightLock core_lock;', '''
// Diagnostic only: 6 seconds, 160-frame aligned, at the DSP's 32728.5 Hz.
// libctru writes capture on its normal DSP interrupt clock.
#define PROBE_FRAMES (160u*1228u)
int16_t *stage9_probe_pcm;
ndspWaveBuf stage9_probe_capture;
uint32_t stage9_probe_started,stage9_probe_done;
uint64_t stage9_probe_start_tick;
static LightLock core_lock;''')
sdk=sdk.replace('(void)unused;LightEvent_Signal(&wake);', '''(void)unused;
    if(stage9_probe_started && stage9_probe_capture.offset>=PROBE_FRAMES-160) {
        ndspSetCapture(NULL);stage9_probe_done=1;
    }
    LightEvent_Signal(&wake);''')
sdk=sdk.replace('unsigned queued=0;', '''if(stage9_probe_pcm && !stage9_probe_started && game_xa_is_active()) {
                stage9_probe_started=1;stage9_probe_start_tick=svcGetSystemTick();
                ndspSetCapture(&stage9_probe_capture);
            }
            unsigned queued=0;''')
sdk=sdk.replace('memset(pcm,0,BLOCKS*BLOCK_FRAMES*4);', '''
    stage9_probe_pcm=linearAlloc(PROBE_FRAMES*4);
    if(!stage9_probe_pcm)return -4;
    memset(stage9_probe_pcm,0,PROBE_FRAMES*4);
    memset(&stage9_probe_capture,0,sizeof(stage9_probe_capture));
    stage9_probe_capture.data_pcm16=stage9_probe_pcm;stage9_probe_capture.nsamples=PROBE_FRAMES;
    memset(pcm,0,BLOCKS*BLOCK_FRAMES*4);''')
sdk=sdk.replace('if(pcm){linearFree(pcm);pcm=NULL;}', 'if(stage9_probe_pcm){linearFree(stage9_probe_pcm);stage9_probe_pcm=NULL;}\n    if(pcm){linearFree(pcm);pcm=NULL;}')
(dest/'game_audio_ndsp.c').write_text(sdk)
xa=(p/'source/game_xa.cpp').read_text()
xa=xa.replace('FILE *disc;', '''struct Continuity {
    uint32_t entry,epoch,target,pulls,requested,supplied,startup_missing,missing,eof_padding;
    uint32_t min_before,min_after,deficient_blocks,longest_gap,current_gap;
    uint32_t first_nonzero,last_nonzero,nonzero_started,produced_sectors,cancel_reason;
    uint32_t holes[32][4],hole_count;
};
Continuity continuity, completed[8];uint32_t completed_count;
FILE *disc;''')
xa=xa.replace('++s.epoch;s.lba=lba;', '''continuity={};continuity.entry=d.last_request;continuity.epoch=s.epoch+1;
    continuity.target=ticks*735u;continuity.min_before=continuity.min_after=UINT32_MAX;
    ++s.epoch;s.lba=lba;''')
xa=xa.replace('event(8,reason,s.played,s.count);', '''if(s.active) {
        continuity.cancel_reason=reason;
        if(completed_count<8)completed[completed_count++]=continuity;
    }
    event(8,reason,s.played,s.count);''')
xa=xa.replace('++d.decoded_sectors;', '++continuity.produced_sectors;\n            ++d.decoded_sectors;')
xa=xa.replace('uint32_t n=frames<s.count?frames:s.count;', '''uint32_t n=frames<s.count?frames:s.count;
    ++continuity.pulls;
    uint32_t clock=continuity.requested;continuity.requested+=frames;continuity.supplied+=n;
    if(s.played && !s.done && s.count<continuity.min_before)continuity.min_before=s.count;
    uint32_t missing=frames-n;
    if(missing && !s.done) {
        if(s.played) {
            ++continuity.deficient_blocks;continuity.missing+=missing;continuity.current_gap+=missing;
            if(continuity.current_gap>continuity.longest_gap)continuity.longest_gap=continuity.current_gap;
            if(continuity.hole_count<32) {
                auto &h=continuity.holes[continuity.hole_count++];
                h[0]=clock+n;h[1]=missing;h[2]=s.matched;h[3]=next_lba;
            }
        } else continuity.startup_missing+=missing;
    } else {continuity.current_gap=0;if(missing)continuity.eof_padding+=missing;}
    if(s.played && !s.done && s.count-n<continuity.min_after)continuity.min_after=s.count-n;''')
xa=xa.replace('d.matrix_nonzero+=(out[i*2]!=0)+(out[i*2+1]!=0);', '''if(out[i*2] || out[i*2+1]) {
            if(!continuity.nonzero_started){continuity.nonzero_started=1;continuity.first_nonzero=clock+i;}
            continuity.last_nonzero=clock+i;
        }
        d.matrix_nonzero+=(out[i*2]!=0)+(out[i*2+1]!=0);''')
(dest/'game_xa.cpp').write_text(xa)
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
flags=(p/'build-game/flags').read_text().splitlines()
sdkflags=shlex.split(flags[1]);engine=shlex.split(flags[0]);engine=[v for v in engine if v!='-std=gnu11']
engine+=['-std=gnu++17','-fno-exceptions','-fno-rtti','-I'+str(p/'build/audio'),'-I'+str(root/'pc_port/PsyCross/src/audio')]
subprocess.run([prefix+'gcc',*sdkflags,'-c',str(dest/'game_audio_ndsp.c'),'-o',str(dest/'game_audio_ndsp.o')],check=True)
subprocess.run([prefix+'g++',*engine,'-c',str(dest/'game_xa.cpp'),'-o',str(dest/'game_xa.o')],check=True)
# Read the exact resolved object list from make without rebuilding or changing it.
raw=subprocess.check_output(['make','-C',str(p),'-f','Makefile.game','-pn'],text=True,stderr=subprocess.DEVNULL)
variables=dict(re.findall(r'^(\w+) := (.*)$',raw,re.M))
objects=variables['OFILES'].split()
for i,name in enumerate(objects):
    if Path(name).name in ('game_audio_ndsp.o','game_xa.o'):objects[i]=str(dest/Path(name).name)
ld=shlex.split(variables['LDFLAGS'])
ld=[v.replace(str(p/'silenthill_game.map'),str(dest/'probe.map')) for v in ld]
ctrulib=Path(next(v[2:] for v in sdkflags if v.startswith('-I') and v.endswith('/libctru/include'))).parent
subprocess.run([prefix+'g++',*ld,*objects,'-L'+str(ctrulib/'lib'),'-lcitro3d','-lctru','-lm','-o',str(dest/'probe.elf')],check=True)
subprocess.run(['3dsxtool',str(dest/'probe.elf'),str(dest/'probe.3dsx'),'--smdh='+str(p/'silenthill_game.smdh')],check=True)
(p/f'build/stage9-r5-{label}-symbols.txt').write_text(subprocess.check_output([prefix+'nm','-n',str(dest/'probe.elf')],text=True))
print('Emulator observer:',dest/'probe.3dsx')
