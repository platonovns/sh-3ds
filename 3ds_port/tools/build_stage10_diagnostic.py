"""Relink a development scenario without changing production object files.

Build the normal ELF first. Default output is internal ELF for ARM tests;
--package also makes a clearly marked emulator-only development 3DSX.
This test artifact is not a hardware candidate and does not replace delivery.
"""
import argparse,hashlib,json,os,re,shlex,subprocess,sys,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--scene',type=int,choices=(1,2,3,4,5,6,7,8,9),required=True)
ap.add_argument('--package',action='store_true')
ap.add_argument('--combat-pad',action='store_true',help='Emulator-only physical aim/fire fixture (scene 2)')
ap.add_argument('--menu-pad',action='store_true',help='Original Status/Map pad itinerary and native readback captures (scene 5)')
ap.add_argument('--without-map',action='store_true',help='Menu scenario without possession; original unavailable-map path')
ap.add_argument('--renderer-reference-r2',action='store_true',help='Performance comparison: same game with frozen R2 renderer')
ap.add_argument('--renderer-reference-r5',action='store_true',help='Performance comparison: same game with accepted R5 renderer')
ap.add_argument('--cafe-exit-pad',action='store_true',help='Original combat/door/MAP2 itinerary with actual feedback captures (scene 2)')
ap.add_argument('--world-capture',action='store_true',help='Stationary native PICA readback and clean exit (scenes 7/9)')
ap.add_argument('--school-infirmary',action='store_true',help='Nearby school save-room PICA fixture; no save/item/flag writes')
ap.add_argument('--flashlight-benchmark',choices=('off','on'),help='R6 fixed-pose dark-town/indoor benchmark, 60-mode')
ap.add_argument('--town-enemy',choices=('air','groaner'),help='Original nearby outdoor encounter, physical aim/fire, 60-mode')
ap.add_argument('--memory-audit',action='store_true',help='Development-only exact linear allocation ledger')
ap.add_argument('--memory-stress',action='store_true',help='Six original house door and Status/Map cycles, nearby fixture starts')
ap.add_argument('--fade-benchmark',action='store_true',help='Per-present resource/decode/sync timeline for the original Cafe exit')
a=ap.parse_args()
assert not a.combat_pad or a.scene==2
assert not a.menu_pad or a.scene==5
assert not a.without_map or a.menu_pad
assert not a.cafe_exit_pad or a.scene in (2,6) and not a.combat_pad and not a.menu_pad
assert not a.world_capture or a.scene in (7,9) and not a.combat_pad and not a.menu_pad and not a.cafe_exit_pad
assert not a.school_infirmary or a.scene==7 and a.world_capture
assert not a.flashlight_benchmark or a.scene in (7,8) and not any((a.world_capture,a.menu_pad,a.cafe_exit_pad,a.combat_pad))
assert not a.town_enemy or a.scene==8 and a.flashlight_benchmark=='off'
assert not a.memory_stress or a.scene==5 and a.memory_audit and not any((a.menu_pad,a.cafe_exit_pad,a.flashlight_benchmark,a.world_capture))
assert not a.fade_benchmark or a.scene==6 and a.cafe_exit_pad
assert not (a.renderer_reference_r2 and a.renderer_reference_r5)
dest=p/(f'build/stage10-dev-scene-{a.scene}'+('-combat' if a.combat_pad else '-menus' if a.menu_pad else '-exit' if a.cafe_exit_pad else '-world' if a.world_capture else '')+('-infirmary' if a.school_infirmary else '')+('-no-map' if a.without_map else '')+('-renderer-r2' if a.renderer_reference_r2 else ''));dest.mkdir(exist_ok=True)
if a.flashlight_benchmark:
    dest=p/f'build/stage10-r6-benchmark-{a.scene}-{a.flashlight_benchmark}';dest.mkdir(exist_ok=True)
if a.town_enemy:
    dest=dest.with_name(dest.name+'-'+a.town_enemy);dest.mkdir(exist_ok=True)
if a.memory_audit:
    dest=dest.with_name(dest.name+'-memory');dest.mkdir(exist_ok=True)
if a.memory_stress:
    dest=dest.with_name(dest.name+'-stress');dest.mkdir(exist_ok=True)
if a.fade_benchmark:
    dest=dest.with_name(dest.name+'-fade');dest.mkdir(exist_ok=True)
if a.renderer_reference_r5:
    dest=dest.with_name(dest.name+'-renderer-r5');dest.mkdir(exist_ok=True)
base=p/'silenthill_game.elf'
base_sha=hashlib.sha256(base.read_bytes()).hexdigest()
identity=re.search(r'"(stage[^"]+)"',(p/'build/build_identity.h').read_text())[1]
assert identity.encode() in base.read_bytes(),'Build the normal ELF after prepare first'
flags=(p/'build-game/flags').read_text().splitlines()
assert 'SH_3DS_DEV_' not in '\n'.join(flags),'Base objects must be production objects'
engine=shlex.split(flags[0]);sdk=shlex.split(flags[1]);extra=f'-DSH_3DS_DEV_SCENE={a.scene}'
prefix=str(Path(os.environ['DEVKITARM'])/'bin/arm-none-eabi-')
if a.combat_pad:extra+=' -DSH_STAGE10_COMBAT_PAD=1'
if a.menu_pad:extra+=' -DSH_STAGE10_MENU_PAD=1'
if a.without_map:extra+=' -DSH_STAGE10_NO_MAP=1'
if a.cafe_exit_pad:extra+=' -DSH_STAGE10_CAFE_EXIT_PAD=1'
if a.world_capture:extra+=' -DSH_STAGE10_WORLD_CAPTURE=1'
if a.school_infirmary:extra+=' -DSH_STAGE10_SCHOOL_INFIRMARY=1'
if a.flashlight_benchmark:extra+=' -DSH_STAGE10_FLASHLIGHT_BENCH='+str(int(a.flashlight_benchmark=='on'))
if a.town_enemy:extra+=' -DSH_STAGE10_TOWN_ENEMY='+str(1 if a.town_enemy=='air' else 2)
if a.memory_audit:extra+=' -DSH_STAGE10_MEMORY_AUDIT=1'
if a.memory_stress:extra+=' -DSH_STAGE10_MEMORY_STRESS=1'
if a.fade_benchmark:extra+=' -DSH_STAGE10_FADE_BENCH=1'
reference=None
if a.renderer_reference_r2:
    receipt=json.loads((p/'reports/stage10-r2-freeze.json').read_text())
    archive=root/receipt['archive'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['archive_sha256']
    with zipfile.ZipFile(archive) as frozen:reference=frozen.read('3ds_port/source/render_3ds.c')
    extra+=' -DSH_STAGE10_RENDERER_REFERENCE_R2=1'
if a.renderer_reference_r5:
    receipt=json.loads((p/'reports/stage10-r5-freeze.json').read_text())
    archive=root/receipt['archive'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['archive_sha256']
    with zipfile.ZipFile(archive) as frozen:reference=frozen.read('3ds_port/source/render_3ds.c')
    extra+=' -DSH_STAGE10_RENDERER_REFERENCE_R5=1'
raw=subprocess.check_output(['make','-C',str(p),'-f','Makefile.game','-pn'],text=True,stderr=subprocess.DEVNULL)
variables=dict(re.findall(r'^(\w+) := (.*)$',raw,re.M))
objects=variables['OFILES'].split()
digest=hashlib.sha256()
object_hashes={}
for name in objects:
    data=Path(name).read_bytes();digest.update(data);object_hashes[name]=hashlib.sha256(data).hexdigest()
digest.update((identity+extra).encode());digest.update((p/'source/game_diagnostics.c').read_bytes())
if reference is not None:digest.update(reference)
for source in (root/'src/bodyprog/game_boot/game_boot.c',root/'src/bodyprog/events/game_sys_states.c',
               root/'src/bodyprog/events/title.c',root/'src/bodyprog/sys/game_main.c',p/'source/main_game.c',
               root/'src/bodyprog/bodyprog_8005E0DC.c',p/'source/game_gpu.c',
               p/'source/game_texture_cache.c',p/'source/render_3ds.c',Path(__file__)):
    digest.update(source.read_bytes())
for directory in (p/'include',root/'include'):
    for source in sorted(directory.rglob('*.h')):digest.update(source.read_bytes())
dev_id=f'stage10.0-dev{a.scene}-src-'+digest.hexdigest()[:16]
(dest/'stage10_dev_identity.h').write_text('#define SH_BUILD_ID "'+dev_id+'"\n')
main=(p/'source/main_game.c').read_text().replace('"build_identity.h"','"stage10_dev_identity.h"')
if a.fade_benchmark:
    needle='static uint32_t fade_frames[192][10],fade_count;'
    assert main.count(needle)==1
    main=main.replace(needle,needle+'\nstatic uint32_t fade_cost[192][16];')
    needle='memcpy(row,values,sizeof(values));'
    assert main.count(needle)==1
    main=main.replace(needle,needle+'\n        extern void Game3ds_DevTimelineSnapshot(uint32_t *out); Game3ds_DevTimelineSnapshot(fade_cost[(fade_count-1)%192]);')
    needle='if(fputs("report_complete=1\\n",out)<0'
    assert main.count(needle)==1
    main=main.replace(needle,'extern void Game3ds_DevTimelineReport(FILE *out); Game3ds_DevTimelineReport(out);\n    '+needle)
    main+='''
void Game3ds_DevTimelineReport(FILE *out)
{
    fprintf(out,"fade_cost_schema=update_us,world_us,primitive_us,decode_us,upload_us,resource_us,io_us,sync_us,vblank_us,report_us,command_us,present_us,reads,read_bytes,raw_reads,raw_bytes\\n");
    unsigned start=fade_count>192?fade_count-192:0;
    for(unsigned i=start;i<fade_count;i++) {
        fprintf(out,"fade_cost_%u=",i-start);
        for(unsigned j=0;j<16;j++)fprintf(out,"%s%lu",j?",":"",(unsigned long)fade_cost[i%192][j]);
        fputc('\\n',out);
    }
}
'''
if a.memory_audit:
    needle='if(fputs("report_complete=1\\n",out)<0'
    assert main.count(needle)==1
    main=main.replace(needle,'extern void Game3ds_DevMemoryReport(FILE *out); Game3ds_DevMemoryReport(out);\n    '+needle)
    needle='uint32_t held = hidKeysHeld();'
    assert main.count(needle)==1
    main=main.replace(needle,needle+'\n    extern void Game3ds_DevMemorySample(void); Game3ds_DevMemorySample();')
if a.cafe_exit_pad or a.flashlight_benchmark or a.memory_stress:
    needle='if(fputs("report_complete=1\\n",out)<0'
    assert main.count(needle)==1
    main=main.replace(needle,'extern void Game3ds_DevReport(FILE *out); Game3ds_DevReport(out);\n    '+needle)
if a.combat_pad:
    needle='if (diagnostic_stage6 && game_state==11)'
    assert main.count(needle)==1
    main=main.replace(needle,'if (diagnostic_gameplay && game_state==11 && player_state==0) { held|=KEY_ZR; if(input_polls%20<2)held|=KEY_B; } else '+needle)
    needle='if(fputs("report_complete=1\\n",out)<0'
    assert main.count(needle)==1
    main=main.replace(needle,'extern void Game3ds_DevReport(FILE *out); Game3ds_DevReport(out);\n    '+needle)
(dest/'main_game.c').write_text(main)
if a.menu_pad or a.cafe_exit_pad or a.world_capture or a.flashlight_benchmark or a.memory_stress:
    needle='uint32_t game3ds_read_pad(void)'
    assert main.count(needle)==1
    main=main.replace(needle,'static void dev_menu_capture(const char *name);\n'+needle)
    needle='uint32_t held = hidKeysHeld();'
    assert main.count(needle)==1
    injection='''
    extern unsigned Game3ds_DevMenuPad(void);
    unsigned itinerary=Game3ds_DevMenuPad();
    if(itinerary&(1u<<28))dev_menu_capture("dev5_status.bmp");
    if(itinerary&(1u<<29))dev_menu_capture("dev5_map.bmp");
    if(itinerary&(1u<<30))game3ds_halt(0,"dev Status/Map itinerary complete",0);
    held|=itinerary&65535;
'''
    if a.cafe_exit_pad:injection='''
    extern unsigned Game3ds_DevCafePad(void);
    unsigned itinerary=Game3ds_DevCafePad();
    unsigned capture=itinerary>>28;
    if(capture==1)dev_menu_capture("dev2_feedback_room_early.bmp");
    if(capture==2)dev_menu_capture("dev2_feedback_room_late.bmp");
    if(capture==3)dev_menu_capture("dev2_feedback_load_early.bmp");
    if(capture==4)dev_menu_capture("dev2_feedback_load_late.bmp");
    if(capture==5)game3ds_halt(0,"dev original Cafe exit complete",0);
    held|=itinerary&65535;
'''
    if a.world_capture:injection='''
    extern unsigned Game3ds_DevWorldPad(void);
    unsigned itinerary=Game3ds_DevWorldPad();
    if(itinerary&(1u<<28))dev_menu_capture("dev_world_feedback.bmp");
    if(itinerary&(1u<<30))game3ds_halt(0,"dev original world capture complete",0);
    held|=itinerary&65535;
'''
    if a.flashlight_benchmark:injection='''
    extern unsigned Game3ds_DevBenchmarkPad(void);
    fps_limit=60;
    unsigned itinerary=Game3ds_DevBenchmarkPad();
    if(itinerary&(1u<<28))dev_menu_capture("dev_r6_feedback_benchmark.bmp");
    if(itinerary&(1u<<30))game3ds_halt(0,"dev R6 flashlight benchmark complete",0);
    held|=itinerary&65535;
'''
    if a.memory_stress:injection='''
    extern unsigned Game3ds_DevStressPad(void);
    unsigned itinerary=Game3ds_DevStressPad();
    if(itinerary&(1u<<30)){dev_menu_capture("dev_r6_feedback_memory.bmp");game3ds_halt(0,"dev R6 memory stress complete",0);}
    held|=itinerary&65535;
'''
    main=main.replace(needle,needle+injection)
    main+='''
static void dev_menu_capture(const char *name)
{
    game3ds_gpu_sync();
    unsigned width=strstr(name,"feedback")?400:320;
    uint16_t *pixels=malloc(width*240*2);
    if(!pixels || !render3ds_read_psx(0,0,width,240,pixels,width))game3ds_halt(462,"dev menu capture",0);
    char path[128];snprintf(path,sizeof(path),"sdmc:/3ds/silenthill/%s",name);
    FILE *f=fopen(path,"wb");if(!f)game3ds_halt(462,"dev capture open",0);
    unsigned char header[54]={0x42,0x4d};
    uint32_t value=54+width*240*3;memcpy(header+2,&value,4);value=54;memcpy(header+10,&value,4);
    value=40;memcpy(header+14,&value,4);value=width;memcpy(header+18,&value,4);value=240;memcpy(header+22,&value,4);
    header[26]=1;header[28]=24;fwrite(header,1,54,f);
    for(int y=239;y>=0;y--)for(unsigned x=0;x<width;x++) {
        unsigned word=pixels[y*width+x];unsigned char bgr[3]={((word>>10)&31)*255/31,((word>>5)&31)*255/31,(word&31)*255/31};
        fwrite(bgr,1,3,f);
    }
    fclose(f);free(pixels);
}
'''
    (dest/'main_game.c').write_text(main)
sources={'game_boot/game_boot.o':root/'src/bodyprog/game_boot/game_boot.c',
         'events/game_sys_states.o':root/'src/bodyprog/events/game_sys_states.c',
         'events/title.o':root/'src/bodyprog/events/title.c',
         'sys/game_main.o':root/'src/bodyprog/sys/game_main.c',
         'bodyprog_8005E0DC.o':root/'src/bodyprog/bodyprog_8005E0DC.c',
         'game_gpu.o':p/'source/game_gpu.c',
         'game_texture_cache.o':p/'source/game_texture_cache.c',
         'render_3ds.o':p/'source/render_3ds.c',
         'main_game.o':dest/'main_game.c'}
if a.flashlight_benchmark and a.scene==8:
    view=(root/'src/bodyprog/view/vw_main.c').read_text()
    needle='void vwSetViewInfoDirectMatrix(GsCOORDINATE2* pcoord, const MATRIX* cammat) // 0x80048CF0\n{'
    assert view.count(needle)==1
    view=view.replace(needle,needle+'''
    extern const MATRIX *Game3ds_DevBenchmarkView(void);
    const MATRIX *fixed=Game3ds_DevBenchmarkView();if(fixed)cammat=fixed;
''')
    source=dest/'vw_main.c';source.write_text(view);sources['view/vw_main.o']=source
if a.fade_benchmark:
    profile=(p/'source/game_profile.c').read_text()+'''
void Game3ds_DevTimelineSnapshot(uint32_t *out)
{
    static const unsigned categories[]={GP_UPDATE,GP_WORLD,GP_PRIMITIVE,GP_DECODE,GP_UPLOAD,GP_RESOURCE,GP_IO,GP_SYNC,GP_VBLANK,GP_REPORT,GP_COMMAND,GP_PRESENT};
    for(unsigned i=0;i<12;i++)out[i]=current.ticks[categories[i]]/(TICKS_PER_MS/1000.0);
    out[12]=current.count[GC_READS];out[13]=current.count[GC_READ_BYTES];
    out[14]=current.count[GC_RAW_READS];out[15]=current.count[GC_RAW_BYTES];
}
'''
    source=dest/'game_profile.c';source.write_text(profile);sources['game_profile.o']=source
if reference is not None:
    source=dest/'render_3ds.c';source.write_bytes(reference);sources['render_3ds.o']=source
if a.flashlight_benchmark:
    render=reference.decode() if reference is not None else (p/'source/render_3ds.c').read_text()
    needle='static bool readback_surface(void)\n{'
    assert render.count(needle)==1
    render=render.replace(needle,'''static uint64_t bench_readback_ticks;
static unsigned bench_readback_calls;
static bool bench_readback_surface_impl(void);
static bool readback_surface(void)
{
    uint64_t begin=svcGetSystemTick();
    bool result=bench_readback_surface_impl();
    bench_readback_ticks+=svcGetSystemTick()-begin;bench_readback_calls++;
    return result;
}
void Game3ds_DevReadbackReset(void) {bench_readback_ticks=0;bench_readback_calls=0;}
void Game3ds_DevReadbackReport(FILE *out)
{
    fprintf(out,"r6_readback_calls=%u\\nr6_readback_total_ticks=%llu\\n",bench_readback_calls,(unsigned long long)bench_readback_ticks);
}
static bool bench_readback_surface_impl(void)
{''')
    source=dest/'render_3ds.c';source.write_text(render);sources['render_3ds.o']=source
replacements={}
compile_headers=hashlib.sha256()
for directory in (p/'include',root/'include',root/'pc_port/include',p/'build/psycross/include'):
    for header in sorted(directory.rglob('*.h')):
        compile_headers.update(header.as_posix().encode()+header.read_bytes())
for key,src in sources.items():
    obj=dest/(Path(key).stem+'.o');ff=sdk if key in ('main_game.o','render_3ds.o') else engine
    signature=hashlib.sha256(compile_headers.digest()+src.read_bytes()+repr((ff,extra)).encode()+
        ((dest/'stage10_dev_identity.h').read_bytes() if key=='main_game.o' else b'')).hexdigest()
    sig=obj.with_suffix('.signature')
    if not obj.exists() or not sig.exists() or sig.read_text()!=signature:
        subprocess.run([prefix+'gcc',*ff,*extra.split(),'-c',str(src),'-o',str(obj)],check=True)
        sig.write_text(signature)
    replacements[str(p/'build-game'/key)]=str(obj)
obj=dest/'game_diagnostics.o'
diagnostics=p/'source/game_diagnostics.c'
diagnostic_source=diagnostics.read_text()
if a.memory_stress:
    diagnostic_source=diagnostic_source.replace('    enter_pending=1;','    Savegame_EventFlagSet(EventFlag_153); /* Prepared unlocked house; not progression evidence. */\n    enter_pending=1;')
    diagnostics=dest/'game_diagnostics.c'
    diagnostics.write_text(diagnostic_source+'''
#include "bodyprog/screen/screen_fade.h"
#include <stdio.h>
extern unsigned int linearSpaceFree(void);
static unsigned stress_phase,stress_age,stress_laps,stress_polls,stress_maps,stress_rooms;
static unsigned stress_free[6];
static void stress_place(unsigned point_index)
{
    const s_MapPoint2d *p=&g_MapOverlayHdr.mapPoints[point_index];
    q3_12 yaw=Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(p->triggerParam0)+2048);
    g_SysWork.playerWork.player.position.vx=p->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
    g_SysWork.playerWork.player.position.vz=p->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));
    g_SysWork.playerWork.player.rotation.vy=yaw;Game_PlayerHeightUpdate();
}
unsigned Game3ds_DevStressPad(void)
{
    static unsigned previous_state=~0u,state_age;
    stress_polls++;
    unsigned state=g_GameWork.gameState;
    if(state!=previous_state){previous_state=state;state_age=0;}else state_age++;
    if(stress_polls>12000)game3ds_halt(462,"R6 memory itinerary stalled",stress_phase);
    if(state==GameState_InGame) {
        if(g_SysWork.sysState!=SysState_Gameplay || g_Player_DisableControl)
            return (stress_polls%20<2?2:0)|(stress_polls%120==0?1u<<3:0);
        stress_age++;
        if(stress_phase==0 && stress_age>60){stress_place(22);stress_phase=1;stress_age=0;}
        if(stress_phase==1) {
            if(g_SavegamePtr->mapRoomIdx==37){stress_rooms++;stress_phase=2;stress_age=0;}
            else return stress_polls%20<2?2:0;
        }
        if(stress_phase==2 && stress_age>30){stress_place(23);stress_phase=3;stress_age=0;}
        if(stress_phase==3) {
            if(g_SavegamePtr->mapRoomIdx==2){stress_rooms++;stress_phase=4;stress_age=0;}
            else return stress_polls%20<2?2:0;
        }
        if(stress_phase==4 && stress_age>30){stress_phase=5;return 1u<<10;}
        if(stress_phase==6 && state_age>60) {
            stress_free[stress_laps++]=linearSpaceFree();stress_phase=0;stress_age=0;
            if(stress_laps==6)return 1u<<30;
        }
    }
    if(state==GameState_InventoryScreen && ScreenFade_IsNone() && state_age>40) {
        if(stress_phase==6)return state_age%30==0?1u<<10:0;
        if(state_age%30==0) {
            if(g_Inventory_SelectionId==InventorySelectionId_Item)return 1u<<7;
            if(g_Inventory_SelectionId==InventorySelectionId_Exit)return 1u<<4;
            if(g_Inventory_SelectionId==InventorySelectionId_Map)return 2;
        }
    }
    if(state==GameState_PaperMapScreen && state_age>90) {
        if(stress_phase!=6)stress_maps++;
        stress_phase=6;return 1;
    }
    return 0;
}
void Game3ds_DevReport(FILE *out)
{
    fprintf(out,"r6_stress_phase=%u\\nr6_stress_laps=%u\\nr6_stress_rooms=%u\\nr6_stress_maps=%u\\nr6_stress_polls=%u\\n",
        stress_phase,stress_laps,stress_rooms,stress_maps,stress_polls);
    for(unsigned i=0;i<stress_laps;i++)fprintf(out,"r6_stress_free_%u=%u\\n",i,stress_free[i]);
}
''')
if a.flashlight_benchmark:
    if a.scene==8 and not a.town_enemy:
        diagnostic_source=diagnostic_source.replace('    enter_pending=1;','    Savegame_EventFlagSet(EventFlag_159);\n    Savegame_EventFlagClear(EventFlag_134);\n    enter_pending=1;')
    diagnostics=dest/'game_diagnostics.c'
    diagnostics.write_text(diagnostic_source+'''
#include "game_profile.h"
#include "bodyprog/gfx/map_effects.h"
#include "bodyprog/view/vw_main.h"
#include "bodyprog/game_boot/fs_chara_anim.h"
#include <stdio.h>
static unsigned bench_age;
static uint64_t bench_started;
static int bench_x,bench_z,bench_yaw;
static SVECTOR bench_view_start,bench_view_end;
static unsigned bench_enemy_frames,bench_enemy_peak;
const MATRIX *Game3ds_DevBenchmarkView(void)
{
    static MATRIX fixed;static unsigned ready;
    if(SH_3DS_DEV_SCENE!=8 || bench_age<80)return NULL;
    if(!ready) {
        /* Fixed development look-at, through the original view-matrix setter.
         * Camera simulation still executes; its easing cannot change this pair. */
        VECTOR3 target=g_SysWork.playerWork.player.position,pos=target;
        pos.vx+=Q12_MULT_PRECISE(Q12(5.0f),Math_Sin(2600));
        pos.vz+=Q12_MULT_PRECISE(Q12(5.0f),Math_Cos(2600));
        pos.vy-=Q12(3.0f);target.vy-=Q12(1.0f);
        int dx=Q12_TO_Q8(target.vx-pos.vx),dy=Q12_TO_Q8(target.vy-pos.vy),dz=Q12_TO_Q8(target.vz-pos.vz);
        SVECTOR rot={ratan2(-dy,Math_Vector2MagCalc(dx,dz)),ratan2(dx,dz),0,0};
        Math_RotMatrixZxyNeg(&rot,&fixed);
        fixed.t[0]=Q12_TO_Q8(pos.vx);fixed.t[1]=Q12_TO_Q8(pos.vy);fixed.t[2]=Q12_TO_Q8(pos.vz);ready=1;
    }
    return &fixed;
}
unsigned Game3ds_DevBenchmarkPad(void)
{
    static unsigned polls;polls++;
    if(g_GameWork.gameState!=GameState_InGame)return 0;
    if(g_SysWork.sysState!=SysState_Gameplay || g_Player_DisableControl)
        return (polls%20<2?2:0)|(polls%120==0?1u<<3:0);
    if(SH_STAGE10_FLASHLIGHT_BENCH)Game_TurnFlashlightOn();else Game_TurnFlashlightOff();
    bench_age++;
    if(bench_age==30) {
        if(SH_3DS_DEV_SCENE==8) {
            /* Just west of the real Cafe exit (22.2,56.5), on the street. */
            g_SysWork.playerWork.player.position.vx=Q12(18.0f);
            g_SysWork.playerWork.player.position.vz=Q12(56.5f);
            Game_PlayerHeightUpdate();
        }
    }
    if(bench_age==80) {
        SVECTOR view;vwGetViewAngle(&view);
        g_SysWork.playerWork.player.rotation.vy=SH_3DS_DEV_SCENE==8?2600:(view.vy+2048)&4095;
        bench_x=g_SysWork.playerWork.player.position.vx;
        bench_z=g_SysWork.playerWork.player.position.vz;
        bench_yaw=g_SysWork.playerWork.player.rotation.vy;
    }
    if(bench_age==120) {
        extern void Game3ds_DevReadbackReset(void);
        Game3ds_DevReadbackReset();bench_started=game3ds_ticks();
        vwGetViewAngle(&bench_view_start);
    }
#ifdef SH_STAGE10_TOWN_ENEMY
    if(bench_age==90) {
        /* Original load/spawn entry only; AI initializes health and animation. */
        s_SubCharacter *p=&g_SysWork.playerWork.player;
        int kind=SH_STAGE10_TOWN_ENEMY==1?Chara_AirScreamer:Chara_Groaner;
        for(unsigned i=0;i<NPC_COUNT_MAX;i++)g_SysWork.npcs[i].model.charaId=Chara_None;
        g_SysWork.npcFlags=0;g_SysWork.field_228C[0]=0;
        int anim=0;
        for(unsigned i=1;i<CHARA_GROUP_COUNT;i++)if(g_CharaModelAnimsData[i].activeCharaId==kind)anim=i;
        if(!anim) {
            Chara_Load(SH_STAGE10_TOWN_ENEMY-1,kind,g_SysWork.npcBoneCoordBuffer,0,NULL,NULL);
            Chara_ProcessLoads();
            for(unsigned i=1;i<CHARA_GROUP_COUNT;i++)if(g_CharaModelAnimsData[i].activeCharaId==kind)anim=i;
        }
        if(!anim)game3ds_halt(462,"dev original enemy model missing",kind);
        Chara_BonesInit(anim-1);
        unsigned slot=Chara_Spawn(kind,0,p->position.vx+Q12_MULT_PRECISE(Q12(4.0f),Math_Sin(p->rotation.vy)),
            p->position.vz+Q12_MULT_PRECISE(Q12(4.0f),Math_Cos(p->rotation.vy)),(p->rotation.vy+2048)&4095,0);
        if(slot>=NPC_COUNT_MAX)game3ds_halt(462,"dev original enemy spawn",slot);
    }
#endif
    if(bench_age==430){vwGetViewAngle(&bench_view_end);return 1u<<28;}
    if(bench_age==450)return 1u<<30;
#ifdef SH_STAGE10_TOWN_ENEMY
    unsigned active=0;
    for(unsigned i=0;i<NPC_COUNT_MAX;i++)
        if(g_SysWork.npcs[i].model.charaId==(SH_STAGE10_TOWN_ENEMY==1?Chara_AirScreamer:Chara_Groaner) && g_SysWork.npcs[i].health>0)active++;
    if(bench_age>=120 && active)bench_enemy_frames++;
    if(active>bench_enemy_peak)bench_enemy_peak=active;
    if(bench_age>=120)return (1u<<15)|(bench_age%20<2?2:0);
#endif
    return 0;
}
void Game3ds_DevReport(FILE *out)
{
    extern void Game3ds_DevReadbackReport(FILE *out);
    fprintf(out,"r6_benchmark_flashlight=%u\\nr6_benchmark_age=%u\\nr6_benchmark_pose=%d,%d,%d\\n",
        SH_STAGE10_FLASHLIGHT_BENCH,bench_age,bench_x,bench_z,bench_yaw);
    fprintf(out,"r6_benchmark_measured_frames=%u\\nr6_benchmark_total_ticks=%llu\\n",bench_age>120?bench_age-120:0,
        (unsigned long long)(bench_started?game3ds_ticks()-bench_started:0));
    Game3ds_DevReadbackReport(out);
    fprintf(out,"r6_benchmark_camera=%d,%d,%d,%d,%d,%d\\n",bench_view_start.vx,bench_view_start.vy,bench_view_start.vz,
        bench_view_end.vx,bench_view_end.vy,bench_view_end.vz);
    fprintf(out,"r6_enemy_frames=%u\\nr6_enemy_peak=%u\\nr6_enemy_final_ammo=%u\\n",bench_enemy_frames,bench_enemy_peak,g_SysWork.playerCombat.currentWeaponAmmo);
}
''')
if a.scene==6:
    diagnostic_source=diagnostic_source.replace('    Savegame_EventFlagSet(EventFlag_M0S01_PickupPocketRadio);','    /* Radio is picked up through the original event AFTER combat. */')
    diagnostic_source=diagnostic_source.replace('        g_SavegamePtr->items[i].id_0=ids[i];','        if(ids[i]==InvItemId_PocketRadio)continue;\n        g_SavegamePtr->items[i].id_0=ids[i];')
    diagnostics=dest/'game_diagnostics.c';diagnostics.write_text(diagnostic_source)
if a.menu_pad:
    diagnostics=dest/'game_diagnostics.c'
    diagnostics.write_text(diagnostic_source+'''
#include "bodyprog/screen/screen_fade.h"
unsigned Game3ds_DevMenuPad(void)
{
    static unsigned state=~0u,age,phase;
    if(state!=(unsigned)g_GameWork.gameState){state=g_GameWork.gameState;age=0;}else age++;
    if(state==GameState_InGame) {
        if(g_SysWork.sysState==SysState_EventCallback)return age%90==0?1u<<3:0;
        if(g_SysWork.sysState!=SysState_Gameplay)return age%90==0?2:0;
        if(phase==0 && age>60){phase=1;return 1u<<10;}
        if(phase==3 && age>60)return 1u<<30;
    }
    if(state==GameState_InventoryScreen && ScreenFade_IsNone() && age>40) {
        if(phase==3)return age%30==0?1u<<10:0;
#ifdef SH_STAGE10_NO_MAP
        if(age>180 && g_Inventory_SelectionId==InventorySelectionId_Map) {
            phase=3;return 1u<<28;
        }
#endif
        if(age==50)return 1u<<28;
        if(age%30==0) {
            if(g_Inventory_SelectionId==InventorySelectionId_Item)return 1u<<7;
            if(g_Inventory_SelectionId==InventorySelectionId_Exit)return 1u<<4;
            if(g_Inventory_SelectionId==InventorySelectionId_Map)return 2;
        }
    }
    if(state==GameState_PaperMapScreen) {
        phase=2;
        if(age==60)return 1u<<29;
        if(age>90){phase=3;return 1;}
    }
    if(age>1500)game3ds_halt(462,"dev menu itinerary stalled",(state<<16)|phase);
    return 0;
}
''')
if a.cafe_exit_pad:
    diagnostics=dest/'game_diagnostics.c'
    diagnostics.write_text(diagnostic_source+'''
static struct {unsigned count,packet_peak;uint64_t ticks,worst;} cafe_profile[7];
static uint64_t cafe_previous;
static unsigned cafe_phase;
static void Game3ds_DevCafeProfile(void)
{
    uint64_t now=game3ds_ticks();
    if(cafe_previous) {
        uint64_t elapsed=now-cafe_previous;
        cafe_profile[cafe_phase].count++;cafe_profile[cafe_phase].ticks+=elapsed;
        if(elapsed>cafe_profile[cafe_phase].worst)cafe_profile[cafe_phase].worst=elapsed;
        uintptr_t base;unsigned capacity;Game3ds_PacketBounds(&base,&capacity);
        uintptr_t cursor=(uintptr_t)GsOUT_PACKET_P;
        if(cursor>=base && cursor-base<=capacity && cursor-base>cafe_profile[cafe_phase].packet_peak)
            cafe_profile[cafe_phase].packet_peak=cursor-base;
    }
    cafe_previous=now;
    if(Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDeathPlayed))cafe_phase=6;
    else if(Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDied))cafe_phase=5;
    else if(Savegame_EventFlagGet(EventFlag_47))cafe_phase=g_SysWork.playerCombat.isAiming?4:3;
    else if(g_SysWork.sysState==SysState_EventCallback)cafe_phase=g_SysWork.sysStateSteps[0]<10?1:2;
    else cafe_phase=0;
}
void Game3ds_DevReport(FILE *out)
{
    if(!g_SavegamePtr)return;
    fprintf(out,"dev_cafe_profile_hz=268111856\\ndev_cafe_profile_schema=phase,count,total_ticks,worst_ticks,packet_peak\\n");
    for(unsigned i=0;i<7;i++)fprintf(out,"dev_cafe_profile_%u=%u,%u,%llu,%llu,%u\\n",i,i,cafe_profile[i].count,
        (unsigned long long)cafe_profile[i].ticks,(unsigned long long)cafe_profile[i].worst,cafe_profile[i].packet_peak);
    fprintf(out,"dev_combat_enemy_hp=%ld\\ndev_combat_ammo=%u\\ndev_combat_died=%u\\ndev_combat_event_done=%u\\ndev_radio_picked_up=%u\\n",
        (long)g_SysWork.npcs[0].health,g_SysWork.playerCombat.currentWeaponAmmo,
        !!Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDied),
        !!Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDeathPlayed),
        !!Savegame_EventFlagGet(EventFlag_M0S01_PickupPocketRadio));
}
unsigned Game3ds_DevCafePad(void)
{
    static unsigned ticks,room_fade,load_fade,outdoor,exit_waypoint;
    if((g_GameWork.gameState==GameState_MainLoadScreen || g_GameWork.gameState==GameState_LoadMapScreen) && Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDeathPlayed)) {
        load_fade++;
        if(load_fade==2)return 3u<<28;
        if(load_fade==10)return 4u<<28;
    }
    if(g_GameWork.gameState!=GameState_InGame)return 0;
    if(g_SavegamePtr->mapIdx==MapIdx_MAP0_S01)Game3ds_DevCafeProfile();
    ticks++;
    if(SH_3DS_DEV_SCENE==6 && ticks<90)return 0;
    if(SH_3DS_DEV_SCENE==6 && !Savegame_EventFlagGet(EventFlag_47))return ticks%20<2?2:0;
    if(g_SavegamePtr->mapIdx==MapIdx_MAP2_S00) {
        if(g_SysWork.sysState==SysState_Gameplay && ++outdoor>=30)return 5u<<28;
        return g_SysWork.sysState==SysState_EventCallback && ticks%30==0?1u<<3:ticks%20<2?2:0;
    }
    if(!Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDeathPlayed)) {
        if(SH_3DS_DEV_SCENE==6 && g_SysWork.sysState==SysState_Gameplay) {
            s_SubCharacter *p=&g_SysWork.playerWork.player,*e=&g_SysWork.npcs[0];
            int desired=ratan2(e->position.vx-p->position.vx,e->position.vz-p->position.vz)&4095;
            int error=((desired-p->rotation.vy+2048)&4095)-2048;
            if(ABS(error)>192)return 1u<<(error>0?4:5);
        }
        return (1u<<15)|(ticks%20<2?2:0);
    }
    if(g_SysWork.sysState==SysState_LoadRoom || g_SysWork.sysState==SysState_LoadOverlay) {
        room_fade++;
        if(room_fade==2)return 1u<<28;
        if(room_fade==10)return 2u<<28;
    }
    if(g_SysWork.sysState!=SysState_Gameplay)return ticks%20<2?2:0;
    s_SubCharacter *p=&g_SysWork.playerWork.player;
    int radio=SH_3DS_DEV_SCENE==6 && !Savegame_EventFlagGet(EventFlag_M0S01_PickupPocketRadio);
    /* Radio is north of a table. Walk around it through the east aisle;
     * the direct diagonal toward the door legitimately hits its collision. */
    int via=SH_3DS_DEV_SCENE==6 && !radio && exit_waypoint<2;
    int target_x=radio?Q12(2.31f):via?Q12(3.9f):3891;
    int target_z=radio?Q12(273.65f):via?(exit_waypoint?Q12(270.0f):Q12(273.65f)):1103872;
    int dx=target_x-p->position.vx,dz=target_z-p->position.vz;
    int near=ABS(dx)<819 && ABS(dz)<819;
    if(via && near){exit_waypoint++;return 0;}
    int desired=near?(radio?0:3072):ratan2(dx,dz)&4095;
    int error=((desired-p->rotation.vy+2048)&4095)-2048;
    unsigned keys=ABS(error)>40?1u<<(error>0?4:5):0;
    if(!near && ABS(error)<256)keys|=1u<<6;
    if(!via && ABS(dx)<2048 && ABS(dz)<2048 && ABS(error)<160 && ticks%20<2)keys|=2;
    if(ticks>2400)game3ds_halt(462,"dev Cafe exit stalled",ticks);
    return keys;
}
''')
if a.combat_pad:
    diagnostics=dest/'game_diagnostics.c'
    diagnostics.write_text(diagnostic_source+'''
void Game3ds_DevReport(FILE *out)
{
    fprintf(out,"dev_combat_enemy_hp=%ld\\ndev_combat_ammo=%u\\ndev_combat_died=%u\\ndev_combat_event_done=%u\\n",
        (long)g_SysWork.npcs[0].health,g_SysWork.playerCombat.currentWeaponAmmo,
        !!Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDied),
        !!Savegame_EventFlagGet(EventFlag_M0S01_AirScreamerDeathPlayed));
}
''')
if a.world_capture:
    diagnostics=dest/'game_diagnostics.c'
    diagnostics.write_text(diagnostic_source+'''
unsigned Game3ds_DevWorldPad(void)
{
    static unsigned age;
#ifdef SH_STAGE10_SCHOOL_INFIRMARY
    static unsigned placed;
#endif
    if(g_GameWork.gameState!=GameState_InGame)return 0;
    if(g_SysWork.sysState!=SysState_Gameplay)return age++%30==0?2:0;
    if(g_Player_DisableControl)return 0;
#ifdef SH_STAGE10_SCHOOL_INFIRMARY
    if(!placed && age>=30) {
        const s_MapPoint2d *point=&g_MapOverlayHdr.mapPoints[89];
        q3_12 yaw=Q12_ANGLE_NORM_U(Q12_ANGLE_FROM_Q8(point->triggerParam0)+2048);
        g_SysWork.playerWork.player.position.vx=point->positionX-Q12_MULT_PRECISE(Q12(0.375f),Math_Sin(yaw));
        g_SysWork.playerWork.player.position.vz=point->positionZ-Q12_MULT_PRECISE(Q12(0.375f),Math_Cos(yaw));
        g_SysWork.playerWork.player.rotation.vy=yaw;
        Game_PlayerHeightUpdate();placed=1;age=0;
    }
#endif
    age++;
    if(age==120)return 1u<<28;
    if(age==150)return 1u<<30;
    return 0;
}
''')
subprocess.run([prefix+'gcc',*engine,*extra.split(),'-c',str(diagnostics),'-o',str(obj)],check=True)
assert hashlib.sha256(base.read_bytes()).hexdigest()==base_sha,'Normal ELF changed during dev compilation; rebuild the diagnostic'
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==sha for n,sha in object_hashes.items()),'Normal objects changed during dev compilation; rebuild the diagnostic'
objects=[replacements.get(n,n) for n in objects]+[str(obj)]
if a.memory_audit:
    obj=dest/'memory_probe.o'
    subprocess.run([prefix+'gcc',*sdk,'-c',str(p/'tests/stage10_r6_memory_probe.c'),'-o',str(obj)],check=True)
    objects.append(str(obj))
ld=[v.replace(str(p/'silenthill_game.map'),str(dest/'diagnostic.map')) for v in shlex.split(variables['LDFLAGS'])]
if a.memory_audit:ld+=['-Wl,--wrap=linearAlloc,--wrap=linearMemAlign,--wrap=linearFree']
ctrulib=Path(next(v[2:] for v in sdk if v.startswith('-I') and v.endswith('/libctru/include'))).parent
elf=dest/'diagnostic.elf'
subprocess.run([prefix+'g++',*ld,*objects,'-L'+str(ctrulib/'lib'),'-lcitro3d','-lctru','-lm','-o',str(elf)],check=True)
assert dev_id.encode() in elf.read_bytes()
record=dict(variant='DEVELOPMENT_ONLY',scene=a.scene,build=dev_id,
    base_elf_sha256=base_sha,
    elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),flags=extra,hardware_accepted=False)
if a.package:
    binary=dest/'diagnostic.3dsx'
    subprocess.run(['3dsxtool',str(elf),str(binary),'--smdh='+str(p/'silenthill_game.smdh')],check=True)
    record['sha256']=hashlib.sha256(binary.read_bytes()).hexdigest();record['bytes']=binary.stat().st_size
(dest/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
