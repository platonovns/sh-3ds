/* Bounded native PsyQ OT bridge. No desktop GPU core or replacement producer. */
#include "game.h"
#include "game3ds.h"
#include "game_pad.h"
#include "game_controls.h"
#include "game_profile.h"
#include "game_render_budget.h"
#include "game_screen.h"
#include "game_display.h"
#include "game_lower_policy.h"
#include "game_feedback.h"
#include "game_feedback_cadence.h"
#include "bodyprog/bodyprog.h"
#include "render_3ds.h"
#include "bodyprog/player.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/screen/screen_draw.h"
#include "bodyprog/screen/background_draw.h"
#include "bodyprog/screen/cutscene_border.h"
#include <psyq/libgs.h>
#include <psyq/libetc.h>
#include <string.h>

extern PsxVram *game3ds_canonical;
extern void Game3ds_Observe(void);
extern char __exidx_end, __bss_end__;
OT_TAG prim_terminator;
PACKET *GsOUT_PACKET_P;
DISPENV GsDISPENV;
DRAWENV GsDRAWENV;
s32 g_ActiveBufferIdx;
s32 g_Screen_FadeStatus;
static DRAWENV draw;
static unsigned width = 320, height = 240, active_buffer;
static uint32_t frame_token;
uint32_t game3ds_gpu_frame_token(void) {return frame_token;}
int Game3ds_FeedbackDecay(unsigned period)
{
    static GameFeedbackCadence cadence;
    return game_feedback_decay(&cadence,game3ds_vblank_clock(),frame_token,period);
}
unsigned game3ds_classic_view=SH_3DS_CLASSIC;
void Game3ds_ClassicView(unsigned classic) {game3ds_classic_view=classic!=0;}
static int draw_origin_y;
static int offscreen_active;
static RECT16 offscreen_rect;
static unsigned offscreen_width,offscreen_margin;
static RECT16 completed_target;
static uint32_t completed_target_frame;
static int completed_target_valid;
static GameDisplayPlan plan={0,320,240,0,0},last_plan;
static unsigned background_2d;
void Game3ds_Background2D(void) {background_2d=1;}
static RECT16 last_frame;
static int frame_valid;
static unsigned update_state;
static int frame_captured;
static unsigned feedback_world;
static unsigned feedback_ready;
static unsigned feedback_origin_y;
static uint32_t feedback_trace[96][GAME_FEEDBACK_TRACE_WORDS];
static unsigned feedback_trace_count,feedback_trace_active;
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
static uint32_t lt_feedback_invalidations,lt_feedback_ready_at_write;
void stage11a_lifetime_feedback(uint32_t out[8])
{
    out[0]=lt_feedback_invalidations;out[1]=lt_feedback_ready_at_write;
    out[2]=frame_captured;out[3]=frame_valid;out[4]=feedback_ready;out[5]=feedback_world;
    out[6]=feedback_trace_count;out[7]=96;
}
#endif
static void trace_feedback(unsigned kind,unsigned page,const uint32_t *words,unsigned length)
{
    uint32_t *r=feedback_trace[feedback_trace_count++%96];
    const uint32_t state[]={kind,frame_token,update_state,active_buffer,width,height,
        draw_origin_y,last_frame.y,last_plan.width,last_plan.height,last_plan.display,
        (uint32_t)draw.clip.x,(uint32_t)draw.clip.y,(uint32_t)draw.clip.w,(uint32_t)draw.clip.h,
        (uint32_t)draw.ofs[0],(uint32_t)draw.ofs[1],feedback_ready,page,0,0,0,0,0};
    memcpy(r,state,sizeof(state));
    if(length>5)length=5;
    if(words)memcpy(r+19,words,length*4);
}
unsigned Game3ds_FeedbackTraceRead(unsigned index,uint32_t *out)
{
    unsigned count=feedback_trace_count<96?feedback_trace_count:96;
    if(index<count && out)memcpy(out,feedback_trace[(feedback_trace_count-count+index)%96],sizeof(feedback_trace[0]));
    return count;
}
uint32_t Game3ds_CanPause(void)
{
    return g_GameWork.gameState==GameState_InGame &&
        g_SysWork.sysState==SysState_Gameplay &&
        !(g_SysWork.sysFlags&SysFlag_CutsceneActive) &&
        g_SysWork.cutsceneBorderState==CutsceneBorderState_None;
}
uint32_t Game3ds_LowerHoldTransition(void)
{
    return g_GameWork.gameState==GameState_InGame &&
        (g_SysWork.sysState==SysState_LoadRoom || g_SysWork.sysState==SysState_LoadOverlay);
}
uint32_t Game3ds_LowerOwner(unsigned display,unsigned start)
{
    return lower_owner(g_GameWork.gameState,g_SysWork.sysState,display,start,
        (g_SysWork.sysFlags&SysFlag_CutsceneActive)!=0);
}
uint32_t Game3ds_CanOpenPause(void)
{
    unsigned owner=Game3ds_LowerOwner(game3ds_gpu_display(),0);
    /* A held lower image also covers event callbacks and cutscenes. Those
     * states must receive START for the original skip and interaction code. */
    return Game3ds_CanPause() && owner==LOWER_GAME_DRAW;
}
void Game3ds_WarningInit(void)
{
    /* main() and Boot display the same TIM. Use the same original environment
     * and producer on both sides of that hand-off, rather than stretching
     * main's image through a synthetic interlaced title canvas. */
    Screen_Init(SCREEN_WIDTH,false);
    g_ActiveBufferIdx=GsGetActiveBuff();
}
extern void integration_overlap_begin_update(void);
void Game3ds_BeginUpdate(uint32_t state)
{
    /* Drain the previous OT before changing its destination. State handlers
     * can select the NEXT game state while still producing the current frame. */
    if(state==GameState_InGame && update_state==state) integration_overlap_begin_update();
    else game3ds_gpu_sync();
    feedback_world=0;
    feedback_ready=0;
    background_2d=0;
    /* Retain the last transition's evidence without tracing unrelated later
     * gameplay uploads. A fresh capture re-arms the short observation window. */
    if(feedback_trace_active && frame_token-feedback_trace_active>2)feedback_trace_active=0;
    if(state==GameState_LoadStatusScreen && update_state!=state)game3ds_status_begin();
    update_state=state;
    game3ds_gpu_begin_draw();
}
void Game3ds_FeedbackInvalidate(uint32_t x,uint32_t y,uint32_t w,uint32_t h)
{
#if defined(SH_STAGE11A_LIFETIME)
    lt_feedback_invalidations++;lt_feedback_ready_at_write+=feedback_ready!=0;
#endif
    if(feedback_trace_active) {uint32_t rect[]={x,y,w,h};trace_feedback(3,0,rect,4);}
    /* A native snapshot is valid only while its canonical PSX page is intact.
     * LoadImage/MoveImage/ClearImage must remain observable by later sampling. */
    if(feedback_ready && w && h && x<width && y<feedback_origin_y+height &&
            y+h>feedback_origin_y)feedback_ready=0;
}
static void capture_frame(void);
void Game3ds_FramebufferCapture(void);
void game3ds_gpu_extent(uint32_t *w,uint32_t *h) {*w=offscreen_active?offscreen_width:plan.width;*h=offscreen_active?(unsigned)offscreen_rect.h:plan.height;}
uint32_t game3ds_gpu_display(void) {return plan.display;}
void game3ds_gpu_clip(int *l,int *t,int *r,int *b)
{
    if(offscreen_active) {*l=0;*t=draw.clip.y-offscreen_rect.y;*r=offscreen_width;*b=*t+draw.clip.h;return;}
    *l=draw.clip.x+plan.x;*t=draw.clip.y-draw_origin_y+plan.y;*r=*l+draw.clip.w;*b=*t+draw.clip.h;
    if(draw.clip.x==0 && draw.clip.w==width) {*l=0;*r=plan.width;}
    if(plan.display==1 && height>240) {
        *t=(draw.clip.y-draw_origin_y)/2+plan.y;*b=*t+(draw.clip.h+1)/2;
    }
    if(height>240 && draw.clip.y==draw_origin_y && draw.clip.h*2==height) {*t=0;*b=plan.height;}
    if(!plan.display && plan.width>width && draw.clip.y==draw_origin_y && draw.clip.h==height) {*t=0;*b=plan.height;}
}
void game3ds_gpu_frame_complete(void) {last_plan=plan;last_frame=(RECT16){0,draw_origin_y,width,height};frame_valid=1;frame_captured=0;}
static void frame_plan(void)
{
    int bottom=update_state==GameState_InventoryScreen || update_state==GameState_PaperMapScreen;
    int world=game_display_world(update_state==GameState_InGame || update_state==GameState_MapEvent,
        feedback_world,background_2d,(g_SysWork.sysFlags&SysFlag_CutsceneActive)!=0);
    plan=game_display_plan(width,height,world,bottom);
    render3ds_ambient_enable(height>240 || !world);
    /* The loading handler intentionally draws framebuffer feedback while it
     * prepares Status. Neither LCD should expose that intermediate canvas. */
    if(update_state==GameState_LoadStatusScreen)plan.display=2;
}
void Game3ds_WarningFrame(unsigned fade)
{
    extern s_FsImageDesc g_MainImg0;
    static DR_TPAGE mode;static TILE overlay;
    /* main() is still streaming BODYPROG through FS_BUFFER_0, whose span
     * reaches the ordinary TEMP packet arena. Keep this short pre-loop OT
     * outside those in-flight file buffers. */
    static PACKET warning_packets[3*(sizeof(SPRT)+sizeof(DR_TPAGE))];
    GsOT *ot=&g_OrderingTable0[g_ActiveBufferIdx];
    GsOUT_PACKET_P=warning_packets;
    GsClearOt(0,0,ot);
    Screen_BackgroundImgDraw(&g_MainImg0);GsDrawOt(ot);
    SetDrawTPage(&mode,0,1,getTPage(0,2,0,0));DrawPrim(&mode);
    setTile(&overlay);setSemiTrans(&overlay,1);setRGB0(&overlay,fade,fade,fade);
    setXY0(&overlay,-SCREEN_WIDTH,-SCREEN_HEIGHT);setWH(&overlay,SCREEN_WIDTH*2,SCREEN_HEIGHT*2);DrawPrim(&overlay);
}
static unsigned page, vblank, vcount_start;
uint32_t game3ds_gpu_mask_updates, game3ds_gpu_mask_bits;
uint32_t game3ds_gpu_oversize_triangles;
uint32_t game3ds_gpu_culled_triangles;
static unsigned short buffer_y[2];
static TILE clear_tiles[2];
static void (*game_vsync_callback)(void);
static unsigned char *pad_data;
static unsigned char native_packets[2][GAME_PACKET_BYTES+GAME_PACKET_GUARD_BYTES] __attribute__((aligned(8)));
static unsigned native_packet_buffer,native_packet_active;
void *Game3ds_PacketBegin(unsigned buffer)
{
    if(buffer>1)game3ds_halt(460,"native packet buffer",buffer);
    native_packet_active=1;native_packet_buffer=buffer;
    memset(native_packets[buffer]+GAME_PACKET_BYTES,0xa5,GAME_PACKET_GUARD_BYTES);
    return native_packets[buffer];
}
void Game3ds_PacketBounds(uintptr_t *base,unsigned *capacity)
{
    if(native_packet_active) {*base=(uintptr_t)native_packets[native_packet_buffer];*capacity=GAME_PACKET_BYTES;return;}
    /* Isolated producer fixtures retain the original scratch setup. */
    *capacity=g_GameWork.gameState==GameState_InGame || g_GameWork.gameState==GameState_MainLoadScreen?131072:
        g_GameWork.gameState==GameState_InventoryScreen?40000:32768;
    *base=(uintptr_t)TEMP_MEMORY_ADDR+g_ActiveBufferIdx * *capacity;
}
void Game3ds_PacketCheck(const void *packet,unsigned bytes)
{
    uintptr_t at=(uintptr_t)packet;
    for(unsigned i=0;i<2;i++) {
        uintptr_t base=(uintptr_t)native_packets[i];
        if(at>=base && at<base+sizeof(native_packets[i])) {
            if(i!=native_packet_buffer || at-base>GAME_PACKET_BYTES || bytes>GAME_PACKET_BYTES-(at-base))
                game3ds_halt(460,"native packet emit bounds",at-base+bytes);
            return;
        }
    }
    /* Static global primitives and isolated original scratch producers are
     * valid. Every native-arena emit is checked before linking into an OT.
     * Guard storage contains a rejected packet's writes before this check. */
}
void Game3ds_PacketValidate(void)
{
    if(!native_packet_active)return;
    for(unsigned i=0;i<GAME_PACKET_GUARD_BYTES;i++)
        if(native_packets[native_packet_buffer][GAME_PACKET_BYTES+i]!=0xa5)
            game3ds_halt(460,"native packet guard modified",GAME_PACKET_BYTES+i);
}
static char *hex_field(char *out,uint32_t value,unsigned digits)
{
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<digits;i++)*out++=hex[(value>>((digits-1-i)*4))&15];
    return out;
}
static unsigned sync_vblank_clock(void)
{
    unsigned now=game3ds_vblank_clock(), elapsed=now-vblank;
    /* Bound callback catch-up after APT suspend/debugger stalls. Game delta
     * retains its original cap; never run minutes of callbacks on resume. */
    if (elapsed>8) elapsed=8;
    vblank=now;
    while (elapsed--) if (game_vsync_callback) game_vsync_callback();
    return vblank;
}

static int readable(const void *ptr, size_t bytes)
{
    /* 3dsx.ld places RW data on the page following .ARM.exidx. */
    uintptr_t p = (uintptr_t)ptr, lo = ((uintptr_t)&__exidx_end + 4095) & ~(uintptr_t)4095;
    uintptr_t hi = (uintptr_t)&__bss_end__;
    return p >= lo && p <= hi && bytes <= hi - p;
}
static void vertex(float *v, int x, int y, int u, int texv, unsigned r, unsigned g, unsigned b, unsigned textured)
{
    game_screen_point(v,x+draw.ofs[0]+(offscreen_active?(int)offscreen_margin-offscreen_rect.x:plan.x),y+draw.ofs[1]+(offscreen_active?-offscreen_rect.y:-draw_origin_y+plan.y));v[2]=0;
    if(!offscreen_active && plan.display==1 && height>240)v[1]=(y+draw.ofs[1]-draw_origin_y)*.5f+plan.y+.5f;
    v[3]=game_screen_uv(u);v[4]=1-game_screen_uv(texv);
    float scale = textured ? 128.0f : 255.0f;
    v[5] = r / scale; v[6] = g / scale; v[7] = b / scale; v[8] = 1;
}
static void packet(const P_TAG *p)
{
    unsigned len = getlen(p);
    if (!len) return;
    unsigned code = p->code, kind = code & 0xfc, blend = (code & 2) ? 1 + ((page >> 5) & 3) : 0;
    const uint32_t *words = (const uint32_t*)((const unsigned char*)p + sizeof(OT_TAG));
    if (code >= 0xe1 && code <= 0xe6) {
        unsigned area_changed=0;
        for (unsigned i = 0; i < len; i++) {
            uint32_t command; memcpy(&command, words + i, 4);
            switch (command >> 24) {
                case 0x00:
                    if (command) {
                        static char fault[96];
                        snprintf(fault,sizeof(fault),"GPU NOP @%08lx n%u i%u c0=%08lx next=%08lx",
                            (unsigned long)(uintptr_t)p,len,i,(unsigned long)words[0],(unsigned long)getaddr(p));
                        game3ds_halt(424,fault,command);
                    }
                    break; /* PsyQ _get_tw(NULL) emits the documented GP0 NOP. */
                case 0xe1: page = command & 0x1ff; break;
                case 0xe2:
                    if (command & 0xfffff) game3ds_halt(424, "nonzero texture window", command);
                    break;
                case 0xe6:
                    if (command & 0xfffffc) game3ds_halt(424,"GPU mask reserved bits",command);
                    game3ds_gpu_mask_bits=command&3; game3ds_gpu_mask_updates++;
                    /* Captured per draw by the bounded PICA bridge. */
                    break;
                case 0xe3: draw.clip.x=command&1023;draw.clip.y=(command>>10)&511;area_changed=1;break;
                case 0xe4:
                    draw.clip.w=(int)(command&1023)-draw.clip.x+1;
                    draw.clip.h=(int)((command>>10)&511)-draw.clip.y+1;area_changed=1;break;
                case 0xe5: draw.ofs[0]=game_screen_signed11(command);draw.ofs[1]=game_screen_signed11(command>>11);break;
                default: game3ds_halt(424, "GPU state opcode", command);
            }
        }
        if(area_changed) {
            int is_vram=draw.clip.w>0 && draw.clip.h>0 && draw.clip.x>=0 && draw.clip.y>=0 &&
                draw.clip.x+draw.clip.w<=1024 && draw.clip.y+draw.clip.h<=512 &&
                (draw.clip.x>=width || draw.clip.x+draw.clip.w<=0 ||
                 draw.clip.y>=draw_origin_y+(int)height || draw.clip.y+draw.clip.h<=draw_origin_y);
            if(offscreen_active && (!is_vram || memcmp(&offscreen_rect,&draw.clip,sizeof(offscreen_rect)))) {
                game3ds_vram_target_end();completed_target=offscreen_rect;
                completed_target_frame=frame_token;completed_target_valid=1;offscreen_active=0;
            }
            if(is_vram && !offscreen_active) {
                offscreen_rect=draw.clip;
                offscreen_width=(offscreen_rect.w==(int)width && offscreen_rect.h==(int)height && plan.width>width && height<=240)?plan.width:(unsigned)offscreen_rect.w;
                offscreen_margin=(offscreen_width-offscreen_rect.w)/2;
                game3ds_vram_target_begin(offscreen_rect.x,offscreen_rect.y,offscreen_rect.w,offscreen_rect.h,offscreen_width);offscreen_active=1;
            }
        }
        return;
    }
    if(code==1 && len==5 && words[1]==0x80000000) {
        RECT16 source;memcpy(&source.x,&words[2],4);memcpy(&source.w,&words[4],4);
        MoveImage(&source,words[3]&65535,words[3]>>16);return;
    }
    if(kind==0x48 || kind==0x4c) {
        unsigned points=kind==0x48?3:4;
        if((code&2) || len!=points+2 || (words[len-1]&0xf000f000)!=0x50005000)
            game3ds_halt(425,"opaque polyline contract",code);
        /* Original MAP2 note/map outlines use connected flat opaque lines.
         * Reuse the bounded line raster path; shared endpoints have the same
         * opaque color, so emitting them twice cannot change the result. */
        for(unsigned i=0;i+1<points;i++) {
            LINE_F2 line;setLineF2(&line);
            memcpy(&line.r0,&words[0],4);line.code=0x40;
            memcpy(&line.x0,&words[1+i],4);memcpy(&line.x1,&words[2+i],4);
            packet((P_TAG*)&line);
        }
        return;
    }
    float q[4][9], tri[6][9]; unsigned textured = 0, clut = 0, count = 6, feedback_draw=0;
    int polygon_xy[4][2];unsigned polygon=0;
    if (kind == 0x64 || kind == 0x74 || kind == 0x7c || kind == 0x60) {
        int x, y, w, h, u = 0, v = 0;
        if (kind == 0x64 || kind == 0x74 || kind == 0x7c) {
            const SPRT *s = (const SPRT*)p;
            if (len != (kind == 0x64 ? 4u : 3u)) game3ds_halt(425, "SPRT length", len);
            textured = 1; clut = s->clut; x=game_screen_signed11(s->x0);y=game_screen_signed11(s->y0);u=s->u0;v=s->v0;
            w = kind == 0x64 ? s->w : kind == 0x74 ? 8 : 16;
            h = kind == 0x64 ? s->h : w;
        } else {
            const TILE *t = (const TILE*)p;
            if (len != 3) game3ds_halt(425, "TILE length", len);
            x=game_screen_signed11(t->x0);y=game_screen_signed11(t->y0);w=t->w;h=t->h;
        }
        vertex(q[0], x, y, u, v, p->pad0, p->pad1, p->pad2, textured);
        vertex(q[1], x+w, y, u+w, v, p->pad0, p->pad1, p->pad2, textured);
        vertex(q[2], x, y+h, u, v+h, p->pad0, p->pad1, p->pad2, textured);
        vertex(q[3], x+w, y+h, u+w, v+h, p->pad0, p->pad1, p->pad2, textured);
        /* A framebuffer texture represents the WHOLE native view, resolved to
         * the reserved PSX display page. Expand only feedback, never authored
         * 2D artwork. Capture and replay use inverse coordinate transforms. */
        unsigned tx=(page&15)*64+u,ty=(page&16)*16+v;
        int target_sprite=!offscreen_active && textured && ((page>>7)&3)==2 &&
            completed_target_valid && completed_target_frame==frame_token &&
            game_feedback_target_sprite(tx,ty,w,h,completed_target.x,completed_target.y,completed_target.w,completed_target.h);
        if(feedback_trace_active && textured && ((page>>7)&3)==2 && tx<width)
            trace_feedback(2,page,words,len);
        int feedback=!offscreen_active && textured && ((page>>7)&3)==2 && frame_valid &&
            last_plan.width>last_frame.w && tx<(unsigned)last_frame.w &&
            ((ty>=buffer_y[0] && ty<buffer_y[0]+height) ||
             (ty>=buffer_y[1] && ty<buffer_y[1]+height));
        if(!offscreen_active && feedback_ready && textured && ((page>>7)&3)==2 && tx<width &&
                ty>=feedback_origin_y && ty+h<=feedback_origin_y+height) {
            for(unsigned i=0;i<4;i++)game_feedback_vertex(q[i],page,last_plan.width,last_plan.height,
                width,height,plan.x,plan.y,feedback_origin_y);
            feedback_draw=GAME_FEEDBACK_PAGE;feedback=1;
        } else if(target_sprite && plan.width>width) {
            unsigned margin=(plan.width-width)/2;
            int left=tx==(unsigned)completed_target.x?-(int)margin:0;
            int right=tx+w==(unsigned)(completed_target.x+completed_target.w)?(int)margin:0;
            for(unsigned i=0;i<4;i++)game_feedback_target_vertex(q[i],page,completed_target.x,completed_target.y,margin,(i&1)?right:left);
            feedback_draw=GAME_FEEDBACK_PAGE;
            feedback=1;
        } else if(feedback && plan.width>width)for(unsigned i=0;i<4;i++) {
            q[i][0]=(q[i][0]-plan.x-.5f)*plan.width/width+.5f;
            q[i][1]=(q[i][1]-plan.y-.5f)*plan.height/height+.5f;
        }
        /* Sprite artwork keeps its original canvas; crop UVs with its edges. */
        float left=(float)plan.x+0.5f,right=left+width;
        if(!offscreen_active && textured && !feedback && plan.width>width)for(unsigned i=0;i<4;i++) {
            float old=q[i][0],clipped=old<left?left:old>right?right:old;
            q[i][3]+=(clipped-old)/256.0f;q[i][0]=clipped;
        }
        if(!offscreen_active && !textured && x<=-(int)width/2 && w>=(int)width) {
            q[0][0]=q[2][0]=0;q[1][0]=q[3][0]=plan.width;
            if(y<=-(int)height/2 && h>=(int)height) {
                q[0][1]=q[1][1]=0;q[2][1]=q[3][1]=plan.height;
            }
        } else if(!offscreen_active && !textured && (code&2) && plan.width>width) {
            /* Some full-screen feedback effects submit two abutting TILEs.
             * Extend their outer edges just like the single-TILE case, while
             * leaving the shared edge, blend modes and effect pixels intact. */
            unsigned edges=game_screen_overlay_edges(x,y,w,h,width,height);
            if(edges&1)q[0][0]=q[2][0]=0;
            if(edges&2)q[1][0]=q[3][0]=plan.width;
            if(edges) {q[0][1]=q[1][1]=0;q[2][1]=q[3][1]=plan.height;}
        }
    } else if(kind==0x40 || kind==0x50) {
        unsigned gouraud=kind==0x50;
        if(len!=(gouraud?4u:3u))game3ds_halt(425,"line length",len);
        uint32_t xy0=words[1],xy1=words[gouraud?3:2],color0=words[0],color1=words[gouraud?2:0];
        int x0=game_screen_signed11(xy0),y0=game_screen_signed11(xy0>>16);
        int x1=game_screen_signed11(xy1),y1=game_screen_signed11(xy1>>16);
        /* Original inventory/save borders are axis-aligned one-pixel lines.
         * Include both PSX endpoints, retaining endpoint Gouraud colors. */
        if(x0!=x1 && y0!=y1) {
            /* Integer PSX line samples, including endpoints. Runs are bounded
             * by signed-11-bit coordinates and normal submission budgets. */
            int dx=ABS(x1-x0),dy=ABS(y1-y0),sx=x0<x1?1:-1,sy=y0<y1?1:-1;
            int error=dx-dy,steps=MAX(dx,dy),step=0;
            for(;;) {
                unsigned rgb[3];
                for(unsigned c=0;c<3;c++) {
                    int a=(color0>>(c*8))&255,b=(color1>>(c*8))&255;
                    rgb[c]=a+(b-a)*step/steps;
                }
                float pixels[6][9];static const unsigned order[6]={0,1,2,1,3,2};
                for(unsigned i=0;i<6;i++) {
                    unsigned corner=order[i];vertex(pixels[i],x0+(corner&1),y0+(corner>>1),0,0,rgb[0],rgb[1],rgb[2],0);
                    pixels[i][0]-=.5f;pixels[i][1]-=.5f;
                }
                game3ds_gpu_rect(&pixels[0][0],6,0,0,0,blend);
                if(x0==x1 && y0==y1)break;
                int twice=2*error;
                if(twice>-dy){error-=dy;x0+=sx;}
                if(twice<dx){error+=dx;y0+=sy;}
                step++;
            }
            return;
        }
        int horizontal=y0==y1;
        if((horizontal && x1<x0) || (!horizontal && y1<y0)) {
            int tmp=x0;x0=x1;x1=tmp;tmp=y0;y0=y1;y1=tmp;
            uint32_t c=color0;color0=color1;color1=c;
        }
        int xs[4]={x0,x1+(horizontal?1:0),x0+(horizontal?0:1),x1+1};
        int ys[4]={y0,y1,y0+1,y1+1};
        if(!horizontal){xs[1]=x0;ys[1]=y1+1;xs[2]=x0+1;ys[2]=y0;}
        for(unsigned i=0;i<4;i++) {
            uint32_t color=(i==1 || i==3)?color1:color0;
            vertex(q[i],xs[i],ys[i],0,0,color&255,(color>>8)&255,(color>>16)&255,0);
            q[i][0]-=0.5f;q[i][1]-=0.5f;
        }
    } else if ((code & 0xe0) == 0x20) {
        polygon=1;
        /* Retail mesh generation emits the GP0 polygon family: flat/Gouraud,
         * textured/untextured, three/four vertices. OT order is unchanged. */
        unsigned points=(code&8)?4:3, gouraud=(code&16)!=0;
        textured=(code&4)!=0;
        unsigned expected=1+points*(1+textured)+(gouraud?points-1:0);
        if (len!=expected) game3ds_halt(425,"polygon length",(code<<16)|len);
        unsigned cursor=1, color=words[0];
        for (unsigned i=0;i<points;i++) {
            if (i && gouraud) color=words[cursor++];
            uint32_t xy=words[cursor++], uv=0;
            if (textured) {
                uv=words[cursor++];
                if (!i) clut=uv>>16;
                if (i==1) page=(uv>>16)&0x1ff;
            }
            unsigned rgb=textured && (code&1) ? 0x808080 : color;
            polygon_xy[i][0]=game_screen_signed11(xy);polygon_xy[i][1]=game_screen_signed11(xy>>16);
            vertex(q[i],polygon_xy[i][0],polygon_xy[i][1],uv&255,(uv>>8)&255,
                   rgb&255,(rgb>>8)&255,(rgb>>16)&255,textured);
        }
        blend=(code&2)?1+((page>>5)&3):0;
        /* Status folds a 16-source-row cell to 12 LCD rows. Nearest skips
         * source row 7 (the bright crossbar in several glyphs). A separate
         * filtered texture identity preserves that stroke without changing
         * the original atlas/CLUT, advances, 12-row geometry or other text.
         * Horizontal samples stay at exact texel centres; no atlas neighbour
         * is sampled at the original U/V endpoints. */
        if(update_state==GameState_InventoryScreen && kind==0x2c && clut==0x7fd3 &&
           (page&0x19c)==0x10 && polygon_xy[1][1]-polygon_xy[0][1]==24 &&
           polygon_xy[2][0]-polygon_xy[0][0]==12)
            feedback_draw=GAME_STATUS_FONT_PAGE;
        count=points==3?3:6;
    } else {
        static char diagnostic[160];
        char *out=diagnostic;
        memcpy(out,"GPU opcode ",11);out=hex_field(out+11,code,2);
        memcpy(out," len ",5);out=hex_field(out+5,len,4);
        memcpy(out," @",2);out=hex_field(out+2,(uintptr_t)p,8);
        memcpy(out," words ",7);out=hex_field(out+7,words[0],8);
        *out++=' ';out=hex_field(out,len>1?words[1]:0,8);
        *out++=' ';out=hex_field(out,len>2?words[2]:0,8);*out=0;
        game3ds_halt(426,diagnostic,code);
    }
    const unsigned order[] = {0,1,2,1,3,2};
    int left,top,right,bottom;game3ds_gpu_clip(&left,&top,&right,&bottom);
    unsigned kept=0;
    for (unsigned i=0;i<count;i+=3) {
        unsigned a=order[i],b=order[i+1],c=order[i+2];
        if(polygon && !game_screen_triangle_size_valid(polygon_xy[a][0],polygon_xy[a][1],
                polygon_xy[b][0],polygon_xy[b][1],polygon_xy[c][0],polygon_xy[c][1])) {
            game3ds_gpu_oversize_triangles++;continue;
        }
        /* State commands have already executed, even when their following
         * geometry misses the draw area. Reject before vertex copies, cache
         * pinning and PICA state generation; preserve every intersecting tri. */
        if(draw.clip.w>0 && draw.clip.h>0 && game_screen_triangle_outside(q[a],q[b],q[c],left,top,right,bottom)) {
            game3ds_gpu_culled_triangles++;continue;
        }
        for(unsigned j=0;j<3;j++)memcpy(tri[kept++],q[order[i+j]],sizeof(q[0]));
    }
    if(kept)game3ds_gpu_rect(&tri[0][0], kept, page|feedback_draw, clut, textured, blend);
}
void DrawPrim(void *p)
{
    if (!readable(p, sizeof(OT_TAG)) || !readable(p, sizeof(OT_TAG) + getlen(p)*4u))
        game3ds_halt(427, "DrawPrim extent", (uintptr_t)p);
    packet(p);
}
void DrawOTag(u_long *first)
{
    frame_plan();
    uint64_t profile=game_prof_begin();
    uint64_t start=game3ds_ticks();
    P_TAG *p = (P_TAG*)first;
    for (unsigned hops = 0; hops < 8192; hops++) {
        if ((void*)p == &prim_terminator) {
            game_prof_end(GP_PRIMITIVE,profile);
            game3ds_primitive_ticks(game3ds_ticks()-start); return;
        }
        if (!readable(p, sizeof(OT_TAG))) game3ds_halt(427, "OT pointer", (uintptr_t)p);
        DrawPrim(p);
        p = nextPrim(p);
    }
    game3ds_halt(428, "OT cycle/budget", 8192);
}
u_long *ClearOTagR(u_long *ot, int n)
{
    OT_TAG *tags = (OT_TAG*)ot;
    if (n < 1 || n > 2048 || !readable(tags, n * sizeof(*tags))) game3ds_halt(429, "ClearOTagR bounds", n);
    memset(tags, 0, n * sizeof(*tags));
    termPrim(&tags[0]);
    for (int i = 1; i < n; i++) setaddr(&tags[i], &tags[i-1]);
    return ot;
}
void AddPrim(void *ot, void *p) {Game3ds_PacketCheck(p,sizeof(OT_TAG)+getlen(p)*4);setaddr(p,getaddr(ot));setaddr(ot,p);}
int DrawSync(int mode) { (void)mode; game3ds_gpu_sync(); return 0; }
int VSyncCallback(void (*callback)(void)) { game_vsync_callback = callback; return 0; }
int ResetCallback(void) { int old = (uintptr_t)game_vsync_callback; game_vsync_callback = NULL; return old; }
int VSync(int mode)
{
    if (mode < 0) return sync_vblank_clock();
    sync_vblank_clock();
    game3ds_gpu_sync();
    game3ds_wait_vblank();
    sync_vblank_clock(); Game3ds_Observe(); return vblank;
}
void Game3ds_PadPoll(void)
{
    Game3ds_Observe();
    unsigned keys = game3ds_read_pad();
    int cx=0,cy=0,rx=0,ry=0;
    game3ds_read_analog(&cx,&cy,&rx,&ry);
    Game3ds_InputSample(keys,cx,cy,rx,ry);
    if (pad_data) {
        /* libctru raw bit layout -> PSX digital pad. Logical Joy code is original. */
        uint16_t buttons = game_pad_buttons(keys);
        pad_data[0] = 0; pad_data[1] = 0x41;
        uint16_t inverted = ~buttons; memcpy(pad_data+2, &inverted, 2);
    }
}
void PadInitDirect(unsigned char *p0, unsigned char *p1)
{
    Game3ds_ControlsReset();
    pad_data = p0; memset(p0, 0x80, 8); p0[0] = 0; p0[1] = 0x41; p0[2] = p0[3] = 0xff;
    memset(p1, 0xff, 8);
}
void PadStartCom(void) {}
void GsInitVcount(void) { vcount_start=game3ds_hblank_clock(); }
int GsGetVcount(void) { return (uint32_t)(game3ds_hblank_clock()-vcount_start); }
void GsClearVcount(void) { vcount_start=game3ds_hblank_clock(); }
void GsInitGraph2(unsigned short w, unsigned short h, unsigned short mode, unsigned short dith, unsigned short vrammode)
{
    (void)dith; (void)vrammode; width = w; height = h;
    memset(&GsDRAWENV, 0, sizeof(GsDRAWENV)); memset(&GsDISPENV, 0, sizeof(GsDISPENV));
    GsDRAWENV.clip.w = w; GsDRAWENV.clip.h = h;
    GsDISPENV.disp.w = w; GsDISPENV.disp.h = h;
    GsDISPENV.isinter=(mode&1)!=0;
}
void GsDefDispBuff2(unsigned short x0, unsigned short y0, unsigned short x1, unsigned short y1)
{
    if (x0 || x1) game3ds_halt(430, "GS horizontal buffer origin", x0);
    buffer_y[0] = y0; buffer_y[1] = y1;
}
void GsInit3D(void) { SetGeomOffset(0, 0); SetGeomScreen(width / 2); }
void GsSwapDispBuff(void)
{
    frame_token++;
    active_buffer ^= 1;
    draw = GsDRAWENV; draw.clip.y = buffer_y[active_buffer];
    draw_origin_y=draw.clip.y;
    draw.ofs[0] = width/2; draw.ofs[1] = buffer_y[active_buffer]+height/2;
}
int GsGetActiveBuff(void) { return active_buffer; }
void GsClearOt(int offset, int point, GsOT *ot)
{
    if (!ot || ot->length > 11) game3ds_halt(429, "GsClearOt", ot ? ot->length : 0);
    ot->offset = offset; ot->point = point;
    ClearOTagR((u_long*)ot->org, 1u << ot->length); ot->tag = &ot->org[(1u << ot->length)-1];
}
void GsDrawOt(GsOT *ot) { DrawOTag((u_long*)ot->tag); }
void GsSortClear(unsigned char r, unsigned char g, unsigned char b, GsOT *ot)
{
    TILE *t = &clear_tiles[g_ActiveBufferIdx]; setTile(t); setRGB0(t,r,g,b);
    setXY0(t, -(int)width/2, -(int)height/2); setWH(t,width,height);
    AddPrim(&ot->org[(1u << ot->length)-1], t);
}
DISPENV *PutDispEnv(DISPENV *env) { GsDISPENV = *env; return env; }
DRAWENV *PutDrawEnv(DRAWENV *env) { draw = *env;draw_origin_y=draw.clip.y;width = env->clip.w; height = env->clip.h; return env; }
void SetDispMask(int mask) { (void)mask; }
int ResetGraph(int mode) { (void)mode; return 0; }
void SetDrawMode(DR_MODE *p, int dfe, int dtd, int tpage, RECT16 *tw)
{
    (void)dfe;
    setlen(p,2); p->code[0] = _get_mode(dfe,dtd,tpage); p->code[1] = _get_tw(tw);
}
void SetDrawTPage(DR_TPAGE *p, int dfe, int dtd, int tpage) { setDrawTPage(p,dfe,dtd,tpage); }
void SetPolyG3(POLY_G3 *p) { setPolyG3(p); }
void SetPolyG4(POLY_G4 *p) { setPolyG4(p); }
void SetPolyF4(POLY_F4 *p) { setPolyF4(p); }
void SetPolyFT4(POLY_FT4 *p) { setPolyFT4(p); }
void SetTile(TILE *p) { setTile(p); }
void TermPrim(void *p) { termPrim(p); }
DRAWENV *GetDrawEnv(DRAWENV *out) { *out = draw; return out; }
void SetPriority(PACKET *p, int a, int b)
{
    /* Retail SLUS_007.07 SetPriority 0x800192FC, verified by MIPS execution. */
    DR_STP *state=(DR_STP*)p;
    setlen(state,2); state->code[0]=0xe6000000|((a!=0)<<1)|(b!=0); state->code[1]=0;
}
void SetDrawEnv(DR_ENV *p, DRAWENV *env)
{
    setlen(p,5);
    p->code[0]=0xe3000000 | (env->clip.x&1023) | ((env->clip.y&511)<<10);
    p->code[1]=0xe4000000 | ((env->clip.x+env->clip.w-1)&1023) | (((env->clip.y+env->clip.h-1)&511)<<10);
    p->code[2]=0xe5000000 | (env->ofs[0]&2047) | ((env->ofs[1]&2047)<<11);
    p->code[3]=_get_tw(&env->tw);
    p->code[4]=_get_mode(env->dfe,env->dtd,env->tpage);
    if (env->isbg) game3ds_halt(453,"SetDrawEnv isbg",env->isbg);
}
void SetDrawMove(DR_MOVE *p, RECT16 *r, int x, int y)
{
    setlen(p,(r->w && r->h)?5:0);
    p->code[0]=0x01000000; p->code[1]=0x80000000;
    memcpy(&p->code[2],&r->x,4); p->code[3]=(x&65535)|((uint32_t)y<<16);
    memcpy(&p->code[4],&r->w,4);
}
void SetDrawArea(DR_AREA *p, RECT16 *r)
{
    setlen(p,2); p->code[0] = 0xe3000000 | (r->x & 1023) | ((r->y & 511)<<10);
    p->code[1] = 0xe4000000 | ((r->x+r->w-1)&1023) | (((r->y+r->h-1)&511)<<10);
}
void SetDrawOffset(DR_OFFSET *p, u_short *ofs)
{
    setlen(p,1); p->code[0] = 0xe5000000 | (ofs[0]&2047) | ((ofs[1]&2047)<<11);
}
int ClearImage(RECT16 *r, u_char red, u_char green, u_char blue)
{
    PsxRect rect = {r->x,r->y,r->w,r->h};
    if (!psx_vram_rect_valid(rect)) game3ds_halt(431, "ClearImage bounds", 0);
    game3ds_gpu_sync();
    uint16_t color = (red>>3) | ((green>>3)<<5) | ((blue>>3)<<10);
    for (unsigned y=0; y<rect.h; y++) for(unsigned x=0; x<rect.w; x++)
        game3ds_canonical->words[(rect.y+y)*1024+rect.x+x]=color;
    game3ds_canonical->generation++;
    game3ds_gpu_dirty_rect(rect.x,rect.y,rect.w,rect.h); return 0;
}
int ClearImage2(RECT16 *r, u_char red, u_char green, u_char blue) { return ClearImage(r,red,green,blue); }
/* Exact RGB555 output for 1:1 offscreen texture operations whose result is
 * subsequently reinterpreted as packed texels, not as an RGB image. */
void game3ds_vram_textured_rect(unsigned x,unsigned y,unsigned w,unsigned h,unsigned page,unsigned clut,unsigned u0,unsigned v0,unsigned semi,unsigned dither)
{
    static const int matrix[4][4]={{-4,0,-3,1},{2,-2,3,-1},{-3,1,-4,0},{3,-1,2,-2}};
    unsigned mode=(page>>7)&3,px=(page&15)*64,py=(page&16)*16,cx=(clut&63)*16,cy=(clut>>6)&511,abr=(page>>5)&3;
    if(!w || !h || x>=1024 || y>=512 || w>1024-x || h>512-y || mode>2)game3ds_halt(462,"VRAM raster bounds",0);
    game3ds_gpu_dirty_rect(x,y,w,h);
    for(unsigned j=0;j<h;j++)for(unsigned i=0;i<w;i++) {
        unsigned u=(u0+i)&255,v=(v0+j)&255;
        uint16_t word=game3ds_canonical->words[((py+v)&511)*1024+((px+(u>>(2-mode)))&1023)];
        if(mode<2) {unsigned bits=4u<<mode,index=(word>>((u&((4u>>mode)-1))*bits))&((1u<<bits)-1);word=game3ds_canonical->words[cy*1024+((cx+index)&1023)];}
        if(!word)continue;
        unsigned stp=word&0x8000;uint16_t *dest=&game3ds_canonical->words[(y+j)*1024+x+i];
        unsigned out=stp;
        for(unsigned k=0;k<3;k++) {
            int color=(word>>(k*5))&31;
            if(dither) {int d=(color<<3)+matrix[(y+j)&3][(x+i)&3];if(d<0)d=0;if(d>255)d=255;color=d>>3;}
            if(semi && stp) {int back=(*dest>>(k*5))&31;
                color=abr==0?(back+color)/2:abr==1?back+color:abr==2?back-color:back+(color>>2);
                if(color<0)color=0;if(color>31)color=31;}
            out|=(unsigned)color<<(k*5);
        }
        *dest=(uint16_t)out;
    }
    game3ds_canonical->generation++;
}
static void capture_frame(void)
{
    if(!frame_valid || frame_captured)return;
    game3ds_gpu_sync();
    int wide=last_plan.width>last_frame.w;
    int folded=last_plan.display==1 && last_frame.h>240;
    if(!game3ds_gpu_resolve(wide?0:last_plan.x,wide?0:last_plan.y,
            wide?last_plan.width:(unsigned)last_frame.w,wide?last_plan.height:
                folded?(unsigned)last_frame.h/2:(unsigned)last_frame.h,
            last_frame.w,last_frame.h,
            game3ds_canonical->words+last_frame.y*1024+last_frame.x,1024))
        game3ds_halt(443,"framebuffer resolve",0);
    game3ds_canonical->generation++;
    frame_captured=1;
    game3ds_gpu_dirty_rect(last_frame.x,last_frame.y,last_frame.w,last_frame.h);
}
int StoreImage(RECT16 *r,u_long *out)
{
    if(!r || !out || !psx_vram_rect_valid((PsxRect){r->x,r->y,r->w,r->h}))game3ds_halt(443,"StoreImage bounds",0);
    capture_frame();
    return psx_vram_store(game3ds_canonical,(PsxRect){r->x,r->y,r->w,r->h},out,(unsigned)r->w*r->h*2);
}
/* Both SDK entry points complete through the same native GPU fence. */
int StoreImage2(RECT16 *r,u_long *out) {return StoreImage(r,out);}
void Game3ds_FramebufferCapture(void)
{
    feedback_trace_active=frame_token?frame_token:1;trace_feedback(1,0,NULL,0);
    capture_frame();
    /* A feedback frame inherits the captured display's framing. Loading and
     * death handlers keep replaying the original framebuffer in non-world
     * game states. Classifying those frames as 2D shrank 400 -> 320 on the
     * first replay and destroyed the provenance for all subsequent frames.
     * Only an actual progressive top-screen capture can carry this flag. */
    if(frame_valid && height<=240 && last_frame.h<=240 && last_plan.display==0)
        feedback_world=last_plan.width>(unsigned)last_frame.w;
    if(frame_valid && height<=240 && last_frame.h<=240 && last_plan.display==0 &&
            last_frame.w==(int)width && last_plan.width<=400) {
        game3ds_feedback_capture(last_plan.width,last_plan.height);
    }
    /* Retail feedback reads the currently selected draw page (the older of
     * two PSX buffers). Native rendering has one shared attachment. Seed the
     * requested page from its last completed image before texture sampling. */
    if(frame_valid && height<=240 && last_frame.h<=240 && last_plan.display==0 &&
            last_frame.w==(int)width && last_frame.y!=draw_origin_y) {
        if(psx_vram_move(game3ds_canonical,(PsxRect){last_frame.x,last_frame.y,last_frame.w,last_frame.h},0,draw_origin_y))
            game3ds_halt(443,"feedback page resolve",draw_origin_y);
        game3ds_gpu_dirty_rect(0,draw_origin_y,last_frame.w,last_frame.h);
    }
    if(frame_valid && height<=240 && last_frame.h<=240 && last_plan.display==0 &&
            last_frame.w==(int)width && last_plan.width<=400) {
        feedback_ready=1;feedback_origin_y=draw_origin_y;
    }
    trace_feedback(4,0,NULL,0);
}
int MoveImage(RECT16 *r,int x,int y)
{
    if(!r)game3ds_halt(443,"MoveImage null",0);
    capture_frame();game3ds_gpu_dirty_rect(x,y,r->w,r->h);
    int result=psx_vram_move(game3ds_canonical,(PsxRect){r->x,r->y,r->w,r->h},x,y);
    if(result)game3ds_halt(443,"MoveImage bounds",result);return result;
}
