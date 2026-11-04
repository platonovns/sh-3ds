#include <3ds.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include <malloc.h>
#include <errno.h>
#include "game3ds.h"
#include "game_texture_cache.h"
#include "game_clock.h"
#include "game_modern_controls.h"
#include "game_render_budget.h"
#include "game_profile.h"
#if defined(SH_STAGE11A)
#include "stage11a_perf.h"
#endif
#include "game_cpu_audit.h"
#if defined(SH_CPU_AUDIT_RECORDER)
#include "game_cpu_recorder.h"
#endif
#include "game_io.h"
#include "game_route.h"
#include "game_stage6_input.h"
#include "game_texture_decode.h"
#include "game_feedback.h"
#include "psx_game_pixel.h"
#include "psx_game_pixel.h"
#include "render_3ds.h"
#include "build_identity.h"
#include "game_card_image.h"
#include "game_lower_policy.h"
extern void game_card_set_initial(unsigned card);
extern int Game3ds_CardChange(unsigned card);
#include "game_stage7_input.h"
#include "game_audio.h"
#if defined(SH_3DS_FMV)
#include "game_fmv.h"
#endif
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
#endif

static PsxVram vram;
static Stage4FsResult fs_result;
static jmp_buf exit_game;
static uint32_t game_state, game_step, frames;
static const char *checkpoint = "NATIVE_BOOT";
static int report_error;
#if !defined(SH_PLAYTEST)
static uint64_t last_observation_report;
#endif
static uint64_t last_disk_report;
static const char *phase = "BOOT";
static uint32_t phase_detail;
static bool diagnostic_input;
static uint32_t input_title_age, input_polls, map_frames;
static unsigned start_events,start_pauses,start_resumes,start_passthrough;
static struct {unsigned event,frame,game,sys,map,room,step0,step1;} start_history[32];
extern uint32_t game3ds_gpu_mask_updates, game3ds_gpu_mask_bits;
extern uint32_t game3ds_gpu_oversize_triangles;
extern uint32_t game3ds_gpu_culled_triangles;
#define DRAW_LIMIT GAME_DRAW_LIMIT
#define VERTEX_LIMIT GAME_VERTEX_LIMIT
static Render3dsVertex staging_vertices[VERTEX_LIMIT];
static struct GameDraw {
    uint32_t page, clut, textured, blend, count, first, mask;
    Render3dsTexture *texture;
    uint32_t first_primitive,primitives;
    uint32_t texture_source;
    int clip[4];
} draws[DRAW_LIMIT];
static uint16_t primitive_sizes[DRAW_LIMIT];
static unsigned draw_count;
static uint32_t packet_peak,packet_last,packet_capacity,packet_buffer;
static uint32_t logical_frames,partial_flushes,max_parts_per_frame,duplicate_presents;
static uint32_t begin_parts,begin_presents;
void game3ds_packet_observe(uint32_t bytes,uint32_t capacity,uint32_t buffer)
{
    packet_last=bytes;packet_capacity=capacity;packet_buffer=buffer;
    if(bytes>packet_peak)packet_peak=bytes;
    if(bytes>capacity)game3ds_halt(460,"native packet arena overflow",bytes);
}
static uint32_t last_submit_token=UINT32_MAX,last_submit_display=UINT32_MAX;
extern uint32_t game3ds_gpu_frame_token(void);
static unsigned staged_vertices, primitive_count;
static bool defer_present,native_dirty;
static bool vram_target_active,vram_saved_dirty;
static GameTextureCache cache;
static Render3dsTexture *textures[GAME_TEXTURE_LIMIT];
static Render3dsTexture *feedback_texture;
static uint16_t *feedback_words;
static unsigned feedback_width,feedback_height;
static uint32_t feedback_generation;
static uint32_t fade_frames[192][10],fade_count;
static uint32_t simulation_tick,last_sim_dt;
static uint32_t feedback_color=UINT32_MAX,feedback_staged_color=UINT32_MAX;
static bool feedback_row(void *context,unsigned y,uint8_t *rgba,unsigned width)
{
    uint32_t color=*(uint32_t*)context;
    static GameFeedbackDecode decode;
    if(width!=512 || y>=256)return false;
    memset(rgba,0,width*4);
    game_feedback_decode_init(&decode,color);
    if(!((uintptr_t)rgba&3))rgba=__builtin_assume_aligned(rgba,4);
    if(y<feedback_height)for(unsigned x=0;x<feedback_width;x++) {
        uint32_t pixel=game_feedback_decode_pixel(&decode,feedback_words[y*400+x]);
        memcpy(rgba+x*4,&pixel,4);
    }
    return true;
}
void game3ds_feedback_capture(uint32_t width,uint32_t height)
{
    game3ds_gpu_sync();
    if(!width || width>400 || !height || height>240)game3ds_halt(461,"native feedback extent",width);
    if(!feedback_words)feedback_words=malloc(400*240*sizeof(*feedback_words));
    if(!feedback_words || !render3ds_read_psx(0,0,width,height,feedback_words,400))
        game3ds_halt(461,"native feedback capture",width);
    feedback_width=width;feedback_height=height;
    feedback_generation++;
    feedback_color=feedback_staged_color=UINT32_MAX;
}
static uint32_t heap_used, heap_free, linear_free, linear_min;
static uint32_t heap_peak;
static int32_t player_x, player_z, player_yaw;
static uint32_t player_state, pad_held, control_changes;
static uint32_t sys_step0, sys_step1, map_event;
static uint32_t current_map, current_room, control_disabled;
static int lower_owns;
static unsigned lower_start_active;
static PrintConsole *lower_console_instance;
static void lower_console_bind(void)
{
    gfxSetDoubleBuffering(GFX_BOTTOM,false);
    if(lower_console_instance) {
        lower_console_instance->frameBuffer=(u16*)gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,NULL,NULL);
        consoleSelect(lower_console_instance);
    }
    lower_owns=0;
}
static void lower_console(void)
{
    render3ds_console_bottom();
    /* consoleInit(NULL) initializes currentConsole from the default template;
     * consoleGetDefault() returns that template, not the active console. */
    lower_console_bind();
}
static struct { char operation[32]; int32_t detail; uint32_t map,room; } last_error;
void game3ds_recoverable(const char *operation,int32_t detail)
{
    snprintf(last_error.operation,sizeof(last_error.operation),"%s",operation?operation:"unknown");
    last_error.detail=detail;last_error.map=current_map;last_error.room=current_room;
}
static void start_event(unsigned event)
{
    unsigned i=start_events++%32;
    start_history[i].event=event;start_history[i].frame=frames;
    start_history[i].game=game_state;start_history[i].sys=player_state;
    start_history[i].map=current_map;start_history[i].room=current_room;
    start_history[i].step0=sys_step0;start_history[i].step1=sys_step1;
}
static uint32_t inv_count,inv_equipped,inv_selected,inv_pickups,inv_slots[40];
void game3ds_inventory_observe(uint32_t count,uint32_t equipped,uint32_t selected,uint32_t pickups,const uint32_t *slots)
{inv_count=count;inv_equipped=equipped;inv_selected=selected;inv_pickups=pickups;memcpy(inv_slots,slots,sizeof(inv_slots));}
static int32_t player_health;
/* Do not enter hardware services after APT signals HOME/sleep. The hook only
 * records state; restoration happens later in the foreground game loop. */
static volatile unsigned hardware_suspended;
static int hardware_foreground(void)
{return !hardware_suspended && aptIsActive() && !aptShouldJumpToHome();}
static bool hp_led_ready;
static int hp_led_bucket = -1;
static unsigned hp_led_resume;
static const uint8_t hp_led_colors[8][3] = {
    {0,3,0}, {1,3,0}, {2,3,0}, {3,3,0}, {3,2,0}, {3,1,0}, {3,0,0}, {0,0,0}
};
unsigned game_hp_indicator = 1, game_ammo_display = 2, game_map_enabled = 1;
static void hp_led_set(int bucket)
{
    if(!hp_led_ready || (bucket==hp_led_bucket && !hp_led_resume))return;
    if(!hardware_foreground()){hp_led_resume=1;return;}
    int from=hp_led_bucket<0?7:hp_led_bucket,to=bucket<0?7:bucket;
    InfoLedPattern pattern={0};pattern.delay=1;pattern.smoothing=1;pattern.loopDelay=0xff;
    for(unsigned i=0;i<32;i++) {
        unsigned n=i<8?i+1:8;
        pattern.redPattern[i]=(hp_led_colors[from][0]*(8-n)+hp_led_colors[to][0]*n+4)/8;
        pattern.greenPattern[i]=(hp_led_colors[from][1]*(8-n)+hp_led_colors[to][1]*n+4)/8;
        pattern.bluePattern[i]=(hp_led_colors[from][2]*(8-n)+hp_led_colors[to][2]*n+4)/8;
    }
    if(R_SUCCEEDED(MCUHWC_SetInfoLedPattern(&pattern))) {hp_led_bucket=bucket;hp_led_resume=0;}
}
static void hp_led_off(void) {hp_led_set(-1);}
static void hp_led_update(int32_t health)
{
    if (!hp_led_ready) return;
    if (health < 0) health = 0;
    if (health > 100*4096) health = 100*4096;
    int bucket = 6 - (health * 7 / (100*4096));
    if (bucket < 0) bucket = 0;
    hp_led_set(bucket);
}
typedef struct { uint32_t frame,map,room,game,step,sys,s0,s1,event; int32_t x,z,health; } RouteState;
static RouteState route_history[64];
static unsigned route_count;
typedef struct { uint32_t kind,id,offset,count; } SkippedMedia;
static SkippedMedia skipped_media[128];
static unsigned skipped_count,skipped_overflow;
void game3ds_map_observe(uint32_t map,uint32_t room,int32_t health,uint32_t disabled)
{ current_map=map; current_room=room; player_health=health; control_disabled=disabled; }
void game3ds_hp_observe(uint32_t valid, int32_t health)
{
    if(game_hp_indicator!=1 || !valid)hp_led_off();
    else if(valid==1)hp_led_update(health);
    else if(hp_led_resume)hp_led_set(hp_led_bucket);
}
void game3ds_media_skip(uint32_t kind,uint32_t id,uint32_t offset)
{
    for(unsigned i=0;i<skipped_count;i++)if(skipped_media[i].kind==kind &&
        skipped_media[i].id==id && skipped_media[i].offset==offset) {
        skipped_media[i].count++;return;
    }
    if(skipped_count==128){skipped_overflow++;return;}
    skipped_media[skipped_count++]=(SkippedMedia){kind,id,offset,1};
}
static uint64_t previous_submit, sample_start, wait_ticks, primitive_ticks;
static uint64_t perf_total, perf_game, perf_texture, perf_submit, perf_primitive, perf_wait;
static uint32_t perf_samples;
static double perf_worst_ms;
static uint64_t status_open_start,status_open_wait;
static double status_open_ms,status_open_work_ms;
static unsigned status_open_count;
void game3ds_status_begin(void) {status_open_start=svcGetSystemTick();status_open_wait=wait_ticks;}
static uint32_t gameplay_input_age;
static bool diagnostic_gameplay;
static bool diagnostic_running;
static bool diagnostic_garage;
static unsigned route_leg,route_laps;
static bool diagnostic_stationary;
static bool diagnostic_stage6;
static bool diagnostic_observe;
static bool diagnostic_observe_fast;
static bool trace_pending;
static uint32_t anim_state, upper_state, lower_anim, upper_anim, lower_frame, upper_frame;
static uint64_t simulation_q12, raw_simulation_q12;
typedef struct {
    uint32_t count;
    uint64_t total, texture, submit, primitive, wait, idle, sim;
    uint64_t batches, primitives, vertices, comparisons, misses, evictions, uploads, invalidations;
    double begin_wait, worst;
} PerfWindow;
static PerfWindow window, recent;
#if !defined(SH_PLAYTEST)
static PerfWindow frame_work;
static uint32_t prior_comparisons, prior_misses, prior_evictions, prior_uploads, prior_invalidations;
static uint64_t prior_idle_ticks, prior_simulation;
#endif
void game3ds_timestep(uint32_t dt, uint32_t raw_dt)
{
    simulation_q12+=dt; raw_simulation_q12+=raw_dt;
    simulation_tick++;last_sim_dt=dt;
}
void game3ds_animation_observe(uint32_t state, uint32_t upper, uint32_t low_anim,
                               uint32_t up_anim, uint32_t low_frame, uint32_t up_frame)
{
    anim_state=state; upper_state=upper; lower_anim=low_anim; upper_anim=up_anim;
    lower_frame=low_frame; upper_frame=up_frame;
}
static double recent_ms(uint64_t ticks)
{
    return recent.count ? ticks/CPU_TICKS_PER_MSEC/recent.count : 0;
}
static double recent_work(uint64_t work) { return recent.count ? (double)work/recent.count : 0; }
static bool title_submitted;
static uint32_t title_frames, last_draws, max_draws, last_batches;

static void trace_primitives(void)
{
    FILE *geometry=fopen("sdmc:/3ds/silenthill/stage5_geometry.csv","wb");
    if(geometry) {
        fprintf(geometry,"primitive,vertex,page,clut,textured,blend,mask,x,y,u,v,r,g,b\n");
        for(unsigned i=0;i<draw_count;i++) {
            const struct GameDraw *d=&draws[i];unsigned first=d->first;
            for(unsigned p=0;p<d->primitives;p++) {
                unsigned n=primitive_sizes[d->first_primitive+p];
                for(unsigned j=0;j<n;j++) {
                    const Render3dsVertex *v=staging_vertices+first+j;
                    fprintf(geometry,"%u,%u,%lu,%lu,%lu,%lu,%lu,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
                        (unsigned)(d->first_primitive+p),j,(unsigned long)d->page,(unsigned long)d->clut,(unsigned long)d->textured,
                        (unsigned long)d->blend,(unsigned long)d->mask,(double)v->x,(double)v->y,(double)v->u,(double)v->v,(double)v->r,(double)v->g,(double)v->b);
                }
                first+=n;
            }
        }
        fclose(geometry);
    }
    FILE *out=fopen("sdmc:/3ds/silenthill/stage5_primitives.csv","wb");
    if (!out) return;
    fprintf(out,"batch,vertices,page,clut,blend,mask,x0,y0,x1,y1,u0,v0,u1,v1,red,green,blue,zero,stp_black,stp_color,opaque\n");
    for(unsigned i=0;i<draw_count;i++) {
        const struct GameDraw *d=&draws[i];
        const Render3dsVertex *v=staging_vertices+d->first;
        float x0=v->x,x1=v->x,y0=v->y,y1=v->y,u0=v->u,u1=v->u,t0=1-v->v,t1=1-v->v;
        for(unsigned j=1;j<d->count;j++) {
            if(v[j].x<x0)x0=v[j].x;
            if(v[j].x>x1)x1=v[j].x;
            if(v[j].y<y0)y0=v[j].y;
            if(v[j].y>y1)y1=v[j].y;
            if(v[j].u<u0)u0=v[j].u;
            if(v[j].u>u1)u1=v[j].u;
            float t=1-v[j].v; if(t<t0)t0=t; if(t>t1)t1=t;
        }
        unsigned classes[4]={0};
        unsigned mode=(d->page>>7)&3;
        if (d->textured && mode<3 && (d->clut>>6)<512) {
            unsigned px=(d->page&15)*64,py=(d->page&16)*16;
            int lo_u=(int)(u0*256),hi_u=(int)(u1*256),lo_v=(int)(t0*256),hi_v=(int)(t1*256);
            if(hi_u-lo_u>256)hi_u=lo_u+256;
            if(hi_v-lo_v>256)hi_v=lo_v+256;
            for(int ty=lo_v;ty<=hi_v;ty++) for(int tx=lo_u;tx<=hi_u;tx++) {
                unsigned x=tx&255,y=ty&255;
                uint16_t word=vram.words[((py+y)&511)*1024+((px+(x>>(2-mode)))&1023)];
                if(mode<2) {
                    unsigned index=mode==0?(word>>((x&3)*4))&15:(word>>((x&1)*8))&255;
                    word=vram.words[(d->clut>>6)*1024+(((d->clut&63)*16+index)&1023)];
                }
                classes[!word?0:word==0x8000?1:word&0x8000?2:3]++;
            }
        }
        fprintf(out,"%u,%lu,%lu,%lu,%lu,%lu,%.1f,%.1f,%.1f,%.1f,%.0f,%.0f,%.0f,%.0f,%.3f,%.3f,%.3f,%u,%u,%u,%u\n",
            i,(unsigned long)d->count,(unsigned long)d->page,(unsigned long)d->clut,(unsigned long)d->blend,
            (unsigned long)d->mask,
            (double)x0,(double)y0,(double)x1,(double)y1,(double)(u0*256),(double)(t0*256),(double)(u1*256),(double)(t1*256),
            (double)v->r,(double)v->g,(double)v->b,classes[0],classes[1],classes[2],classes[3]);
    }
    fclose(out);
}
static bool texture_reuse_unpinned(unsigned slot,GameTextureDecode *decode)
{
    int victim=-1;
    for(unsigned i=0;i<GAME_TEXTURE_LIMIT;i++)
        if(textures[i] && cache.entries[i].occupied && !cache.entries[i].pinned &&
           (victim<0 || cache.entries[i].age<cache.entries[victim].age))victim=(int)i;
    if(victim<0 || !game_texture_discard(&cache,(unsigned)victim))return false;
    textures[slot]=textures[victim];textures[victim]=NULL;
    return render3ds_texture_update_tiles(textures[slot],decode,0,0,32,32);
}
static Render3dsTexture *texture_for(struct GameDraw *d)
{
    if(d->page==GAME_FEEDBACK_PAGE) {
        if(!feedback_texture)feedback_texture=render3ds_texture_create_rows(512,256,feedback_row,&d->clut,NULL,NULL);
        else if(feedback_color!=d->clut && !render3ds_texture_update_rows(feedback_texture,feedback_row,&d->clut))
            game3ds_halt(461,"native feedback upload",d->clut);
        if(!feedback_texture)game3ds_halt(461,"native feedback allocation",0);
        feedback_color=d->clut;render3ds_texture_psx_coverage(feedback_texture,3);
        return feedback_texture;
    }
    bool upload;
    uint64_t lookup=game_prof_begin();
    int slot=game_texture_acquire(&cache,d->page,d->clut,&upload);
    game_prof_end(GP_CACHE,lookup);
    if (slot<0) {
        unsigned required=0;
        for(unsigned i=0;i<draw_count;i++)if(draws[i].textured) {
            unsigned j=0;
            for(;j<i;j++)if(draws[j].textured && draws[j].page==draws[i].page && draws[j].clut==draws[i].clut)break;
            if(j==i)required++;
        }
        game3ds_halt(432,"simultaneous pinned textures",required);
    }
    if (upload) {
        GameTextureDecode decode;
        if(!game_texture_decode_init(&decode,&vram,d->page,d->clut))game3ds_halt(433,"game texture metadata",d->page);
        if (!textures[slot]) {
            bool reused=false;
            /* Keep room for other linear allocations when an old unpinned
             * texture can back this key; pinned submission textures stay put. */
            if(linearSpaceFree()<2u*1024u*1024u) {
                reused=texture_reuse_unpinned((unsigned)slot,&decode);
                if(!reused && textures[slot])game3ds_halt(433,"game texture reuse/decode",d->page);
            }
            if(!reused)textures[slot]=render3ds_texture_create_rows(256,256,game_texture_decode_row,&decode,NULL,NULL);
            if(!textures[slot]) {
                reused=texture_reuse_unpinned((unsigned)slot,&decode);
                if(!reused && textures[slot])game3ds_halt(433,"game texture reuse/decode",d->page);
            }
        }
        else if (!render3ds_texture_update_tiles(textures[slot],&decode,
                    cache.entries[slot].tx0,cache.entries[slot].ty0,cache.entries[slot].tx1,cache.entries[slot].ty1))
            game3ds_halt(433,"game texture update/decode",d->page);
        if (!textures[slot]) game3ds_halt(433,"game texture allocation/decode",d->page);
        render3ds_texture_psx_coverage(textures[slot],decode.coverage);
        render3ds_texture_linear(textures[slot],(d->page&GAME_STATUS_FONT_PAGE)!=0);
        cache.entries[slot].dirty=false; cache.uploads++;
    }
    return textures[slot];
}

uint64_t game3ds_ticks(void) { return svcGetSystemTick(); }
static uint64_t clock_origin;
static bool clock_started;
static unsigned lower_auto=1,lower_lcd_ready;
static int lower_lcd_on=1;
static unsigned lower_lcd_target=1,lower_lcd_level=0,lower_lcd_resume;
static u32 lower_lcd_normal;
static uint64_t lower_lcd_tick,lower_lcd_on_since;
static int lower_lcd_pending;
static aptHookCookie lower_apt_cookie;
static int lower_apt_hooked;
/* Do not hold gsp::Lcd across an APT handoff: HOME needs its session. */
static Result lower_lcd_call(unsigned op,u32 *value)
{
    if(!hardware_foreground())return -1;
    Result rc=gspLcdInit();
    if(R_FAILED(rc))return rc;
    if(op==0)rc=GSPLCD_GetBrightness(GSPLCD_SCREEN_BOTTOM,value);
    else if(op==1)rc=GSPLCD_SetBrightnessRaw(GSPLCD_SCREEN_BOTTOM,*value);
    else if(op==2)rc=GSPLCD_PowerOnBacklight(GSPLCD_SCREEN_BOTTOM);
    else rc=GSPLCD_PowerOffBacklight(GSPLCD_SCREEN_BOTTOM);
    gspLcdExit();
    return rc;
}
static Result lower_lcd_get(u32 *value){return lower_lcd_call(0,value);}
static Result lower_lcd_set(u32 value){return lower_lcd_call(1,&value);}
static Result lower_lcd_power(int on){return lower_lcd_call(on?2:3,NULL);}
/* ON SUSPEND is called before the display is handed to the Home Menu.
 * Restore the system-visible LCD state without changing the game's target. */
static void lower_lcd_handoff(void)
{
    if(!lower_lcd_ready || hardware_suspended ||
       (lower_lcd_on && (!lower_lcd_normal || lower_lcd_level==lower_lcd_normal)))return;
    if(R_FAILED(gspLcdInit()))return;
    if(lower_lcd_normal && R_SUCCEEDED(GSPLCD_SetBrightnessRaw(GSPLCD_SCREEN_BOTTOM,lower_lcd_normal)))
        lower_lcd_level=lower_lcd_normal;
    if(!lower_lcd_on && R_SUCCEEDED(GSPLCD_PowerOnBacklight(GSPLCD_SCREEN_BOTTOM)))
        lower_lcd_on=1;
    gspLcdExit();
}
static void lower_apt_hook(APT_HookType type,void *arg)
{
    (void)arg;
    if(type==APTHOOK_ONSUSPEND)lower_lcd_handoff();
    if(type==APTHOOK_ONSUSPEND || type==APTHOOK_ONSLEEP || type==APTHOOK_ONEXIT)
        hardware_suspended=1;
    else if(type==APTHOOK_ONWAKEUP || type==APTHOOK_ONRESTORE) {
        hardware_suspended=0;lower_lcd_resume=1;hp_led_resume=1;
    }
}
static void lower_backlight(int on)
{
    if(!lower_lcd_ready)return;
    lower_lcd_target=on;lower_lcd_pending=0;
    if(!hardware_foreground()) {lower_lcd_resume=1;return;}
    if(on && lower_lcd_normal) {
        lower_lcd_set(lower_lcd_normal);
        lower_lcd_level=lower_lcd_normal;
    }
    if(on==lower_lcd_on)return;
    Result rc=lower_lcd_power(on);
    if(R_SUCCEEDED(rc))lower_lcd_on=on;
    else game3ds_recoverable("lower backlight",rc);
}
static void lower_request_off(void)
{
    if(hardware_foreground() && lower_lcd_ready && lower_lcd_target && lower_lcd_on && lower_lcd_normal && lower_lcd_level==lower_lcd_normal) {
        u32 current=0;
        if(R_SUCCEEDED(lower_lcd_get(&current)) && current>=16 && current<=172)
            lower_lcd_level=lower_lcd_normal=current;
    }
    lower_lcd_pending=0;lower_lcd_target=0;
}
void game3ds_lower_backlight_tick(void)
{
    if(!hardware_foreground())return;
    if(hp_led_resume)hp_led_set(hp_led_bucket);
    if(!lower_lcd_ready)return;
    uint64_t now=svcGetSystemTick();
    if(lower_lcd_resume) {
        lower_lcd_resume=0;lower_lcd_on=1;
        if(!lower_lcd_target) {
            if(R_SUCCEEDED(lower_lcd_power(0)))lower_lcd_on=0;
        } else if(lower_lcd_normal) {
            lower_lcd_set(lower_lcd_normal);
            lower_lcd_level=lower_lcd_normal;
        }
        lower_lcd_tick=now;
    }
    if(lower_lcd_pending && now-lower_lcd_on_since>=SYSCLOCK_ARM11/5) {
        lower_lcd_pending=0;lower_lcd_target=1;
    }
    if(!lower_lcd_normal) {if(lower_lcd_on!=(int)lower_lcd_target)lower_backlight(lower_lcd_target);return;}
    if(lower_lcd_target && !lower_lcd_on) {
        if(R_FAILED(lower_lcd_set(16)))return;
        if(R_FAILED(lower_lcd_power(1)))return;
        lower_lcd_on=1;lower_lcd_level=16;lower_lcd_tick=now;
    }
    if(!lower_lcd_on)return;
    if(now-lower_lcd_tick<SYSCLOCK_ARM11/32)return;
    lower_lcd_tick=now;
    unsigned step=(lower_lcd_normal>16?(lower_lcd_normal-16+15)/16:1);
    unsigned target=lower_lcd_target?lower_lcd_normal:16;
    unsigned next=lower_lcd_level;
    if(next<target)next=(target-next<step)?target:next+step;
    else if(next>target)next=(next-target<step)?target:next-step;
    if(next!=lower_lcd_level && R_SUCCEEDED(lower_lcd_set(next)))lower_lcd_level=next;
    if(!lower_lcd_target && lower_lcd_level<=16) {
        if(R_SUCCEEDED(lower_lcd_power(0)))lower_lcd_on=0;
    }
}
void game3ds_lower_backlight_observe(unsigned game,unsigned sys,unsigned cutscene,unsigned disabled,unsigned has_map)
{
    int on=lower_backlight_content_policy(lower_auto,game,sys,cutscene,disabled,has_map,game_map_enabled,game_ammo_display!=2);
    if(on==0)lower_request_off();
    else if(on==1) {
        int status=game==14 || game==15 || game==16 || game==18 || game==19 || game==20 ||
                   (game==11 && (sys==1 || sys==2 || sys==3 || sys==8 || sys==9));
        if(status || !lower_auto) {lower_lcd_pending=0;lower_lcd_target=1;}
        else if(!lower_lcd_target && !lower_lcd_pending) {lower_lcd_pending=1;lower_lcd_on_since=svcGetSystemTick();}
    } else lower_lcd_pending=0;
    game3ds_lower_backlight_tick();
}
#if defined(SH_3DS_FMV)
void game_fmv_platform_begin(void)
{
    if(lower_auto)lower_request_off();
    hp_led_off();
    game3ds_gpu_sync();
    render3ds_wait_idle();
    lower_console();consoleClear();gfxFlushBuffers();
}
void game_fmv_platform_end(uint64_t began)
{
    if(clock_started)clock_origin+=svcGetSystemTick()-began;
    previous_submit=0;wait_ticks=primitive_ticks=0;
    memset(&window,0,sizeof(window));
}
#endif
static uint32_t clock_units(uint32_t frequency)
{
    uint64_t now=svcGetSystemTick();
    if (!clock_started) { clock_origin=now; clock_started=true; }
    return game_clock_units(now-clock_origin,SYSCLOCK_ARM11,frequency);
}
uint32_t game3ds_vblank_clock(void) { return clock_units(60); }
uint32_t game3ds_hblank_clock(void) { return clock_units(15780); }
uint32_t game3ds_q12_clock(void) { return clock_units(4096); }
static unsigned fps_limit=60,title_request,control_mode=GAME_CONTROL_HYBRID;
unsigned game_overlay_mode,game_text_style;
unsigned game_lower_brightness=4,game_card_number=1,game_map_invert=0;
static unsigned settings_error;
#if defined(SH_CPU_AUDIT_RECORDER) && !defined(SH_PLAYTEST)
void Game3ds_CpuRecorderView(int32_t out[7]);
static CpuRecordContext cpu_record_context(void)
{
    CpuRecordContext c={.game=game_state,.map=current_map,.room=current_room,
        .fps_mode=fps_limit,.control_mode=control_mode,
        .lcd_frames=render3ds_stats()->lcd_presents,.x=player_x,.z=player_z,.yaw=player_yaw};
    if(game_state==11) {
        int32_t view[7];Game3ds_CpuRecorderView(view);c.flashlight=view[0];
        memcpy(c.view,view+1,sizeof(c.view));
    }
    return c;
}
#if !defined(SH_PLAYTEST)
static void cpu_record_indicator(void)
{
    /* The ordinary lower console is available during gameplay/dialogue.
     * Native Status/Map retain exclusive ownership of their lower image. */
    if(game3ds_gpu_display())return;
    char label[40];
    if(cpu_recorder_label(label,sizeof(label))) {
        uint64_t start=game_prof_clock();
        printf("\x1b[29;1H%-39s\x1b[H",label);gfxFlushBuffers();
        game_prof_add(GP_REPORT,game_prof_clock()-start);
    }
}
#endif
#endif
uint32_t game3ds_control_mode(void) {return control_mode;}
static int settings_load_one(const char *path)
{
    FILE *f=fopen(path,"rb");
    if(!f)return 0;
    unsigned mode,fps,overlay=0,style=0,cursor=0,brightness=5,lower=0,card=1,hp=1,ammo=1,invert=1,hud_invert=0,auto_lcd=1,map_invert=0,map_enabled=1,old_culling=0;char extra;
    char version[16]={0};
    int fields=fscanf(f,"%15s\nmode=%u\nfps=%u\n",version,&mode,&fps);
    if(fields==3 && !strcmp(version,"SH3DS6"))
        fields+=fscanf(f,"overlay=%u\nstyle=%u\nbrightness=%u\ncard=%u\nhp=%u\nammo=%u\n",&overlay,&style,&brightness,&card,&hp,&ammo);
    if(fields==3 && !strcmp(version,"SH3DS8"))
        fields+=fscanf(f,"overlay=%u\nstyle=%u\nbrightness=%u\ncard=%u\nhp=%u\nammo=%u\nauto_lcd=%u\nmap_invert=%u\n",&overlay,&style,&brightness,&card,&hp,&ammo,&auto_lcd,&map_invert);
    if(fields==3 && (!strcmp(version,"SH3DS9") || !strcmp(version,"SH3DS10")))
        fields+=fscanf(f,"overlay=%u\nstyle=%u\nbrightness=%u\ncard=%u\nhp=%u\nammo=%u\nauto_lcd=%u\nmap_invert=%u\nmap_enabled=%u\n",&overlay,&style,&brightness,&card,&hp,&ammo,&auto_lcd,&map_invert,&map_enabled);
    /* Preserve the user's other preferences when downgrading from the
     * short-lived culling settings format; its last field is discarded. */
    if(fields==12 && !strcmp(version,"SH3DS10"))
        fields+=fscanf(f,"culling=%u\n",&old_culling);
    if(fields==3 && !strcmp(version,"SH3DS7"))
        fields+=fscanf(f,"overlay=%u\nstyle=%u\nbrightness=%u\ncard=%u\nhp=%u\nammo=%u\nauto_lcd=%u\n",&overlay,&style,&brightness,&card,&hp,&ammo,&auto_lcd);
    if(fields==3 && (!strcmp(version,"SH3DS2") || !strcmp(version,"SH3DS3") || !strcmp(version,"SH3DS4") || !strcmp(version,"SH3DS5")))
        fields+=fscanf(f,"overlay=%u\nstyle=%u\ncursor=%u\nbrightness=%u\nlower=%u\ncard=%u\n",&overlay,&style,&cursor,&brightness,&lower,&card);
    if(fields==9 && (!strcmp(version,"SH3DS3") || !strcmp(version,"SH3DS4") || !strcmp(version,"SH3DS5")))
        fields+=fscanf(f,"hp=%u\nammo=%u\ninvert=%u\n",&hp,&ammo,&invert);
    if(fields==12 && (!strcmp(version,"SH3DS4") || !strcmp(version,"SH3DS5")))
        fields+=fscanf(f,"hud_invert=%u\n",&hud_invert);
    int trailing=fscanf(f," %c",&extra);fclose(f);
    int v5=!strcmp(version,"SH3DS5"),v6=!strcmp(version,"SH3DS6"),v7=!strcmp(version,"SH3DS7"),v8=!strcmp(version,"SH3DS8"),v10=!strcmp(version,"SH3DS10"),v9=!strcmp(version,"SH3DS9") || v10;
    if(((fields==3 && !strcmp(version,"SH3DS1")) || (fields==9 && (!strcmp(version,"SH3DS2") || v6)) || (fields==10 && v7) || (fields==11 && v8) || (fields==12 && ((v9 && !v10) || !strcmp(version,"SH3DS3"))) || (fields==13 && (!strcmp(version,"SH3DS4") || v5 || v10))) && trailing==EOF && mode<=GAME_CONTROL_HYBRID && (fps==30 || fps==60) && overlay<4 && style<4 && cursor<2 && ((v5 || v6 || v7 || v8 || v9) ? brightness>=((v8 || v9)?1u:2u) && brightness<=10 : brightness>=1 && brightness<=5) && lower<2 && card>=1 && card<=8 && hp<3 && ammo<(v9?3u:4u) && invert<2 && hud_invert<2 && auto_lcd<2 && (!(v8 || v9) || map_invert<2) && map_enabled<2 && old_culling<3) {
        control_mode=mode;fps_limit=fps;game_overlay_mode=overlay;game_text_style=style;
        game_lower_brightness=(v5 || v6 || v7 || v8 || v9)?brightness:brightness*2;game_card_number=card;lower_auto=auto_lcd;
        game_hp_indicator=hp;game_ammo_display=v9?ammo:ammo==3?2:ammo==2?0:ammo;
        game_map_invert=(v8 || v9)?map_invert:0;game_map_enabled=map_enabled;
        game_card_set_initial(card);
        return 1;
    }
    settings_error=1;game3ds_recoverable("settings read",1);return 0;
}
static void settings_load(void)
{
    if(!settings_load_one("sdmc:/3ds/silenthill/native_settings.cfg"))
        settings_load_one("sdmc:/3ds/silenthill/native_settings.bak");
}
static void settings_save(void)
{
    const char *path="sdmc:/3ds/silenthill/native_settings.cfg";
    const char *temp="sdmc:/3ds/silenthill/native_settings.tmp";
    const char *backup="sdmc:/3ds/silenthill/native_settings.bak";
    FILE *f=fopen(temp,"wb");if(!f){settings_error=2;game3ds_recoverable("settings write",errno);return;}
    int ok=fprintf(f,"SH3DS9\nmode=%u\nfps=%u\noverlay=%u\nstyle=%u\nbrightness=%u\ncard=%u\nhp=%u\nammo=%u\nauto_lcd=%u\nmap_invert=%u\nmap_enabled=%u\n",control_mode,fps_limit,game_overlay_mode,game_text_style,game_lower_brightness,game_card_number,game_hp_indicator,game_ammo_display,lower_auto,game_map_invert,game_map_enabled)>0;
    if(fclose(f))ok=0;
    if(!ok) {settings_error=2;game3ds_recoverable("settings write",errno);return;}
    /* SD/FAT rename does not replace an existing destination. Keep the last
     * valid preference file until the complete new file has been closed. */
    if(remove(backup) && errno!=ENOENT) {settings_error=2;game3ds_recoverable("settings backup",errno);return;}
    if(rename(path,backup) && errno!=ENOENT) {settings_error=2;game3ds_recoverable("settings backup",errno);return;}
    if(rename(temp,path)) {int e=errno;rename(backup,path);settings_error=2;game3ds_recoverable("settings rename",e);return;}
    settings_error=0;
}
void Game3ds_FpsLimit(unsigned fps) {if(fps==30 || fps==60)fps_limit=fps;}
uint32_t game3ds_fps_limit(void) {return fps_limit;}
uint32_t game3ds_take_title_request(void) {unsigned r=title_request;title_request=0;return r;}
static void pause_menu(void)
{
    /* Block at the pad boundary: no engine, FS, callbacks or simulation ticks
     * run here. Exclude pause wall time from all game clocks on return. */
    lower_start_active=1;
    lower_backlight(1);
    game3ds_gpu_sync();
    /* Swap to the unused lower buffer for the console. The previously visible
     * gameplay frame stays intact while START owns the other buffer. */
    unsigned resume_lower=lower_owns;
    if(resume_lower)gfxScreenSwapBuffers(GFX_BOTTOM,false);
    lower_console();
    uint64_t start=svcGetSystemTick();
    game_audio_pause(1);
    unsigned selected=0,previous=KEY_START,diagnostics=0;int card_error=0;
    unsigned changed=0;
    consoleClear();
    gfxFlushBuffers();gfxScreenSwapBuffers(GFX_BOTTOM,false);
    for(;;) {
        if(!aptMainLoop())game3ds_halt(0,"APT exit",0);
        hidScanInput();unsigned held=hidKeysHeld(),down=held&~previous;previous=held;
        if(diagnostics) {
            if(down&(KEY_B|KEY_A|KEY_START)) {diagnostics=0;consoleClear();}
            else {
                printf("\x1b[H\n  DIAGNOSTICS\n\n  Source ID:\n  %s\n\n  Map %lu  room %lu\n  FPS %.1f\n\n  Last recoverable error:\n  %s (%ld)\n  Map %lu room %lu\n\n  B: back\n",
                    SH_BUILD_ID,(unsigned long)current_map,(unsigned long)current_room,
                    recent.total?1000.0/recent_ms(recent.total):0.0,
                    last_error.operation[0]?last_error.operation:"none",(long)last_error.detail,
                    (unsigned long)last_error.map,(unsigned long)last_error.room);
                gfxFlushBuffers();gspWaitForVBlank();
            }
            continue;
        }
        if(down&KEY_DUP)selected=(selected+14)%15;
        if(down&KEY_DDOWN)selected=(selected+1)%15;
        if((down&(KEY_DLEFT|KEY_DRIGHT)) || ((down&KEY_B) && selected>=2 && selected<=12)) {
            int delta=(down&KEY_DLEFT)?-1:1;
            switch(selected) {
            case 2: fps_limit=fps_limit==30?60:30;changed=1;break;
            case 3: control_mode=(control_mode+3+delta)%3;changed=1;break;
            case 4: game_overlay_mode=(game_overlay_mode+4+delta)%4;changed=1;break;
            case 5: game_text_style=(game_text_style+4+delta)%4;changed=1;break;
            case 6: if(delta<0 && game_lower_brightness>1) {--game_lower_brightness;changed=1;} else if(delta>0 && game_lower_brightness<10) {++game_lower_brightness;changed=1;} break;
            case 7: {unsigned card=(game_card_number+7+delta)%8+1;
                int rc=Game3ds_CardChange(card);
                if(rc>0){game_card_number=card;changed=1;card_error=0;}
                else {card_error=-rc;game3ds_recoverable("card switch",card_error);}
                break;}
            case 8: game_hp_indicator=(game_hp_indicator+3+delta)%3;hp_led_off();changed=1;break;
            case 9: game_ammo_display=(game_ammo_display+3+delta)%3;changed=1;break;
            case 10: game_map_enabled=!game_map_enabled;changed=1;break;
            case 11: lower_auto=!lower_auto;changed=1;break;
            case 12: game_map_invert=!game_map_invert;changed=1;break;
            }
        }
        if(down&(KEY_START|KEY_A))break;
        if(down&KEY_B) {
            if(selected==0)break;
            if(selected==1){title_request=1;break;}
            if(selected==13) {settings_save();game3ds_halt(0,"Pause: application exit",0);}
            if(selected==14) {diagnostics=1;consoleClear();continue;}
        }
        /* Clear each menu row before repainting after input, including the
         * remainder of any value that was longer than its replacement. */
        if(down)for(unsigned row=5;row<=21;row++)printf("\x1b[%u;1H%-39s",row,"");
        printf("\x1b[H\n        SILENT HILL - PAUSED\n\n\n"
            "  %c Resume\n  %c Exit to Title\n  %c Gameplay: %u FPS\n  %c Controls: %s\n"
            "  %c Counter: %s\n  %c Text: %s\n  %c Map bright: %u%% SEL+UD\n  %c Memory Card: %u\n  %c HP indicator: %s\n  %c HUD: %s\n  %c Map: %s SEL+L\n  %c Lower auto: %s\n  %c Map invert: %s SEL+R\n  %c Quit application\n  %c Diagnostics\n\n"
            "  D-pad: select / change\n  B: confirm   A / START: resume\n%s",
            selected==0?'>':' ',selected==1?'>':' ',selected==2?'>':' ',fps_limit,
            selected==3?'>':' ',control_mode==0?"Tank":control_mode==1?"Modern":"Hybrid",
            selected==4?'>':' ',(const char*[]){"Off","FPS","Frame time","FPS + Frame time"}[game_overlay_mode],
            selected==5?'>':' ',(const char*[]){"White","Black","White + outline","Black 70%"}[game_text_style],
            selected==6?'>':' ',game_lower_brightness*10,
            selected==7?'>':' ',game_card_number,selected==8?'>':' ',(const char*[]){"OFF","LED","SQUARE"}[game_hp_indicator],
            selected==9?'>':' ',(const char*[]){"CURRENT","CURRENT + RESERVE","OFF"}[game_ammo_display],
            selected==10?'>':' ',game_map_enabled?"ON":"OFF",selected==11?'>':' ',lower_auto?"ON":"OFF",selected==12?'>':' ',game_map_invert?"ON":"OFF",selected==13?'>':' ',selected==14?'>':' ',settings_error?"  Settings could not be saved/read\n":"");
        if(card_error)printf("  Card switch error %d\n",card_error);
        gfxFlushBuffers();gspWaitForVBlank();
    }
    if(changed)settings_save();
    /* Swallow the closing key; it must not activate a title/menu action. */
    do {hidScanInput();gspWaitForVBlank();}while(aptMainLoop() && (hidKeysHeld()&(KEY_START|KEY_A|KEY_B)));
    clock_origin+=svcGetSystemTick()-start;
    game_prof_end(GP_PAUSE,start);
    game_audio_pause(0);
    previous_submit=0;wait_ticks=primitive_ticks=0;
    memset(&window,0,sizeof(window));
    lower_start_active=0;
    if(resume_lower) {
        gfxSetDoubleBuffering(GFX_BOTTOM,true);
        gfxScreenSwapBuffers(GFX_BOTTOM,false);lower_owns=1;
    } else consoleClear();
}
void game3ds_primitive_ticks(uint64_t ticks) { primitive_ticks+=ticks; }
void game3ds_player_observe(int32_t x, int32_t z, int32_t yaw, uint32_t state, uint32_t pad,
                           uint32_t step0, uint32_t step1, uint32_t event)
{
    if (game_state==11 && state==0 && (pad&0xf0) &&
        (player_x!=x || player_z!=z || player_yaw!=yaw)) control_changes++;
    player_x=x; player_z=z; player_yaw=yaw; player_state=state; pad_held=pad;
    sys_step0=step0; sys_step1=step1; map_event=event;
    game_prof_context(game_state,state,x,z,yaw,fs_result.file_id,map_frames);
    game_io_context(game_state,state,map_frames,x,z,yaw);
}
static void memory_sample(void)
{
    struct mallinfo mem=mallinfo(); heap_used=mem.uordblks; heap_free=mem.fordblks;
    if(heap_used>heap_peak)heap_peak=heap_used;
    linear_free=linearSpaceFree(); if (!linear_min || linear_free<linear_min) linear_min=linear_free;
}
#if defined(SH_STAGE11A_LIFETIME)
unsigned stage11a_lifetime_io_history(void);
void stage11a_lifetime_feedback(uint32_t out[8]);
void stage11a_lifetime_render(Stage11aLifetime *s)
{
    uint32_t *p=s->render;
    unsigned occupied=0,pinned=0,dirty=0,clean=0,index_used=0,allocated=0;
    for(unsigned i=0;i<GAME_TEXTURE_LIMIT;i++) {
        const GameTextureEntry *e=&cache.entries[i];occupied+=e->occupied;
        pinned+=e->occupied&&e->pinned;dirty+=e->occupied&&e->dirty;clean+=e->occupied&&!e->dirty;
        allocated+=textures[i]!=NULL;
    }
    for(unsigned i=0;i<256;i++)index_used+=cache.index[i]!=0;
    p[0]=cache.active;p[1]=cache.peak;p[2]=occupied;p[3]=pinned;p[4]=dirty;p[5]=clean;
    p[6]=index_used;p[7]=allocated;p[8]=cache.clock;p[9]=cache.hits;p[10]=cache.misses;
    p[11]=cache.comparisons;p[12]=cache.invalidations;p[13]=cache.uploads;p[14]=cache.evictions;
    p[15]=vram.generation;p[16]=feedback_generation;p[17]=draw_count;p[18]=primitive_count;
    p[19]=staged_vertices;p[20]=packet_peak;p[21]=max_draws;p[22]=last_batches;
    const Render3dsStats *r=render3ds_stats();p[23]=r->texture_bytes;p[24]=r->readback_copies;
    p[25]=r->draw_calls;p[26]=r->vertex_capacity;p[27]=r->command_buffer_bytes;
    p[28]=feedback_words!=NULL;p[29]=feedback_texture!=NULL;p[30]=cache.peak_pinned;
    p[31]=GAME_TEXTURE_LIMIT;stage11a_lifetime_renderer(p+32);
    /* Profile-independent existing renderer envelopes (120 presentations), so
     * OFF mode can still compare FPS and coarse graphics costs. */
    s->cache[4]=recent.count;
    if(recent.count) {
        s->cache[5]=(uint32_t)(recent.total/CPU_TICKS_PER_MSEC/recent.count*1000);
        s->cache[6]=(uint32_t)(recent.texture/CPU_TICKS_PER_MSEC/recent.count*1000);
        s->cache[7]=(uint32_t)(recent.submit/CPU_TICKS_PER_MSEC/recent.count*1000);
        s->cache[8]=(uint32_t)(recent.primitive/CPU_TICKS_PER_MSEC/recent.count*1000);
        s->cache[9]=(uint32_t)(recent.wait/CPU_TICKS_PER_MSEC/recent.count*1000);
    }
    s->cache[10]=logical_frames;s->cache[11]=partial_flushes;s->cache[12]=packet_last;
    s->cache[13]=r->vertices_used;s->cache[14]=max_parts_per_frame;s->cache[15]=native_dirty;
    s->resource[9]=stage11a_lifetime_io_history();
    stage11a_lifetime_feedback(s->cache+16);
}
#endif
#if defined(SH_STAGE11A)
static struct {
    uint32_t invalidations,misses,uploads,evictions,feedback,generation;
    uint32_t heap_used,heap_free,linear_free,vram_free;
} s11_render_boundary[2];
void stage11a_renderer_boundary(unsigned start)
{
    unsigned i=start?0:1;memory_sample();
    s11_render_boundary[i].invalidations=cache.invalidations;
    s11_render_boundary[i].misses=cache.misses;s11_render_boundary[i].uploads=cache.uploads;
    s11_render_boundary[i].evictions=cache.evictions;
    s11_render_boundary[i].feedback=feedback_generation;s11_render_boundary[i].generation=vram.generation;
    s11_render_boundary[i].heap_used=heap_used;s11_render_boundary[i].heap_free=heap_free;
    s11_render_boundary[i].linear_free=linear_free;s11_render_boundary[i].vram_free=vramSpaceFree();
}
void stage11a_renderer_report(FILE *out)
{
    fputs("stage11a_cache_window_schema=invalidations,misses,uploads,evictions,feedback_generations,vram_generations\n",out);
    fprintf(out,"stage11a_cache_window=%lu,%lu,%lu,%lu,%lu,%lu\n",
        (unsigned long)(s11_render_boundary[1].invalidations-s11_render_boundary[0].invalidations),
        (unsigned long)(s11_render_boundary[1].misses-s11_render_boundary[0].misses),
        (unsigned long)(s11_render_boundary[1].uploads-s11_render_boundary[0].uploads),
        (unsigned long)(s11_render_boundary[1].evictions-s11_render_boundary[0].evictions),
        (unsigned long)(s11_render_boundary[1].feedback-s11_render_boundary[0].feedback),
        (unsigned long)(s11_render_boundary[1].generation-s11_render_boundary[0].generation));
    fputs("stage11a_memory_schema=normal_heap_used,normal_heap_free_chunks,linear_free,vram_free\n",out);
    for(unsigned i=0;i<2;i++)fprintf(out,"stage11a_memory_%s=%lu,%lu,%lu,%lu\n",i?"end":"start",
        (unsigned long)s11_render_boundary[i].heap_used,(unsigned long)s11_render_boundary[i].heap_free,
        (unsigned long)s11_render_boundary[i].linear_free,(unsigned long)s11_render_boundary[i].vram_free);
}
#endif
static double average_ms(uint64_t ticks)
{
    return perf_samples ? ticks / CPU_TICKS_PER_MSEC / perf_samples : 0;
}

static unsigned combat_trace,combat_rows;
static uint32_t combat_last[5];
static uint32_t model_calls[64],model_bytes[64],model_fade[64],visibility_rows;
static int32_t visibility_last[6][15];
static unsigned visibility_seen;
uint32_t game3ds_debug_enabled(void) {return combat_trace;}
void game3ds_model_observe(uint32_t character,uint32_t bytes,uint32_t fade)
{
    if(!combat_trace || character>=64)return;
    model_calls[character]++;model_bytes[character]+=bytes;model_fade[character]=fade;
}
void game3ds_visibility_observe(uint32_t slot,const int32_t *row)
{
    if(!combat_trace || visibility_rows>=512 || slot>=6)return;
    if(!row[0] && (visibility_seen&(1u<<slot)) &&
        !memcmp(row,visibility_last[slot],sizeof(visibility_last[slot])))return;
    memcpy(visibility_last[slot],row,sizeof(visibility_last[slot]));
    visibility_seen|=1u<<slot;
    unsigned id=(unsigned)row[0];
    FILE *f=fopen("sdmc:/3ds/silenthill/stage8_visibility_trace.txt",visibility_rows?"ab":"wb");
    if(f) {
        if(!visibility_rows)fprintf(f,"build=%s\nslot,char,control,anim,x,y,z,health,flags,model_loaded,sys,sysflags,event41,event42,event46,event47,fps,model_calls,packet_bytes,fade\n",SH_BUILD_ID);
        fprintf(f,"%lu",(unsigned long)slot);
        for(unsigned i=0;i<15;i++)fprintf(f,",%ld",(long)row[i]);
        fprintf(f,",%u,%lu,%lu,%lu\n",fps_limit,(unsigned long)(id<64?model_calls[id]:0),
            (unsigned long)(id<64?model_bytes[id]:0),(unsigned long)(id<64?model_fade[id]:0));
        fclose(f);
    }
    visibility_rows++;
}
void game3ds_combat_phase(uint32_t phase_id,uint32_t character,uint32_t control,uint32_t animation,uint32_t attack)
{
    if(!combat_trace || combat_rows>=128)return;
    uint32_t row[5]={phase_id,character,control,animation,attack};
    if(!memcmp(combat_last,row,sizeof(row)))return;
    memcpy(combat_last,row,sizeof(row));
    FILE *f=fopen("sdmc:/3ds/silenthill/stage8_attack_trace.txt",combat_rows?"ab":"wb");
    if(f) {
        if(!combat_rows)fprintf(f,"build=%s\nphase,character,control,animation,attack,map,sys,health\n",SH_BUILD_ID);
        fprintf(f,"%lu,%lu,%lu,%lu,%lu,%lu,%lu,%ld\n",(unsigned long)phase_id,(unsigned long)character,
            (unsigned long)control,(unsigned long)animation,(unsigned long)attack,(unsigned long)current_map,
            (unsigned long)player_state,(long)player_health);fclose(f);
    }
    combat_rows++;
}
static void report(void)
{
#if defined(SH_STAGE11A_LIFETIME)
    static bool lifetime_title_written;
    bool lifetime_terminal=!strcmp(checkpoint,"FAIL") || !strcmp(checkpoint,"EXIT");
    if(!lifetime_terminal && (game_state==11 || game_state==12 || (game_state==7 && lifetime_title_written)))return;
    if(game_state==7 && !strcmp(checkpoint,"TITLE_FRAME_SUBMITTED"))lifetime_title_written=true;
#endif
#if defined(SH_STAGE11A)
    /* SD reports are deferred until the recording has stopped. */
    if(stage11a_perf_active())return;
#endif
    memory_sample();
    uint64_t now=svcGetSystemTick();
    bool terminal=!strcmp(checkpoint,"FAIL") || !strcmp(checkpoint,"EXIT");
    if(!terminal && (game_state==11 || game_state==12) && map_frames>1) {
        /* R3 diagnostic candidate: sparse audio telemetry is on by default,
         * including a clean exit snapshot; no hardware marker is required. */
        unsigned seconds=diagnostic_observe_fast?1:15;
        if(now-last_disk_report<(uint64_t)SYSCLOCK_ARM11*seconds)return;
    }
    last_disk_report=now;
    uint64_t report_start=game_prof_begin();
    char snapshot[4096];
    int size = snprintf(snapshot, sizeof(snapshot),
        "schema=3\nbuild=%s\ncontext=ORIGINAL_MAINLOOP\ncheckpoint=%s\n"
        "phase=%.48s\nphase_detail=%lu\n"
        "first_failure=%lu\noperation=%.64s\ndetail=%lu\nfile_id=%lu\n"
        "game_state=%lu\ngame_step=%lu\nfs_state=%lu\nfs_step=%lu\n"
        "reads=%lu\nuploads=%lu\nframes=%lu\ntitle_frames=%lu\nmap_frames=%lu\ninput=%s\n"
        "draws=%lu\nmax_draws=%lu\nbatches=%lu\ncommand_bytes=%lu\ncommand_percent=%.1f\n"
        "pica_queue_ms=%.4f\npica_queue_valid=%u\n"
        "texture_bytes=%lu\nvertices=%lu\nmask=PICA_STENCIL_FRAMEBUFFER\nmask_updates=%lu\nmask_bits=%lu\n"
        "cache_active=%lu\ncache_peak=%lu\ncache_hits=%lu\ncache_misses=%lu\ncache_evictions=%lu\ncache_peak_pinned=%lu\n"
        "cache_uploads=%lu\ncache_invalidations=%lu\nvram_generation=%lu\n"
        "heap_used=%lu\nheap_free=%lu\nlinear_free=%lu\nlinear_min=%lu\n"
        "player_x=%ld\nplayer_z=%ld\nplayer_yaw=%ld\nplayer_state=%lu\npad_held=%lu\ncontrol_changes=%lu\n"
        "sys_step0=%lu\nsys_step1=%lu\nmap_event=%lu\n"
        "perf_samples=%lu\nframe_ms=%.3f\nframe_worst_ms=%.3f\nfps=%.3f\n"
        "game_ms=%.3f\nprimitive_ms=%.3f\ntexture_ms=%.3f\nsubmit_ms=%.3f\nwait_ms=%.3f\n"
        "recent_samples=%lu\nrecent_frame_ms=%.3f\nrecent_fps=%.3f\nrecent_worst_ms=%.3f\n"
        "recent_primitive_ms=%.3f\nrecent_texture_ms=%.3f\nrecent_submit_ms=%.3f\nrecent_wait_ms=%.3f\nrecent_idle_ms=%.3f\nrecent_begin_wait_ms=%.3f\n"
        "recent_batches=%.2f\nrecent_primitives=%.2f\nrecent_vertices=%.2f\nrecent_cache_comparisons=%.2f\n"
        "recent_misses=%lu\nrecent_evictions=%lu\nrecent_uploads=%lu\nrecent_invalidations=%lu\n"
        "recent_sim_speed=%.4f\nmap_wall_ms=%.1f\nsimulation_ms=%.1f\nraw_simulation_ms=%.1f\n"
        "anim_state=%lu\nupper_state=%lu\nlower_anim=%lu\nupper_anim=%lu\nlower_frame=%lu\nupper_frame=%lu\n"
        "stage4_baseline=HARDWARE_ACCEPTED\nstage5_baseline=HARDWARE_ACCEPTED\nmap=STAGE6_DEVELOPMENT\n",
        SH_BUILD_ID, checkpoint, phase, (unsigned long)phase_detail, (unsigned long)fs_result.first_failure,
        fs_result.operation ? fs_result.operation : "NONE", (unsigned long)fs_result.detail,
        (unsigned long)fs_result.file_id, (unsigned long)game_state, (unsigned long)game_step,
        (unsigned long)fs_result.state, (unsigned long)fs_result.substate,
        (unsigned long)fs_result.reads, (unsigned long)fs_result.uploads, (unsigned long)frames,
        (unsigned long)title_frames, (unsigned long)map_frames,
        stage7_input_enabled ? "DIAGNOSTIC_STAGE7_PAD" : diagnostic_stage6 ? "DIAGNOSTIC_STAGE6_PAD" : diagnostic_garage ? "DIAGNOSTIC_GARAGE_PAD" : diagnostic_stationary ? "DIAGNOSTIC_STATIONARY_PAD" : diagnostic_running ? "DIAGNOSTIC_RUNNING_PAD" : diagnostic_gameplay ? "DIAGNOSTIC_GAMEPLAY_PAD" : diagnostic_input ? "DIAGNOSTIC_PAD_PULSES" : "PHYSICAL",
        (unsigned long)last_draws, (unsigned long)max_draws,(unsigned long)last_batches,
        (unsigned long)render3ds_stats()->command_buffer_bytes,
        (double)(render3ds_stats()->command_buffer_usage * 100),
        (double)render3ds_stats()->gpu_queue_ms,(unsigned)render3ds_stats()->timing_valid,
        (unsigned long)render3ds_stats()->texture_bytes, (unsigned long)render3ds_stats()->vertices_used,
        (unsigned long)game3ds_gpu_mask_updates,(unsigned long)game3ds_gpu_mask_bits,
        (unsigned long)cache.active,(unsigned long)cache.peak,(unsigned long)cache.hits,
        (unsigned long)cache.misses,(unsigned long)cache.evictions,(unsigned long)cache.peak_pinned,(unsigned long)cache.uploads,
        (unsigned long)cache.invalidations,(unsigned long)vram.generation,
        (unsigned long)heap_used,(unsigned long)heap_free,(unsigned long)linear_free,(unsigned long)linear_min,
        (long)player_x,(long)player_z,(long)player_yaw,(unsigned long)player_state,
        (unsigned long)pad_held,(unsigned long)control_changes,
        (unsigned long)sys_step0,(unsigned long)sys_step1,(unsigned long)map_event,(unsigned long)perf_samples,
        average_ms(perf_total),perf_worst_ms,perf_total ? 1000.0/average_ms(perf_total) : 0,
        average_ms(perf_game),average_ms(perf_primitive),average_ms(perf_texture),
        average_ms(perf_submit),average_ms(perf_wait),
        (unsigned long)recent.count,recent_ms(recent.total),recent.total ? 1000.0/recent_ms(recent.total) : 0,recent.worst,
        recent_ms(recent.primitive),recent_ms(recent.texture),recent_ms(recent.submit),recent_ms(recent.wait),recent_ms(recent.idle),
        recent.count ? recent.begin_wait/recent.count : 0,
        recent_work(recent.batches),recent_work(recent.primitives),recent_work(recent.vertices),recent_work(recent.comparisons),
        (unsigned long)recent.misses,(unsigned long)recent.evictions,(unsigned long)recent.uploads,(unsigned long)recent.invalidations,
        recent.total ? recent.sim/(recent.total/CPU_TICKS_PER_MSEC*4.096) : 0,
        sample_start ? (svcGetSystemTick()-sample_start)/CPU_TICKS_PER_MSEC : 0,
        simulation_q12/4.096,raw_simulation_q12/4.096,
        (unsigned long)anim_state,(unsigned long)upper_state,(unsigned long)lower_anim,(unsigned long)upper_anim,
        (unsigned long)lower_frame,(unsigned long)upper_frame);
    if (size < 0 || (unsigned)size >= sizeof(snapshot)) { report_error = 1; return; }
    FILE *out = fopen("sdmc:/3ds/silenthill/stage4_status.txt", "wb");
    if (!out) { report_error = 2; return; }
    static char output_buffer[16384];
    setvbuf(out,output_buffer,_IOFBF,sizeof(output_buffer));
    report_error = 0;
    if (fwrite(snapshot, 1, (size_t)size, out) != (size_t)size) report_error = 3;
    game_prof_report(out);
    game_io_report(out);
    game_audio_report(out);
    game_cpu_audit_report(out);
#if defined(SH_CPU_AUDIT_RECORDER)
    cpu_recorder_reference(out);
#endif
    fprintf(out,"fps_scope=LOGICAL_LCD_PRESENTATIONS\nmap_frames_scope=LEGACY_NATIVE_SUBMISSIONS\n");
    fprintf(out,"control_mode=%u\nnative_settings_error=%u\nfade_presentation_count=%lu\n",
        control_mode,settings_error,(unsigned long)fade_count);
    unsigned fade_start=fade_count>192?fade_count-192:0;
    for(unsigned i=fade_start;i<fade_count;i++) {
        fprintf(out,"fade_present_%u=",i-fade_start);
        for(unsigned j=0;j<10;j++)fprintf(out,j?",%lu":"%lu",(unsigned long)fade_frames[i%192][j]);
        fputc('\n',out);
    }
    fprintf(out,"stage8_fps_limit=%u\nrecent_work_ms=%.3f\nstage8_combat_trace_rows=%u\n",
        fps_limit,recent_ms(recent.total>recent.wait?recent.total-recent.wait:0),combat_rows);
    fprintf(out,"stage8_status_opens=%u\nstage8_status_open_ms=%.3f\nstage8_status_open_work_ms=%.3f\n",
        status_open_count,status_open_ms,status_open_work_ms);
    unsigned used_items=0;
    for(unsigned i=0;i<40;i++)if((inv_slots[i]&255)!=255 && (inv_slots[i]&255)!=0)used_items++;
    fprintf(out,"inventory_count=%u\ninventory_capacity=%lu\ninventory_equipped=%lu\ninventory_selected=%lu\npicked_up_item_count=%lu\n",
        used_items,(unsigned long)inv_count,(unsigned long)inv_equipped,(unsigned long)inv_selected,(unsigned long)inv_pickups);
    for(unsigned i=0;i<40;i++)if((inv_slots[i]&255)!=255 && (inv_slots[i]&255)!=0)fprintf(out,"inventory_slot_%u=%lu,%lu\n",i,(unsigned long)(inv_slots[i]&255),(unsigned long)(inv_slots[i]>>8));
    uint32_t display_width,display_height;game3ds_gpu_extent(&display_width,&display_height);
    fprintf(out,"stage7_display=%lu\nstage7_viewport=%lu,%lu\nmemcard_path=sdmc:/3ds/silenthill/memcard.mcr\nmemcard_format=PS1_RAW_128K\nmemcard_ready=%d\nmemcard_heap_bytes=%u\nmemcard_transaction_extra_peak=131072\nmemcard_linear_bytes=0\nbottom_color_vram_bytes=%u\n",
        (unsigned long)game3ds_gpu_display(),(unsigned long)display_width,(unsigned long)display_height,
        game_card_ready(),game_card_heap_bytes(),render3ds_stats()->target_bytes>384000?307200:0);
    stage4_fs_game_report(out);
    fprintf(out,"gpu_oversize_triangles=%lu\n",(unsigned long)game3ds_gpu_oversize_triangles);
    fprintf(out,"gpu_culled_triangles=%lu\nfeedback_snapshot_heap_bytes=%u\nfeedback_texture_linear_bytes=%u\n",
        (unsigned long)game3ds_gpu_culled_triangles,feedback_words?400*240*2:0,feedback_texture?512*256*4:0);
    fprintf(out,"readback_linear_bytes=%lu\nreadback_gpu_copies=%lu\nreadback_direct_mismatches=%lu\n",
        (unsigned long)render3ds_stats()->readback_bytes,(unsigned long)render3ds_stats()->readback_copies,
        (unsigned long)render3ds_stats()->readback_direct_mismatches);
    unsigned feedback_trace_count=Game3ds_FeedbackTraceRead(0,NULL);
    fprintf(out,"gpu_native_parts=%lu\ngpu_lcd_presents=%lu\ngpu_logical_frames=%lu\ngpu_partial_flushes=%lu\ngpu_max_parts_per_frame=%lu\ngpu_duplicate_presents=%lu\n",
        (unsigned long)render3ds_stats()->native_parts,(unsigned long)render3ds_stats()->lcd_presents,
        (unsigned long)logical_frames,(unsigned long)partial_flushes,(unsigned long)max_parts_per_frame,(unsigned long)duplicate_presents);
    fprintf(out,"feedback_trace_count=%u\n",feedback_trace_count);
    for(unsigned i=0;i<feedback_trace_count;i++) {
        uint32_t row[GAME_FEEDBACK_TRACE_WORDS];Game3ds_FeedbackTraceRead(i,row);
        fprintf(out,"feedback_trace_%u=",i);
        for(unsigned j=0;j<GAME_FEEDBACK_TRACE_WORDS;j++)fprintf(out,j?",%lu":"%lu",(unsigned long)row[j]);
        fputc('\n',out);
    }
    fprintf(out,"normal_heap_peak=%lu\npsx_surface_color_vram=%lu\npsx_surface_stencil_vram=%lu\npresentation_vertices_linear=%u\n",
        (unsigned long)heap_peak,(unsigned long)render3ds_psx_surface_bytes(),(unsigned long)render3ds_psx_surface_bytes(),
        render3ds_psx_surface_bytes()?256:0);
    fprintf(out,"route_leg=%u\nroute_laps=%u\nstage6_pad_route=%u\nstage6_route_leg=%u\n",route_leg,route_laps,diagnostic_stage6,stage6_leg);
    fprintf(out,"map_idx=%lu\nmap_room=%lu\nplayer_health=%ld\ncontrol_disabled=%lu\n",
        (unsigned long)current_map,(unsigned long)current_room,(long)player_health,(unsigned long)control_disabled);
#ifdef SH_3DS_DEV_SCENE
    fprintf(out,"boot_variant=DEVELOPMENT_STAGE10_SCENE_%u\n",SH_3DS_DEV_SCENE);
#elif defined(SH_3DS_DEV_START_MAP)
    fprintf(out,"boot_variant=DEVELOPMENT_MAP_%u\n",SH_3DS_DEV_START_MAP);
#else
    fprintf(out,"boot_variant=NORMAL_NEW_GAME\n");
#endif
    fprintf(out,"route_history_total=%u\nroute_history_capacity=64\n",route_count);
    fprintf(out,"packet_bytes=%lu\npacket_peak=%lu\npacket_capacity=%lu\npacket_buffer=%lu\n",
        (unsigned long)packet_last,(unsigned long)packet_peak,(unsigned long)packet_capacity,(unsigned long)packet_buffer);
    fprintf(out,"start_events=%u\nstart_pauses=%u\nstart_resumes=%u\nstart_passthrough=%u\nstart_schema=event,frame,game,sys,map,room,step0,step1\n",start_events,start_pauses,start_resumes,start_passthrough);
    for(unsigned i=start_events>32?start_events-32:0;i<start_events;i++) {
        unsigned j=i%32;
        fprintf(out,"start_%u=%u,%u,%u,%u,%u,%u,%u,%u\n",i,start_history[j].event,
            start_history[j].frame,start_history[j].game,start_history[j].sys,
            start_history[j].map,start_history[j].room,start_history[j].step0,start_history[j].step1);
    }
    for(unsigned i=route_count>64?route_count-64:0;i<route_count;i++) {
        const RouteState *r=&route_history[i%64];
        fprintf(out,"state_%u=%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%ld,%ld,%ld\n",i,
            (unsigned long)r->frame,(unsigned long)r->map,(unsigned long)r->room,(unsigned long)r->game,
            (unsigned long)r->step,(unsigned long)r->sys,(unsigned long)r->s0,(unsigned long)r->s1,
            (unsigned long)r->event,(long)r->x,(long)r->z,(long)r->health);
    }
    fprintf(out,"skipped_media_count=%u\nskipped_media_overflow=%u\n",skipped_count,skipped_overflow);
    for(unsigned i=0;i<skipped_count;i++)fprintf(out,"skipped_media_%u=%lu,%lu,%lu,%lu\n",i,
        (unsigned long)skipped_media[i].kind,(unsigned long)skipped_media[i].id,
        (unsigned long)skipped_media[i].offset,(unsigned long)skipped_media[i].count);
    fprintf(out,"normal_heap_total=%lu\nnormal_heap_used=%lu\nnormal_heap_free=%lu\nlinear_total=%lu\nlinear_used=%lu\npsx_ram_bytes=3145728\npsx_vram_bytes=1048580\nrenderer_vertex_bytes=%lu\nrenderer_color_bytes=%lu\nrenderer_depth_stencil_bytes=384000\n",
        (unsigned long)envGetHeapSize(),(unsigned long)heap_used,(unsigned long)(envGetHeapSize()-heap_used),
        (unsigned long)envGetLinearHeapSize(),(unsigned long)(envGetLinearHeapSize()-linear_free),
        (unsigned long)render3ds_stats()->vertex_buffer_bytes,(unsigned long)render3ds_stats()->target_bytes);
    if(fputs("report_complete=1\n",out)<0 || fflush(out)) report_error=3;
    if (fclose(out)) report_error = 4;
    game_prof_end(GP_REPORT,report_start);
}
void game3ds_progress(const char *name, uint32_t detail)
{
    phase = name; phase_detail = detail;
#if !defined(SH_PLAYTEST)
    report();
#endif
}
#if defined(SH_PLAYTEST) && defined(SH_PLAYTEST_LIVE_CHECKPOINTS)
/* Two small alternating snapshots preserve the previous completed write if
 * the SD write is interrupted. No timings or subsystem profiler are enabled. */
static void playtest_live_checkpoint(void)
{
    static uint32_t last_frame,sequence;
    if((game_state!=11 && game_state!=12) || map_frames-last_frame<300)return;
    last_frame=map_frames;
    const char *path=(sequence++ & 1)?"sdmc:/3ds/silenthill/playtest_live1.txt":"sdmc:/3ds/silenthill/playtest_live0.txt";
    FILE *f=fopen(path,"wb");if(!f)return;
    fprintf(f,"build=%s\nframe=%lu\nmap_frames=%lu\ngame_state=%lu\ngame_step=%lu\nsys_state=%lu\nsys_step0=%lu\nsys_step1=%lu\nmap=%lu\nroom=%lu\nphase=%.48s\nphase_detail=%lu\nfs_state=%lu\nfs_step=%lu\nfirst_failure=%lu\nlast_recoverable=%.31s\nlast_recoverable_detail=%ld\ncomplete=1\n",
        SH_BUILD_ID,(unsigned long)frames,(unsigned long)map_frames,(unsigned long)game_state,(unsigned long)game_step,
        (unsigned long)player_state,(unsigned long)sys_step0,(unsigned long)sys_step1,(unsigned long)current_map,
        (unsigned long)current_room,phase?phase:"NONE",(unsigned long)phase_detail,(unsigned long)fs_result.state,
        (unsigned long)fs_result.substate,(unsigned long)fs_result.first_failure,
        last_error.operation[0]?last_error.operation:"NONE",(long)last_error.detail);
    fclose(f);
}
#endif
void game3ds_observe(uint32_t state, uint32_t step, uint32_t fs_state, uint32_t fs_step)
{
#if !defined(SH_PLAYTEST)
    int changed = game_state != state || game_step != step;
#endif
    game_state = state; game_step = step; fs_result.state = fs_state; fs_result.substate = fs_step;
    RouteState r={frames,current_map,current_room,state,step,player_state,sys_step0,sys_step1,map_event,player_x,player_z,player_health};
    RouteState *last=route_count?&route_history[(route_count-1)%64]:NULL;
    if(!last || last->map!=r.map || last->room!=r.room || last->game!=r.game || last->step!=r.step ||
       last->sys!=r.sys || last->s0!=r.s0 || last->s1!=r.s1 || last->event!=r.event)
        route_history[route_count++%64]=r;
    checkpoint = map_frames && (state == 11 || state == 12) ? "MAP0_FRAME_SUBMITTED" :
        title_submitted && state == 7 ? "TITLE_FRAME_SUBMITTED" : "ORIGINAL_MAINLOOP";
#if defined(SH_PLAYTEST) && defined(SH_PLAYTEST_LIVE_CHECKPOINTS)
    playtest_live_checkpoint();
#endif
#if !defined(SH_PLAYTEST)
    uint64_t now=svcGetSystemTick();
    /* Polls keep running when no wait is necessary. A wait counter can stop
     * on a multiple of 300, so it must never be the report scheduling clock. */
    if (changed || now-last_observation_report >= (uint64_t)SYSCLOCK_ARM11*(diagnostic_observe_fast?1:5)) {
        last_observation_report=now;
        report();
        if(!game3ds_gpu_display()) {
        printf("\x1b[HStage 10 ORIGINAL MAINLOOP\n%s\nState %lu step %lu\nReads %lu uploads %lu\nFirst FAIL %lu / report %s\nSTART: pause menu\n",
            SH_BUILD_ID, (unsigned long)state, (unsigned long)step, (unsigned long)fs_result.reads,
            (unsigned long)fs_result.uploads, (unsigned long)fs_result.first_failure, report_error ? "ERROR" : "OK");
        printf("Map %lu cache %lu/%u evict %lu\nHeap %lu linear free %lu\n%.1f fps %.1f ms\n",
            (unsigned long)map_frames,(unsigned long)cache.active,GAME_TEXTURE_LIMIT,
            (unsigned long)cache.evictions,(unsigned long)heap_used,(unsigned long)linear_free,
            recent.total ? 1000.0/recent_ms(recent.total) : 0,recent_ms(recent.total));
        gfxFlushBuffers();
        }
    }
#endif
}
void game3ds_halt(uint32_t code, const char *operation, uint32_t detail)
{
    lower_backlight(1);
    hp_led_off();
#if defined(SH_CPU_AUDIT_RECORDER) && !defined(SH_PLAYTEST)
    CpuRecordContext c=cpu_record_context();cpu_recorder_finish(&c,code?"GAME_FAILURE":"FINAL_DUMP");
#endif
    if (code && !fs_result.first_failure) {
        fs_result.first_failure = code; fs_result.operation = operation; fs_result.detail = detail;
    }
    checkpoint = code ? "FAIL" : "EXIT";
    /* Publish a readable failure before GPU drain, file IO, or worker joins:
     * any of those may be the operation that stopped making progress. */
    lower_console_bind();
    consoleClear();
    printf("\x1b[H  SILENT HILL %s\n\n  FAIL %lu\n  %.32s\n  DETAIL %lu\n  STATE %lu STEP %lu\n  MAP %lu ROOM %lu\n\n  REPORT: stage4_status.txt\n",
        checkpoint,(unsigned long)code,operation?operation:"NONE",(unsigned long)detail,
        (unsigned long)game_state,(unsigned long)game_step,(unsigned long)current_map,(unsigned long)current_room);
    gfxFlushBuffers();gfxScreenSwapBuffers(GFX_BOTTOM,false);
    draw_count = 0;
    render3ds_end_frame();
    report();
    longjmp(exit_game, 1);
}
uint32_t game3ds_read_pad(void)
{
    static unsigned start_held;
    static unsigned brightness_chord;
    static unsigned select_pending,select_consumed;
    game_prof_frame();
#if !defined(SH_PLAYTEST)
    game_cpu_audit_poll();
#endif
    if (!aptMainLoop()) game3ds_halt(0, "APT exit", 0);
    hidScanInput();
    uint32_t held = hidKeysHeld();
#if defined(SH_CPU_AUDIT_RECORDER) && !defined(SH_PLAYTEST)
    CpuRecordContext c=cpu_record_context();
#if defined(SH_STAGE11A_LIFETIME)
    stage11a_lifetime_poll(&c);
#endif
    held=cpu_recorder_input(held,&c);
    cpu_record_indicator();
#endif
    held|=game_stage7_input_pad(player_x,player_z,player_yaw,game_state,player_state);
    if(stage7_stop_route)diagnostic_stage6=false;
    unsigned raw_select=held&KEY_SELECT;
    unsigned chord=raw_select && !(held&KEY_START) && Game3ds_CanPause()
        ? held&(KEY_DUP|KEY_DDOWN|KEY_DRIGHT|KEY_DLEFT) : 0;
    unsigned chord_down=chord&~brightness_chord;
    brightness_chord=chord;
    if(chord) {
        select_consumed=1;
        unsigned before=game_lower_brightness,invert_before=game_map_invert,map_before=game_map_enabled;
        if(chord_down==KEY_DUP && game_lower_brightness<10)++game_lower_brightness;
        else if(chord_down==KEY_DDOWN && game_lower_brightness>1)--game_lower_brightness;
        else if(chord_down==KEY_DRIGHT)game_map_invert=!game_map_invert;
        else if(chord_down==KEY_DLEFT)game_map_enabled=!game_map_enabled;
        if(before!=game_lower_brightness || invert_before!=game_map_invert || map_before!=game_map_enabled)settings_save();
        held&=~(KEY_DUP|KEY_DDOWN|KEY_DRIGHT|KEY_DLEFT);
    }
    /* Defer a plain SELECT until release so SELECT followed by a direction
     * cannot open the original map before the brightness chord is recognized. */
    if(raw_select && !(held&KEY_START) && Game3ds_CanPause()) {
        select_pending=1;held&=~KEY_SELECT;
    } else if(!raw_select && select_pending) {
        if(!select_consumed && Game3ds_CanPause())held|=KEY_SELECT;
        select_pending=select_consumed=0;
    } else if(raw_select && (held&KEY_START)) {
        select_pending=select_consumed=0;
    }
    unsigned start_down=(held&KEY_START) && !start_held;
    start_held=(held&KEY_START)!=0;
    if(start_down && !(held&KEY_SELECT) && Game3ds_CanOpenPause()) {
        start_pauses++;start_event(1);
        pause_menu();held=0;start_held=0;
        start_resumes++;start_event(2);
    } else if(start_down) {
        start_passthrough++;start_event(3);
    }
    if ((held & (KEY_START | KEY_SELECT)) == (KEY_START | KEY_SELECT))
        game3ds_halt(0, "START+SELECT exit", 0);
    input_polls++;
    input_title_age = game_state == 7 ? input_title_age + 1 : 0;
    if (diagnostic_input && (input_title_age == 90 || input_title_age == 150)) held |= KEY_B;
    if ((diagnostic_gameplay || diagnostic_stationary) && game_state==11 && player_state==10 && !(input_polls%120)) held|=KEY_B;
#if defined(SH_3DS_DEV_SCENE) && SH_3DS_DEV_SCENE==5
    /* Exercise MAP2's original START skip at the physical pad boundary. */
    if(diagnostic_gameplay && game_state==11 && player_state==10 && !(input_polls%120))held|=KEY_START;
#endif
    if (diagnostic_stage6 && game_state==11)
        held|=game_stage6_input_pad(current_map,player_state,player_x,player_z,player_yaw);
    else if (diagnostic_garage && game_state==11 && player_state==0)
        held|=game_route_pad(player_x,player_z,player_yaw,&route_leg,&route_laps);
    else if (diagnostic_gameplay && game_state==11 && player_state==0) {
        /* Repeating short walk/turn/backward sequence through the ordinary
         * physical pad boundary. No player, camera or game state is written. */
        unsigned age=gameplay_input_age++ % 720;
        if (age>=60 && age<(diagnostic_running?120u:180u)) {held|=KEY_DUP;if(diagnostic_running)held|=KEY_Y;}
        if (age>=240 && age<300) held|=KEY_DRIGHT;
        if (age>=360 && age<480) held|=KEY_DDOWN;
        if (age>=540 && age<600) held|=KEY_DLEFT;
    }
    return held;
}
void game3ds_read_analog(int *cx,int *cy,int *rx,int *ry)
{
    circlePosition circle={0},look={0};
    hidCircleRead(&circle);hidCstickRead(&look);
    *cx=circle.dx;*cy=circle.dy;*rx=look.dx;*ry=look.dy;
}
uint32_t game3ds_wait_vblank(void)
{
    uint64_t wait_start=svcGetSystemTick();
    gspWaitForVBlank(); wait_ticks+=svcGetSystemTick()-wait_start; frames++;
    if(game_prof_enabled)game_prof_add(GP_VBLANK,svcGetSystemTick()-wait_start);
    return 0;
}
static void perf_present(uint64_t end)
{
#if defined(SH_PLAYTEST)
    if ((game_state==11 || game_state==12) && previous_submit && map_frames>60) {
        window.count++;window.total+=end-previous_submit;
        if(window.count==120){recent=window;memset(&window,0,sizeof(window));}
    }
    previous_submit=end;wait_ticks=primitive_ticks=0;
#else
    if ((game_state==11 || game_state==12) && previous_submit && map_frames>60) {
        uint64_t total=end-previous_submit,texture=frame_work.texture,submit=frame_work.submit;
        perf_samples++;perf_total+=total;perf_texture+=texture;perf_submit+=submit;
        perf_wait+=wait_ticks;perf_primitive+=primitive_ticks;
        perf_game+=total>texture+submit+wait_ticks?total-texture-submit-wait_ticks:0;
        double ms=total/CPU_TICKS_PER_MSEC;if(ms>perf_worst_ms)perf_worst_ms=ms;
        window.count++;window.total+=total;window.texture+=texture;window.submit+=submit;
        window.primitive+=primitive_ticks;window.wait+=wait_ticks;
        window.idle+=render3ds_stats()->idle_ticks-prior_idle_ticks;
        window.sim+=simulation_q12-prior_simulation;
        window.begin_wait+=frame_work.begin_wait;
        window.primitives+=frame_work.primitives;window.batches+=frame_work.batches;
        window.vertices+=frame_work.vertices;window.comparisons+=frame_work.comparisons;
        window.misses+=frame_work.misses;window.evictions+=frame_work.evictions;
        window.uploads+=frame_work.uploads;window.invalidations+=frame_work.invalidations;
        if(ms>window.worst)window.worst=ms;
        if(window.count==120){recent=window;memset(&window,0,sizeof(window));}
    }
    previous_submit=end;wait_ticks=primitive_ticks=0;
    if(!sample_start && (game_state==11 || game_state==12))sample_start=end;
#endif
}
void game3ds_gpu_begin_draw(void)
{
    defer_present=true;begin_parts=render3ds_stats()->native_parts;begin_presents=render3ds_stats()->lcd_presents;
#if !defined(SH_PLAYTEST)
    memset(&frame_work,0,sizeof(frame_work));
    prior_idle_ticks=render3ds_stats()->idle_ticks;prior_simulation=simulation_q12;
#endif
}
static void integration_overlap_dispatch(int wait);
void game3ds_gpu_end_draw(void)
{
    defer_present=false;
    if(lower_owns && game3ds_gpu_display()==1) {
        gfxSetDoubleBuffering(GFX_BOTTOM,false);lower_owns=0;
    }
    static char counter[40];static uint64_t counter_total;static unsigned counter_mode=~0u;
    if(game_overlay_mode!=counter_mode || recent.total!=counter_total) {
        double ms=recent_ms(recent.total),fps=ms>0?1000.0/ms:0;
        counter_mode=game_overlay_mode;counter_total=recent.total;
        if(game_overlay_mode==1)snprintf(counter,sizeof(counter),"FPS %.1f",fps);
        else if(game_overlay_mode==2)snprintf(counter,sizeof(counter),"%.1f MS",ms);
        else if(game_overlay_mode==3)snprintf(counter,sizeof(counter),"%.1f FPS %.1f MS",fps,ms);
        else counter[0]=0;
    }
    if(game_state==11 && game3ds_gpu_display()==0) integration_overlap_dispatch(0);
    else game3ds_gpu_sync();
    if(native_dirty) {
#if !defined(SH_PLAYTEST)
        uint64_t begin=svcGetSystemTick();
#endif
        if(!render3ds_present_psx())game3ds_halt(434,"PICA final presentation",0);
#if !defined(SH_PLAYTEST)
        frame_work.submit+=svcGetSystemTick()-begin;
#endif
        native_dirty=false;
    }
    uint32_t parts=render3ds_stats()->native_parts-begin_parts;
    uint32_t presents=render3ds_stats()->lcd_presents-begin_presents;
    logical_frames++;if(parts>max_parts_per_frame)max_parts_per_frame=parts;
    if(presents>1)duplicate_presents+=presents-1;
    /* One FPS sample per completed LCD frame, regardless of readback parts. */
    if(presents)perf_present(svcGetSystemTick());
    unsigned lower_owner_now=Game3ds_LowerOwner(game3ds_gpu_display(),lower_start_active);
    if(lower_owner_now==LOWER_GAME_DRAW) {
        if(!lower_owns) {render3ds_console_bottom();gfxSetDoubleBuffering(GFX_BOTTOM,true);lower_owns=1;}
        u16 w,h;uint16_t *fb=(uint16_t*)gfxGetFramebuffer(GFX_BOTTOM,GFX_LEFT,&w,&h);
        int drawn=Game3ds_LowerDraw(fb);
        if(drawn)Game3ds_LowerCounter(fb,counter);
        if(drawn) {gfxFlushBuffers();gfxScreenSwapBuffers(GFX_BOTTOM,false);}
    } else if(lower_owner_now==LOWER_SPECIAL) {
        if(lower_owns && game3ds_gpu_display()!=1) {
            lower_console();consoleClear();gfxFlushBuffers();
        }
        lower_owns=0;
    }
    static uint32_t last_feedback_generation;
    uint32_t fade=Game3ds_FadeState();
    if(presents && (feedback_generation!=last_feedback_generation || (fade&65535))) {
        uint32_t *row=fade_frames[fade_count++%192];
        const uint32_t values[]={simulation_tick,logical_frames,game3ds_vblank_clock(),
            game3ds_q12_clock(),fade>>16,fade&65535,feedback_generation,feedback_color,last_sim_dt,parts};
        memcpy(row,values,sizeof(values));
    }
    last_feedback_generation=feedback_generation;
}
static void integration_overlap_dispatch(int wait)
{
    if(game3ds_gpu_display()==2) {draw_count=primitive_count=staged_vertices=0;native_dirty=false;return;}
    if (draw_count) {
        if(trace_pending && map_frames>700 && player_state==0) { trace_pending=false; trace_primitives(); }
#if !defined(SH_PLAYTEST)
        uint64_t begin=svcGetSystemTick();
#endif
        uint64_t pin_start=game_prof_begin();
        game_texture_begin(&cache);
        /* Submission-local keys only. VRAM writes and feedback-color changes
         * flush this submission, so an earlier resolved pointer is immutable.
         * Reserve ALL resident unique keys before acquiring any missing key. */
        uint32_t key_index[256]={0};
        for(unsigned i=0;i<draw_count;i++)if(draws[i].textured) {
            struct GameDraw *d=&draws[i];d->texture_source=i;
            if(d->page==GAME_FEEDBACK_PAGE)continue;
            unsigned hash=(d->page*0x9e3779b9u^d->clut*0x85ebca6bu);hash=(hash^(hash>>16))&255;
            for(unsigned n=0;n<256;n++,hash=(hash+1)&255) {
                unsigned prior=key_index[hash];
                if(!prior){key_index[hash]=i+1;game_texture_pin(&cache,d->page,d->clut);break;}
                if(draws[prior-1].page==d->page && draws[prior-1].clut==d->clut){d->texture_source=prior-1;break;}
                /* Overflow remains correct: the existing cache limit reports
                 * too many simultaneous keys during acquisition. */
                if(n==255)game_texture_pin(&cache,d->page,d->clut);
            }
        }
        game_prof_end(GP_CACHE,pin_start);
        for(unsigned i=0;i<draw_count;i++)if(draws[i].textured)draws[i].texture=
            draws[i].texture_source==i?texture_for(&draws[i]):draws[draws[i].texture_source].texture;
#if !defined(SH_PLAYTEST)
        uint64_t texture_end=svcGetSystemTick();
        game_prof_count(GC_CACHE_PROBES,(uint32_t)(cache.comparisons-prior_comparisons));
#endif
        uint64_t submit_start=game_prof_begin();
        game_prof_count(GC_PRIMITIVES,primitive_count);game_prof_count(GC_BATCHES,draw_count);
        uint32_t viewport_width,viewport_height;game3ds_gpu_extent(&viewport_width,&viewport_height);
        uint32_t display=game3ds_gpu_display(),token=game3ds_gpu_frame_token();
        if(!render3ds_set_display(display))game3ds_halt(420,"display target allocation/routing",display);
        /* GP0 copies may flush part of one ordering table. Resume the same
         * native surface instead of clearing primitives emitted before copy. */
        render3ds_continue_psx_frame(token==last_submit_token && display==last_submit_display);
        if (!render3ds_begin_psx_frame(viewport_width,viewport_height)) game3ds_halt(434, "PICA native FrameBegin", (viewport_width<<16)|viewport_height);
        render3ds_set_scissor(0,0,viewport_width,viewport_height);
        uint64_t commands=game_prof_begin();
        for (unsigned i=0; i<draw_count; i++) {
            render3ds_set_scissor(draws[i].clip[0],draws[i].clip[1],draws[i].clip[2],draws[i].clip[3]);
            render3ds_set_psx_mask(draws[i].mask);
            if (!render3ds_draw_psx_ordered(staging_vertices+draws[i].first,draws[i].count,
                primitive_sizes+draws[i].first_primitive,draws[i].primitives,draws[i].texture,draws[i].blend))
                game3ds_halt(435, "PICA vertex budget/draw", i);
        }
        last_draws = primitive_count; last_batches=draw_count;
        if (last_draws > max_draws) max_draws = last_draws;
        game_prof_end(GP_COMMAND,commands);
        draw_count = 0; primitive_count=0; staged_vertices=0;
        uint64_t present=game_prof_begin();
        if(defer_present || vram_target_active){render3ds_end_psx_part();native_dirty=true;partial_flushes++;}
        else {render3ds_end_frame();native_dirty=false;}
        game_prof_end(GP_PRESENT,present);
        if(!vram_target_active)game3ds_gpu_frame_complete();
        last_submit_token=token;last_submit_display=display;
        uint64_t end=svcGetSystemTick();
        if(display==1 && status_open_start) {
            uint64_t elapsed=end-status_open_start,pacing=wait_ticks-status_open_wait;
            status_open_ms=elapsed/CPU_TICKS_PER_MSEC;
            status_open_work_ms=(elapsed>pacing?elapsed-pacing:0)/CPU_TICKS_PER_MSEC;
            status_open_count++;status_open_start=0;
        }
        game_prof_end(GP_SUBMIT,submit_start);
#if !defined(SH_PLAYTEST)
        frame_work.texture+=texture_end-begin;frame_work.submit+=end-texture_end;
        frame_work.begin_wait+=render3ds_stats()->begin_wait_ms;
        frame_work.primitives+=last_draws;frame_work.batches+=last_batches;
        frame_work.vertices+=render3ds_stats()->vertices_used;
        frame_work.comparisons+=(uint32_t)(cache.comparisons-prior_comparisons);
        frame_work.misses+=(uint32_t)(cache.misses-prior_misses);
        frame_work.evictions+=(uint32_t)(cache.evictions-prior_evictions);
        frame_work.uploads+=(uint32_t)(cache.uploads-prior_uploads);
        frame_work.invalidations+=(uint32_t)(cache.invalidations-prior_invalidations);
        prior_comparisons=cache.comparisons; prior_misses=cache.misses; prior_evictions=cache.evictions;
        prior_uploads=cache.uploads; prior_invalidations=cache.invalidations;
#endif
        if (game_state == 7) title_frames++;
        if (game_state == 11 || game_state == 12) {
            map_frames++;
            if (map_frames == 1 || !(map_frames % 300)) {
#if !defined(SH_PLAYTEST)
                checkpoint="MAP0_FRAME_SUBMITTED"; report();
#endif
            }
        }
        if (game_state == 7 && title_frames >= 60 && !title_submitted) {
            title_submitted = true; checkpoint = "TITLE_FRAME_SUBMITTED";
#if !defined(SH_PLAYTEST)
            report();
#endif
        }
    }
    if(wait)render3ds_wait_idle();
}
void game3ds_gpu_sync(void) {integration_overlap_dispatch(1);}
void integration_overlap_begin_update(void) {if(draw_count)game3ds_gpu_sync();}
typedef struct {unsigned x,y,w,h;} VramTarget;
static VramTarget vram_target_rect;
static unsigned vram_target_width,vram_target_margin;
static uint32_t vram_saved_token,vram_saved_display;
static bool vram_seed_row(void *context,unsigned y,uint8_t *rgba,unsigned width)
{
    VramTarget *r=context;
    if(y>=r->h || width!=r->w)return false;
    for(unsigned x=0;x<width;x++) {
        uint16_t p=vram.words[(r->y+y)*1024+r->x+x];
        unsigned red=p&31,green=(p>>5)&31,blue=(p>>10)&31;
        uint32_t color=((red<<3)|(red>>2))|(((green<<3)|(green>>2))<<8)|
            (((blue<<3)|(blue>>2))<<16)|((p&0x8000)?0x80000000u:(p?0xff000000u:0));
        memcpy(rgba+x*4,&color,4);
    }
    return true;
}
void game3ds_vram_target_begin(unsigned x,unsigned y,unsigned w,unsigned h,unsigned view_width)
{
    if(vram_target_active || !w || !h || x+w>1024 || y+h>512 || view_width<w || view_width>400)
        game3ds_halt(462,"VRAM target bounds",0);
    game3ds_gpu_sync();
    vram_saved_token=last_submit_token;vram_saved_display=last_submit_display;vram_saved_dirty=native_dirty;
    if(!render3ds_select_vram_surface(true))game3ds_halt(462,"VRAM target select",0);
    vram_target_rect=(VramTarget){x,y,w,h};
    vram_target_width=view_width;vram_target_margin=(view_width-w)/2;
    unsigned pw=0,ph=0;
    Render3dsTexture *seed=render3ds_texture_create_rows(w,h,vram_seed_row,&vram_target_rect,&pw,&ph);
    if(!seed || !render3ds_begin_psx_frame(view_width,h))game3ds_halt(462,"VRAM target seed",0);
    float u=(float)w/pw,v=1.0f-(float)h/ph;
    float left=vram_target_margin,right=left+w;
    Render3dsVertex q[6]={{left,0,0,0,1,1,1,1,1},{right,0,0,u,1,1,1,1,1},{left,h,0,0,v,1,1,1,1},
        {right,0,0,u,1,1,1,1,1},{right,h,0,u,v,1,1,1,1},{left,h,0,0,v,1,1,1,1}};
    render3ds_texture_psx_coverage(seed,3);render3ds_set_psx_mask(0);
    if(!render3ds_draw_psx_triangles(q,6,seed,0))game3ds_halt(462,"VRAM target seed draw",0);
    render3ds_end_psx_part();render3ds_texture_destroy(seed);
    vram_target_active=true;last_submit_token=game3ds_gpu_frame_token();last_submit_display=game3ds_gpu_display();native_dirty=false;
}
void game3ds_vram_target_end(void)
{
    if(!vram_target_active)return;
    game3ds_gpu_sync();
    VramTarget r=vram_target_rect;
    if(vram_target_width>r.w)game3ds_feedback_capture(vram_target_width,r.h);
    if(!render3ds_read_psx(vram_target_margin,0,r.w,r.h,vram.words+r.y*1024+r.x,1024))game3ds_halt(462,"VRAM target resolve",0);
    vram.generation++;
    game3ds_gpu_dirty_rect(r.x,r.y,r.w,r.h);
    if(!render3ds_select_vram_surface(false))game3ds_halt(462,"VRAM target restore",0);
    vram_target_active=false;last_submit_token=vram_saved_token;last_submit_display=vram_saved_display;native_dirty=vram_saved_dirty;
}
void game3ds_gpu_dirty(void)
{
    game3ds_gpu_dirty_rect(0,0,1024,512);
}
void game3ds_gpu_dirty_rect(uint32_t x, uint32_t y, uint32_t w, uint32_t h)
{
    game3ds_gpu_sync();
    Game3ds_FeedbackInvalidate(x,y,w,h);
    game_texture_invalidate(&cache,(PsxRect){x,y,w,h});
}
void game3ds_gpu_rect(const float *vertices, uint32_t count, uint32_t page, uint32_t clut, uint32_t textured, uint32_t blend)
{
    int clip[4];game3ds_gpu_clip(&clip[0],&clip[1],&clip[2],&clip[3]);
    unsigned feedback=(page&GAME_FEEDBACK_PAGE)!=0;
    if(feedback) {
        clut=(unsigned)(vertices[5]*128+.5f)|((unsigned)(vertices[6]*128+.5f)<<8)|
            ((unsigned)(vertices[7]*128+.5f)<<16);
        if(feedback_staged_color!=clut && draw_count)game3ds_gpu_sync();
        feedback_staged_color=clut;page=GAME_FEEDBACK_PAGE;
    } else page &= 0x19f|GAME_STATUS_FONT_PAGE; /* ABR is separate draw state. */
    if (!textured) page=clut=0;
    else if ((page>>7)==2) clut=0; /* 16-bit texels do not use a CLUT. */
    if ((count != 3 && count != 6) || primitive_count == DRAW_LIMIT || count>VERTEX_LIMIT-staged_vertices)
        game3ds_halt(436, "game draw budget", primitive_count);
    struct GameDraw *d=draw_count ? &draws[draw_count-1] : NULL;
    /* Merge only adjacent equal state. Painter/OT order is preserved. */
    if (!d || d->page!=page || d->clut!=clut || d->textured!=textured || d->blend!=blend || d->mask!=game3ds_gpu_mask_bits || memcmp(d->clip,clip,sizeof(clip))) {
        d=&draws[draw_count++]; d->first=staged_vertices; d->count=0;
        d->first_primitive=primitive_count;d->primitives=0;
        d->page=page; d->clut=clut; d->textured=textured; d->blend=blend; d->texture=NULL;
        d->mask=game3ds_gpu_mask_bits;
        memcpy(d->clip,clip,sizeof(clip));
    }
    Render3dsVertex *out=staging_vertices+staged_vertices;
    memcpy(out,vertices,count*sizeof(*out));d->count+=count;staged_vertices+=count;
    if(feedback)for(unsigned i=0;i<count;i++)out[i].r=out[i].g=out[i].b=1;
    primitive_sizes[primitive_count++]=count;d->primitives++;
    float alpha = blend == 1 ? 0.5f : blend == 4 ? 0.25f : 1.0f;
    for (unsigned i=0; i<count; i++) out[i].a = alpha;
}
int game3ds_gpu_readback(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint16_t *out,uint32_t stride)
{return render3ds_read_psx(x,y,w,h,out,stride);}
int game3ds_gpu_resolve(uint32_t x,uint32_t y,uint32_t w,uint32_t h,uint32_t ow,uint32_t oh,uint16_t *out,uint32_t stride)
{return render3ds_resolve_psx(x,y,w,h,ow,oh,out,stride);}
int main(void)
{
    gfxInitDefault();
    hp_led_ready = R_SUCCEEDED(mcuHwcInit());
    GSPGPU_SetLcdForceBlack(true);
    /* Initialize both CPU framebuffer pairs before allowing scanout. Render
     * targets are separately cleared before their first display transfer. */
    for(unsigned pair=0;pair<2;pair++) {
        for(unsigned eye=0;eye<2;eye++) {
            u16 w,h;u8 *pixels=gfxGetFramebuffer(GFX_TOP,eye?GFX_RIGHT:GFX_LEFT,&w,&h);
            memset(pixels,0,(size_t)w*h*3);
        }
        gfxFlushBuffers();gfxSwapBuffers();gspWaitForVBlank();
    }
    GSPGPU_SetLcdForceBlack(false);
    lower_console_instance=consoleInit(GFX_BOTTOM, NULL); gfxSetDoubleBuffering(GFX_BOTTOM,false); osSetSpeedupEnable(true);
    if (!setjmp(exit_game)) {
        FILE *attack_debug=fopen("sdmc:/3ds/silenthill/stage8_debug.txt","rb");
        if(attack_debug) {
            char token[16]={0};size_t n=fread(token,1,sizeof(token)-1,attack_debug);fclose(attack_debug);
            remove("sdmc:/3ds/silenthill/stage8_debug.txt");
            if(n!=7 || memcmp(token,"ATTACK\n",7))game3ds_halt(456,"Stage 8 debug marker",n);
            combat_trace=1;
        }
        FILE *stage7_fixture=fopen("sdmc:/3ds/silenthill/stage7_input.txt","rb");
        if(stage7_fixture) {
            char token[24]={0};size_t n=fread(token,1,sizeof(token)-1,stage7_fixture);fclose(stage7_fixture);
            remove("sdmc:/3ds/silenthill/stage7_input.txt");
            if(n!=16 || memcmp(token,"STAGE7_LIVE_PAD\n",16))game3ds_halt(456,"Stage 7 input fixture",n);
            stage7_input_enabled=1;
        }
        FILE *observe=fopen("sdmc:/3ds/silenthill/stage6_observe.txt","rb");
        if(observe) {
            char token[16]={0};size_t n=fread(token,1,sizeof(token)-1,observe);fclose(observe);
            remove("sdmc:/3ds/silenthill/stage6_observe.txt");
            diagnostic_observe_fast=n==13 && !memcmp(token,"OBSERVE_FAST\n",13);
            if(!diagnostic_observe_fast && (n!=8 || memcmp(token,"OBSERVE\n",8)))
                game3ds_halt(456,"Stage 6 observation fixture",n);
            diagnostic_observe=true;
        }
        int stage6_fixture=game_stage6_input_load();
        if(stage6_fixture<0)game3ds_halt(456,"Stage 6 pad itinerary",0);
        diagnostic_stage6=stage6_fixture>0;
        diagnostic_input=diagnostic_stage6;
        FILE *cache_mode=fopen("sdmc:/3ds/silenthill/stage5_io_cache.txt","rb");
        if(cache_mode) {
            char token[8]={0};fread(token,1,sizeof(token)-1,cache_mode);fclose(cache_mode);
            remove("sdmc:/3ds/silenthill/stage5_io_cache.txt");token[strcspn(token,"\r\n")]=0;
            if(strcmp(token,"OFF"))game3ds_halt(458,"resource cache fixture",0);
            stage4_fs_game_cache_enable(0);
        }
#if !defined(SH_PLAYTEST)
        FILE *profiling=fopen("sdmc:/3ds/silenthill/stage5_profile.txt","rb");
        if(profiling) {
            char value[16]={0};fread(value,1,sizeof(value)-1,profiling);fclose(profiling);
            remove("sdmc:/3ds/silenthill/stage5_profile.txt");
            value[strcspn(value,"\r\n")]=0;
            if(!strcmp(value,"DETAIL1"))game_prof_enable(1);
            else if(!strcmp(value,"DETAIL16"))game_prof_enable(16);
            else game3ds_halt(457,"profile fixture",0);
        }
        game_prof_enable(16);game_cpu_audit_init(game_prof_enabled);
#endif
        if (!render3ds_init()) game3ds_halt(420, render3ds_stats()->error, 0);
        FILE *trace=fopen("sdmc:/3ds/silenthill/stage5_capture.txt","rb");
        if(trace) { fclose(trace); remove("sdmc:/3ds/silenthill/stage5_capture.txt"); trace_pending=true; }
        /* One-use Azahar input fixture. It enters through the physical pad
         * boundary; original Joy/menu/difficulty/map selection remain intact. */
        FILE *fixture=fopen("sdmc:/3ds/silenthill/stage4_autoinput.txt","rb");
        if (fixture) {
            char value[32]={0}; size_t bytes=fread(value,1,sizeof(value)-1,fixture);
            fclose(fixture); remove("sdmc:/3ds/silenthill/stage4_autoinput.txt");
            diagnostic_garage=bytes==sizeof("STAGE5_GARAGE_PAD_INPUT\n")-1 && !memcmp(value,"STAGE5_GARAGE_PAD_INPUT\n",bytes);
            diagnostic_running=bytes==sizeof("STAGE5_RUNNING_PAD_INPUT\n")-1 &&
                !memcmp(value,"STAGE5_RUNNING_PAD_INPUT\n",bytes);
            diagnostic_gameplay=diagnostic_garage || diagnostic_running || (bytes==sizeof("STAGE5_GAMEPLAY_PAD_INPUT\n")-1 &&
                !memcmp(value,"STAGE5_GAMEPLAY_PAD_INPUT\n",bytes));
            diagnostic_stationary=bytes==sizeof("STAGE5_STATIONARY_PAD_INPUT\n")-1 &&
                !memcmp(value,"STAGE5_STATIONARY_PAD_INPUT\n",bytes);
            diagnostic_input=diagnostic_stage6 || diagnostic_gameplay || diagnostic_stationary || (bytes==sizeof("STAGE4_LEVEL_B_PAD_INPUT\n")-1 &&
                !memcmp(value,"STAGE4_LEVEL_B_PAD_INPUT\n",bytes));
            if (!diagnostic_input) game3ds_halt(456,"diagnostic input fixture",bytes);
        }
        game_audio_init();
        settings_load();
        lower_lcd_ready=1;
        if(R_SUCCEEDED(lower_lcd_get(&lower_lcd_normal)) && lower_lcd_normal>=16 && lower_lcd_normal<=172)
            lower_lcd_level=lower_lcd_normal;
        else lower_lcd_normal=0;
        aptHook(&lower_apt_cookie,lower_apt_hook,NULL);
        lower_apt_hooked=1;
#if defined(SH_CPU_AUDIT_RECORDER) && !defined(SH_PLAYTEST)
        cpu_recorder_init("sdmc:/3ds/silenthill",SH_BUILD_ID);
#endif
        report();
#if defined(SH_3DS_FMV) && defined(SH_FMV_DEV_MOVIE)
        /* Compile-only opt-in: no game state, saves or progression run. */
        {
            int result=game_fmv_play(SH_FMV_DEV_MOVIE,0);
            game3ds_halt(0,"FMV developer entry complete",(uint32_t)result);
        }
#else
        game3ds_run(&fs_result, &vram);
#endif
    }
    game3ds_gpu_sync(); game_audio_shutdown(); game_audio_cd_close(); stage4_fs_game_close(); report();
    lower_backlight(1);
    lower_console();consoleClear();gfxFlushBuffers();gfxScreenSwapBuffers(GFX_BOTTOM,false);
    while (aptMainLoop()) {
        hidScanInput();
        if (hidKeysDown() & KEY_START) break;
        printf("\x1b[HStage 10 ORIGINAL MAINLOOP\n%s\n%s\nFAIL %lu / %.48s\nDetail %lu file %lu\nState %lu step %lu\nReads %lu uploads %lu\nReport %s\nSTART: exit\n",
            SH_BUILD_ID, checkpoint, (unsigned long)fs_result.first_failure,
            fs_result.operation ? fs_result.operation : "NONE", (unsigned long)fs_result.detail,
            (unsigned long)fs_result.file_id, (unsigned long)game_state, (unsigned long)game_step,
            (unsigned long)fs_result.reads, (unsigned long)fs_result.uploads, report_error ? "ERROR" : "OK");
        gfxFlushBuffers(); gspWaitForVBlank();
    }
    free(feedback_words);feedback_words=NULL;
    if (hp_led_ready) {
        InfoLedPattern off = {0};
        MCUHWC_SetInfoLedPattern(&off);
        mcuHwcExit();
    }
    if(lower_apt_hooked)aptUnhook(&lower_apt_cookie);
    render3ds_shutdown(); gfxExit(); return 0;
}
