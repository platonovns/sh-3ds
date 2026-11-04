#include "render_3ds.h"
#include "texture_layout.h"
#include "psx_readback_region.h"
#include "game_profile.h"
#include "psx_batch.h"
#ifdef SH_3DS_GAME
#include "game_texture_decode.h"
#define PROFILE_START(name) uint64_t name=game_prof_begin()
#define PROFILE_END(category,name) game_prof_end(category,name)
#define PROFILE_COUNT(counter,value) game_prof_count(counter,value)
#else
#define PROFILE_START(name)
#define PROFILE_END(category,name) ((void)0)
#define PROFILE_COUNT(counter,value) ((void)0)
#endif

#include <3ds.h>
#include "game_cpu_audit.h"
#include <citro3d.h>
#include <stdlib.h>
#include <string.h>

#include "foundation_shbin.h"

#ifdef SH_3DS_GAME
#include "game_render_budget.h"
#define VERTEX_CAPACITY GAME_VERTEX_LIMIT
#define COMMAND_BUFFER_BYTES GAME_COMMAND_BYTES
#else
#define VERTEX_CAPACITY 256u
#define COMMAND_BUFFER_BYTES (32u * 1024u)
#endif
#define TRANSFER_FLAGS_FOR(format) (GX_TRANSFER_FLIP_VERT(0) | GX_TRANSFER_OUT_TILED(0) | \
    GX_TRANSFER_RAW_COPY(0) | GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8) | \
    GX_TRANSFER_OUT_FORMAT(format) | GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO))
#define TRANSFER_FLAGS TRANSFER_FLAGS_FOR(GX_TRANSFER_FMT_RGB8)

struct Render3dsTexture {
    C3D_Tex gpu;
    struct Render3dsTexture *next;
#ifdef SH_3DS_GAME
    unsigned coverage;
#endif
};
static unsigned texture_coverage(const Render3dsTexture *texture)
{
#ifdef SH_3DS_GAME
    return texture->coverage;
#else
    (void)texture;return 3;
#endif
}
void render3ds_texture_psx_coverage(Render3dsTexture *texture,unsigned classes)
{
#ifdef SH_3DS_GAME
    if(texture)texture->coverage=classes&3;
#else
    (void)texture;(void)classes;
#endif
}

static struct {
    Render3dsStats stats;
    bool active, in_frame, empty_clip;
    C3D_RenderTarget *target;
    C3D_RenderTarget *bottom_target;
    unsigned display;
    DVLB_s *shader;
    shaderProgram_s program;
    C3D_Mtx projection;
    int projection_location;
    Render3dsVertex *vertices;
    Render3dsTexture *textures;
    TickCounter cpu_timer;
    unsigned psx_blend;
    unsigned psx_mask;
    bool pending_draw;
    C3D_Tex native_color;
    C3D_RenderTarget *native_target;
    C3D_Tex ambient_color;
    C3D_RenderTarget *ambient_target;
    C3D_Tex ambient_mask;
    C3D_RenderTarget *ambient_mask_target;
    Render3dsVertex *present_vertices;
    bool native_frame;
    bool continue_native;
    unsigned native_width,native_height;
    /* State belongs to this renderer. Invalidate at each frame/presentation
     * boundary; uploads happen outside a frame and start with a fresh cache. */
    int tev_state, blend_state, alpha_state, stencil_state;
    C3D_Tex *bound_texture;
    bool texture_bound;
    bool scissor_valid;
    int scissor[4];
    uint32_t *readback_color,*readback_mask;
    unsigned readback_generation;
    bool readback_valid;
} renderer;
static C3D_RenderTarget *vram_target;
static C3D_Tex vram_color;
static unsigned vram_width, vram_height;
static bool vram_selected;
static bool ambient_enabled;
void render3ds_ambient_enable(bool enabled) {ambient_enabled=enabled;}
#ifdef SH_3DS_GAME
static char counter_text[40],counter_cached[40];
static unsigned counter_style,counter_cached_style=~0u,counter_count;
static Render3dsVertex *counter_vertices;
void render3ds_counter(const char *text,unsigned style)
{
    if(!text)text="";
    strncpy(counter_text,text,sizeof(counter_text)-1);counter_text[sizeof(counter_text)-1]=0;
    counter_style=style;
}
static unsigned counter_glyph(char c)
{
    static const unsigned glyphs[]={0x7b6f,0x2c97,0x73e7,0x73cf,0x5bc9,0x79cf,0x79ef,0x7249,0x7bef,0x7bcf};
    if(c>='0' && c<='9')return glyphs[c-'0'];
    switch(c) {case 'F':return 0x79e4;case 'P':return 0x7be4;case 'S':return 0x79cf;
        case 'M':return 0x5fed;case '.':return 0x0002;case ':':return 0x0410;default:return 0;}
}
static void counter_build(void)
{
    if(!strcmp(counter_cached,counter_text) && counter_cached_style==counter_style)return;
    if(!counter_vertices)counter_vertices=linearAlloc(2048*sizeof(*counter_vertices));
    counter_count=0;if(!counter_vertices)return;
    strcpy(counter_cached,counter_text);counter_cached_style=counter_style;
    unsigned passes=counter_style==2?2:1;
    for(unsigned pass=0;pass<passes;pass++)for(unsigned i=0;counter_text[i] && i<30;i++) {
        unsigned bits=counter_glyph(counter_text[i]);
        for(unsigned y=0;y<5;y++)for(unsigned x=0;x<3;x++)if(bits&(1u<<(14-y*3-x))) {
            if(counter_count+6>2048)break;
            float px=4+i*8+x*2+(passes==2 && !pass),py=4+y*2+(passes==2 && !pass);
            float col=(counter_style==1 || counter_style==3 || (passes==2 && !pass))?0.f:1.f;
            float a=counter_style==3?0.7f:1.f;
            Render3dsVertex q[6]={{px,py,0,0,0,col,col,col,a},{px+2,py,0,0,0,col,col,col,a},{px,py+2,0,0,0,col,col,col,a},
                {px+2,py,0,0,0,col,col,col,a},{px+2,py+2,0,0,0,col,col,col,a},{px,py+2,0,0,0,col,col,col,a}};
            memcpy(counter_vertices+counter_count,q,sizeof(q));counter_count+=6;
        }
    }
    GSPGPU_FlushDataCache(counter_vertices,counter_count*sizeof(*counter_vertices));
}
#endif
#if defined(SH_STAGE11A_LIFETIME)
#include "stage11a_lifetime.h"
void stage11a_lifetime_renderer(uint32_t out[8])
{
    /* Existing list is traversed ONLY at a sparse snapshot, with a hard cap so
     * corruption cannot turn diagnostics into an unbounded frame-time loop. */
    unsigned n=0;const Render3dsTexture *t=renderer.textures;
    for(;t && n<128;t=t->next)n++;
    out[0]=n;out[1]=t!=NULL;out[2]=renderer.stats.vertices_used;
    out[3]=renderer.in_frame;out[4]=renderer.pending_draw;out[5]=renderer.readback_generation;
    out[6]=renderer.readback_valid;out[7]=(uint32_t)(renderer.stats.command_buffer_usage*1000000.0f);
}
#endif

static void invalidate_draw_state(void)
{
    renderer.tev_state=renderer.blend_state=renderer.alpha_state=renderer.stencil_state=-1;
    renderer.texture_bound=false;
    renderer.scissor_valid=false;
}
static void alpha_test(bool enabled,GPU_TESTFUNC function,unsigned reference)
{
    int key=(enabled?1:0)|((unsigned)function<<1)|(reference<<8);
    if(renderer.alpha_state==key)return;
    C3D_AlphaTest(enabled,function,reference);renderer.alpha_state=key;
}
static void texture_env(unsigned state)
{
    if(renderer.tev_state==(int)state)return;
    C3D_TexEnv *env=C3D_GetTexEnv(0);
    C3D_TexEnvInit(env);
    C3D_TexEnvSrc(env,C3D_Both,state?GPU_TEXTURE0:GPU_PRIMARY_COLOR,GPU_PRIMARY_COLOR,0);
    C3D_TexEnvFunc(env,C3D_Both,state?GPU_MODULATE:GPU_REPLACE);
    if(state==2) {
        C3D_TexEnvSrc(env,C3D_Alpha,GPU_TEXTURE0,0,0);
        C3D_TexEnvFunc(env,C3D_Alpha,GPU_REPLACE);
    } else if(state==3) {
        C3D_TexEnvSrc(env,C3D_Alpha,GPU_TEXTURE0,GPU_TEXTURE0,0);
        C3D_TexEnvOpAlpha(env,GPU_TEVOP_A_SRC_ALPHA,GPU_TEVOP_A_ONE_MINUS_SRC_ALPHA,GPU_TEVOP_A_SRC_ALPHA);
        C3D_TexEnvFunc(env,C3D_Alpha,GPU_MODULATE);
    }
    renderer.tev_state=state;
}

const Render3dsStats *render3ds_stats(void)
{
    return &renderer.stats;
}

static bool native_begin;
static void wait_idle(void)
{
    uint64_t start=svcGetSystemTick();
    /* FrameBegin waits for command lists AND display transfers. No resource may
     * be freed while the asynchronous FrameEnd queue still references it. */
    if (renderer.active && C3D_FrameBegin(0)) {
        if(renderer.pending_draw) {
            renderer.stats.gpu_queue_ms=C3D_GetDrawingTime();renderer.stats.timing_valid=true;
            renderer.pending_draw=false;
        }
        C3D_FrameEnd(GX_CMDLIST_FLUSH);
    }
    renderer.stats.idle_calls++;
    renderer.stats.idle_ticks+=svcGetSystemTick()-start;
#ifdef SH_3DS_GAME
    if(game_prof_enabled)game_prof_add(GP_SYNC,svcGetSystemTick()-start);
#endif
}

void render3ds_wait_idle(void) { wait_idle(); }

void render3ds_shutdown(void)
{
    if (renderer.in_frame)
        render3ds_end_frame();
#ifdef SH_3DS_GAME
    if(counter_vertices) {wait_idle();linearFree(counter_vertices);counter_vertices=NULL;counter_count=0;counter_cached_style=~0u;}
#endif
    if(renderer.native_target) {
        C3D_RenderTargetDelete(renderer.native_target);renderer.native_target=NULL;
        C3D_TexDelete(&renderer.native_color);
    }
    if(renderer.ambient_target) {C3D_RenderTargetDelete(renderer.ambient_target);renderer.ambient_target=NULL;C3D_TexDelete(&renderer.ambient_color);}
    if(renderer.ambient_mask_target) {C3D_RenderTargetDelete(renderer.ambient_mask_target);renderer.ambient_mask_target=NULL;C3D_TexDelete(&renderer.ambient_mask);}
    if(vram_target) {C3D_RenderTargetDelete(vram_target);vram_target=NULL;C3D_TexDelete(&vram_color);}
    vram_selected=false;vram_width=vram_height=0;
    if(renderer.present_vertices) {linearFree(renderer.present_vertices);renderer.present_vertices=NULL;}
    if(renderer.readback_color) {linearFree(renderer.readback_color);renderer.readback_color=NULL;}
    if(renderer.readback_mask) {linearFree(renderer.readback_mask);renderer.readback_mask=NULL;}
    if (renderer.target) {
        /* Deleting the linked target drains the queue before freeing VRAM. */
        C3D_RenderTargetDelete(renderer.target);
        renderer.target = NULL;
    }
    if(renderer.bottom_target) {C3D_RenderTargetDelete(renderer.bottom_target);renderer.bottom_target=NULL;}
    while (renderer.textures)
        render3ds_texture_destroy(renderer.textures);
    if (renderer.vertices) {
        linearFree(renderer.vertices);
        renderer.vertices = NULL;
    }
    shaderProgramFree(&renderer.program);
    memset(&renderer.program, 0, sizeof(renderer.program));
    if (renderer.shader) {
        DVLB_Free(renderer.shader);
        renderer.shader = NULL;
    }
    if (renderer.active) {
        C3D_Fini();
        renderer.active = false;
    }
    renderer.stats.ready = false;
}

bool render3ds_init(void)
{
    if (renderer.active)
        return renderer.stats.ready;
    memset(&renderer, 0, sizeof(renderer));
    renderer.stats.error = "C3D_Init failed";
    if (!C3D_Init(COMMAND_BUFFER_BYTES))
        return false;
    renderer.active = renderer.stats.citro3d_ok = true;
    renderer.stats.command_buffer_bytes = COMMAND_BUFFER_BYTES;
    renderer.stats.error = "Top target allocation failed";
    /* Rotated physical target, 400x240 screen. Draw order needs no depth buffer. */
#ifdef SH_3DS_GAME
    renderer.target = C3D_RenderTargetCreate(240,400,GPU_RB_RGBA8,GPU_RB_DEPTH24_STENCIL8);
#else
    renderer.target = C3D_RenderTargetCreate(240,400,GPU_RB_RGBA8,-1);
#endif
    if (!renderer.target)
        goto fail;
    renderer.stats.target_ok = true;
    renderer.stats.target_bytes = C3D_CalcColorBufSize(240, 400, GPU_RB_RGBA8);
    C3D_RenderTargetClear(renderer.target,C3D_CLEAR_ALL,0x000000FF,0);
    C3D_RenderTargetSetOutput(renderer.target, GFX_TOP, GFX_LEFT, TRANSFER_FLAGS);

    renderer.stats.error = "Shader parse/program failed";
    renderer.shader = DVLB_ParseFile((u32 *)foundation_shbin, foundation_shbin_size);
    if (!renderer.shader || renderer.shader->numDVLE != 1)
        goto fail;
    if (R_FAILED(shaderProgramInit(&renderer.program)) ||
        R_FAILED(shaderProgramSetVsh(&renderer.program, &renderer.shader->DVLE[0])))
        goto fail;
    renderer.projection_location = shaderInstanceGetUniformLocation(
        renderer.program.vertexShader, "projection");
    if (renderer.projection_location < 0)
        goto fail;
    renderer.stats.shader_ok = true;

    renderer.stats.error = "Vertex buffer failed";
    renderer.vertices = linearAlloc(VERTEX_CAPACITY * sizeof(Render3dsVertex));
    if (!renderer.vertices)
        goto fail;
    renderer.stats.buffer_ok = true;
    renderer.stats.vertex_capacity = VERTEX_CAPACITY;
    renderer.stats.vertex_buffer_bytes = VERTEX_CAPACITY * sizeof(Render3dsVertex);

    C3D_AttrInfo *attributes = C3D_GetAttrInfo();
    AttrInfo_Init(attributes);
    AttrInfo_AddLoader(attributes, 0, GPU_FLOAT, 3);
    AttrInfo_AddLoader(attributes, 1, GPU_FLOAT, 2);
    AttrInfo_AddLoader(attributes, 2, GPU_FLOAT, 4);
    C3D_BufInfo *buffers = C3D_GetBufInfo();
    BufInfo_Init(buffers);
    renderer.stats.error = "Vertex buffer binding failed";
    if (BufInfo_Add(buffers, renderer.vertices, sizeof(Render3dsVertex), 3, 0x210) < 0)
        goto fail;
    Mtx_OrthoTilt(&renderer.projection, 0, 400, 240, 0, 1, -1, true);
    C3D_CullFace(GPU_CULL_NONE);
    C3D_DepthTest(false, GPU_ALWAYS, GPU_WRITE_COLOR);
    C3D_AlphaTest(false, GPU_ALWAYS, 0);
    renderer.stats.ready = true;
    renderer.stats.error = "OK";
    return true;
fail:
    render3ds_shutdown();
    return false;
}

bool render3ds_begin_frame(void)
{
    uint64_t start=svcGetSystemTick();
#ifdef SH_3DS_GAME
    /* Original MainLoop owns pacing. Queue completion is still mandatory,
     * but an extra SDK VBlank here would create a second frame-pacing owner. */
    unsigned flags=0;
#else
    unsigned flags=C3D_FRAME_SYNCDRAW;
#endif
    if (!renderer.stats.ready || renderer.in_frame || !C3D_FrameBegin(flags))
        return false;
    renderer.stats.begin_wait_ms=(svcGetSystemTick()-start)/CPU_TICKS_PER_MSEC;
    /* The preceding queue is complete here; timings refer to that queue. */
    if (renderer.pending_draw) {
        renderer.stats.gpu_queue_ms = C3D_GetDrawingTime();
        renderer.stats.timing_valid = true;
        renderer.pending_draw=false;
    }
    osTickCounterStart(&renderer.cpu_timer);
    renderer.in_frame = true;
    invalidate_draw_state();
    renderer.native_frame=false;
    C3D_BufInfo *buffers=C3D_GetBufInfo();BufInfo_Init(buffers);
    BufInfo_Add(buffers,renderer.vertices,sizeof(Render3dsVertex),3,0x210);
    renderer.empty_clip = false;
    renderer.stats.vertices_used = 0;
    renderer.stats.draw_calls = 0;
    C3D_RenderTarget *destination=renderer.display?renderer.bottom_target:renderer.target;
    if(!native_begin) {
    C3D_RenderTargetClear(destination,
#ifdef SH_3DS_GAME
        C3D_CLEAR_ALL,
#else
        C3D_CLEAR_COLOR,
#endif
        0x000000FF,0);
    C3D_FrameDrawOn(destination);
    }
    C3D_BindProgram(&renderer.program);
    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER, renderer.projection_location, &renderer.projection);
    C3D_SetScissor(GPU_SCISSOR_DISABLE, 0, 0, 0, 0);
    return true;
}

uint32_t render3ds_psx_surface_bytes(void) {return renderer.native_target?renderer.native_color.size:0;}
void render3ds_console_bottom(void)
{
    wait_idle();
    if(renderer.bottom_target)C3D_RenderTargetDetachOutput(renderer.bottom_target);
}
bool render3ds_set_display(unsigned display)
{
    if(renderer.in_frame || display>1)return false;
    if(display && !renderer.bottom_target) {
        /* Physical bottom target is in VRAM; shared native surface and vertex
         * buffers are reused. Top's physical color target retains the world. */
        renderer.bottom_target=C3D_RenderTargetCreate(240,320,GPU_RB_RGBA8,-1);
        if(!renderer.bottom_target)return false;
        C3D_RenderTargetClear(renderer.bottom_target,C3D_CLEAR_COLOR,0x000000FF,0);
        /* consoleInit owns RGB565 bottom LCD buffers. Match the actual output
         * format rather than transferring 3-byte RGB8 into a 2-byte buffer. */
        renderer.stats.target_bytes+=C3D_CalcColorBufSize(240,320,GPU_RB_RGBA8);
    }
    if(display) {
        unsigned format=gfxGetScreenFormat(GFX_BOTTOM)==GSP_RGB565_OES?GX_TRANSFER_FMT_RGB565:GX_TRANSFER_FMT_RGB8;
        C3D_RenderTargetSetOutput(renderer.bottom_target,GFX_BOTTOM,GFX_LEFT,TRANSFER_FLAGS_FOR(format));
    }
    renderer.display=display;
    return true;
}
void render3ds_continue_psx_frame(bool preserve) {renderer.continue_native=preserve;}
bool render3ds_read_psx(unsigned x,unsigned y,unsigned width,unsigned height,uint16_t *out,unsigned stride)
{return render3ds_resolve_psx(x,y,width,height,width,height,out,stride);}
static bool readback_surface(void)
{
    unsigned bytes=renderer.native_color.size;
    if(renderer.stats.readback_bytes!=bytes*2) {
        if(renderer.readback_color)linearFree(renderer.readback_color);
        if(renderer.readback_mask)linearFree(renderer.readback_mask);
        renderer.readback_color=linearAlloc(bytes);renderer.readback_mask=linearAlloc(bytes);
        renderer.stats.readback_bytes=bytes*2;renderer.readback_valid=false;
    }
    if(!renderer.readback_color || !renderer.readback_mask)return false;
    if(renderer.readback_valid && renderer.readback_generation==renderer.stats.frames)return true;
    /* Read the render attachment through the GPU transfer engine. CPU reads
     * now use an explicitly invalidated linear allocation, with a documented
     * row pitch, rather than assuming byte-readable/coherent tiled VRAM.
     * This is the pre-presentation attachment, never the rotated LCD buffer. */
    GSPGPU_FlushDataCache(renderer.readback_color,bytes);
    unsigned dimensions=GX_BUFFER_DIM(renderer.native_color.width,512);
    C3D_SyncDisplayTransfer(renderer.native_color.data,dimensions,renderer.readback_color,dimensions,
        GX_TRANSFER_FLIP_VERT(0)|GX_TRANSFER_OUT_TILED(0)|GX_TRANSFER_RAW_COPY(0)|
        GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8)|GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGBA8)|
        GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO));
    if(R_FAILED(GSPGPU_InvalidateDataCache(renderer.readback_color,bytes)))return false;
    GSPGPU_FlushDataCache(renderer.readback_mask,bytes);
    C3D_SyncTextureCopy(renderer.native_target->frameBuf.depthBuf,0,renderer.readback_mask,0,bytes,8);
    if(R_FAILED(GSPGPU_InvalidateDataCache(renderer.readback_mask,bytes)))return false;
    /* Bounded evidence from the real capture path. A device-specific VRAM
     * read discrepancy is reported, instead of inferred from emulator probes. */
    for(unsigned i=0;i<32;i++) {
        unsigned x=(i*137)%renderer.native_width,y=(i*83)%renderer.native_height;
        size_t offset=texture3ds_offset(renderer.native_color.width,512,x,511-y);
        uint32_t direct;memcpy(&direct,(uint8_t*)renderer.native_color.data+offset,4);
        if(direct!=renderer.readback_color[(511-y)*renderer.native_color.width+x])
            renderer.stats.readback_direct_mismatches++;
    }
    renderer.readback_generation=renderer.stats.frames;renderer.readback_valid=true;
    renderer.stats.readback_copies++;return true;
}
bool render3ds_resolve_psx(unsigned x,unsigned y,unsigned width,unsigned height,unsigned out_width,unsigned out_height,uint16_t *out,unsigned stride)
{
    PsxResolveRegion r={x,y,width,height,out_width,out_height,0,0,out_width,out_height};
    if(!renderer.native_target || !out || renderer.in_frame || x>renderer.native_width || y>renderer.native_height ||
        !width || !height || !out_width || !out_height || out_width>1024 || out_height>512 ||
        width>renderer.native_width-x || height>renderer.native_height-y || stride<out_width)return false;
    wait_idle();
    if(!readback_surface())return false;
    /* Optional CPU audit; standalone renderer probes do not link its driver.
     * Resolve stays on main, after the original GPU/readback barrier. */
    extern uint64_t game_cpu_audit_begin(unsigned thread) __attribute__((weak));
    extern void game_cpu_audit_end(unsigned scope,uint64_t start) __attribute__((weak));
    uint64_t audit=game_cpu_audit_begin?game_cpu_audit_begin(GCPU_MAIN):0;
    psx_resolve_region(renderer.readback_color,renderer.readback_mask,renderer.native_color.width,&r,out,stride);
    if(game_cpu_audit_end)game_cpu_audit_end(GCPU_RESOLVE,audit);
    return true;
}
bool render3ds_begin_psx_frame(unsigned width,unsigned height)
{
    if(!width || !height || width>1024 || height>512 || renderer.in_frame)return false;
    bool preserve=renderer.continue_native && renderer.native_target && renderer.native_width==width && renderer.native_height==height;
    renderer.continue_native=false;
    unsigned physical_width=width>512?1024:512;
    if(renderer.native_target && renderer.native_color.width!=physical_width) {
        C3D_RenderTargetDelete(renderer.native_target);renderer.native_target=NULL;C3D_TexDelete(&renderer.native_color);
    }
    if(!renderer.native_target) {
        if(!C3D_TexInitVRAM(&renderer.native_color,physical_width,512,GPU_RGBA8))return false;
        C3D_TexSetFilter(&renderer.native_color,GPU_NEAREST,GPU_NEAREST);
        C3D_TexSetWrap(&renderer.native_color,GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE);
        renderer.native_target=C3D_RenderTargetCreateFromTex(&renderer.native_color,GPU_TEXFACE_2D,0,GPU_RB_DEPTH24_STENCIL8);
        if(!renderer.native_target){C3D_TexDelete(&renderer.native_color);return false;}
        if(!renderer.present_vertices)renderer.present_vertices=linearAlloc(270*sizeof(Render3dsVertex));
        if(!renderer.present_vertices){C3D_RenderTargetDelete(renderer.native_target);renderer.native_target=NULL;C3D_TexDelete(&renderer.native_color);return false;}
    }
    if(!renderer.ambient_target && C3D_TexInitVRAM(&renderer.ambient_color,8,8,GPU_RGBA8)) {
        C3D_TexSetFilter(&renderer.ambient_color,GPU_LINEAR,GPU_LINEAR);
        C3D_TexSetWrap(&renderer.ambient_color,GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE);
        renderer.ambient_target=C3D_RenderTargetCreateFromTex(&renderer.ambient_color,GPU_TEXFACE_2D,0,GPU_RB_DEPTH24_STENCIL8);
        if(!renderer.ambient_target)C3D_TexDelete(&renderer.ambient_color);
    }
    if(!renderer.ambient_mask_target && C3D_TexInitVRAM(&renderer.ambient_mask,8,256,GPU_RGBA8)) {
        C3D_TexSetFilter(&renderer.ambient_mask,GPU_NEAREST,GPU_NEAREST);
        C3D_TexSetWrap(&renderer.ambient_mask,GPU_CLAMP_TO_EDGE,GPU_CLAMP_TO_EDGE);
        renderer.ambient_mask_target=C3D_RenderTargetCreateFromTex(&renderer.ambient_mask,GPU_TEXFACE_2D,0,GPU_RB_DEPTH24_STENCIL8);
        if(!renderer.ambient_mask_target)C3D_TexDelete(&renderer.ambient_mask);
    }
    native_begin=true;
    bool begun=render3ds_begin_frame();native_begin=false;
    if(!begun)return false;
    renderer.native_frame=true;renderer.native_width=width;renderer.native_height=height;
    if(!preserve)C3D_RenderTargetClear(renderer.native_target,C3D_CLEAR_ALL,0x000000FF,0);
    C3D_FrameDrawOn(renderer.native_target);
    /* Native +Y follows the texture's physical +Y. Defer the display Y flip
     * to presentation, so PICA's inclusive lower edge is PSX's inclusive top. */
    C3D_Mtx projection;Mtx_Ortho(&projection,0,physical_width,0,512,1,-1,true);
    C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,renderer.projection_location,&projection);
    return render3ds_set_scissor(0,0,width,height);
}
bool render3ds_set_scissor(int left, int top, int right, int bottom)
{
    if (!renderer.in_frame)
        return false;
    if (left < 0) left = 0;
    if (top < 0) top = 0;
    int max_x=renderer.native_frame?renderer.native_color.width:400,max_y=renderer.native_frame?512:240;
    if (right > max_x) right = max_x;
    if (bottom > max_y) bottom = max_y;
    renderer.empty_clip = left >= right || top >= bottom;
    if (!renderer.empty_clip) {
        if(renderer.scissor_valid && renderer.scissor[0]==left && renderer.scissor[1]==top &&
           renderer.scissor[2]==right && renderer.scissor[3]==bottom)return true;
        /* OrthoTilt rotates logical (x,y) to physical (240-y,400-x). */
        if(renderer.native_frame)C3D_SetScissor(GPU_SCISSOR_NORMAL,left,top,right,bottom);
        else C3D_SetScissor(GPU_SCISSOR_NORMAL, 240 - bottom, 400 - right,
                           240 - top, 400 - left);
        renderer.scissor_valid=true;
        renderer.scissor[0]=left;renderer.scissor[1]=top;
        renderer.scissor[2]=right;renderer.scissor[3]=bottom;
    }
    return true;
}

/* Independent render-to-VRAM attachment. Switching is only allowed between
 * completed submissions, so neither attachment is sampled while in flight. */
bool render3ds_select_vram_surface(bool select)
{
    if(renderer.in_frame)return false;
    if(select==vram_selected)return true;
    wait_idle();
    C3D_RenderTarget *target=renderer.native_target;
    C3D_Tex color=renderer.native_color;
    unsigned width=renderer.native_width,height=renderer.native_height;
    renderer.native_target=vram_target;renderer.native_color=vram_color;
    renderer.native_width=vram_width;renderer.native_height=vram_height;
    vram_target=target;vram_color=color;vram_width=width;vram_height=height;
    renderer.readback_valid=false;
    renderer.continue_native=false;
    vram_selected=select;
    return true;
}

static void psx_blend(unsigned mode)
{
    if(renderer.blend_state==(int)mode)return;
    C3D_BlendingColor(mode==4?0x40404040:0x80808080);
    C3D_AlphaBlend(mode==3?GPU_BLEND_REVERSE_SUBTRACT:GPU_BLEND_ADD,GPU_BLEND_ADD,
        (mode==1 || mode==4)?GPU_CONSTANT_ALPHA:GPU_ONE,
        mode==0?GPU_ZERO:mode==1?GPU_ONE_MINUS_CONSTANT_ALPHA:GPU_ONE,
        GPU_ONE,GPU_ZERO);
    renderer.blend_state=mode;
}
static void draw_arrays(unsigned first,unsigned count)
{
    PROFILE_COUNT(GC_DRAWS,1);
    C3D_DrawArrays(GPU_TRIANGLES,first,count); renderer.stats.draw_calls++;
}
void render3ds_set_psx_mask(unsigned bits) { renderer.psx_mask=bits&3; }
static void psx_mask(bool texel_stp)
{
    bool write_one=(renderer.psx_mask&1)!=0 || texel_stp;
    int key=((renderer.psx_mask&2)?2:0)|write_one;
    if(renderer.stencil_state==key)return;
    if(renderer.psx_mask&2) {
        /* Compare old mask with zero. On success INVERT maps 0->1 without
         * needing different comparison and replacement reference values. */
        C3D_StencilTest(true,GPU_EQUAL,0,1,1);
        C3D_StencilOp(GPU_STENCIL_KEEP,GPU_STENCIL_KEEP,
                      write_one?GPU_STENCIL_INVERT:GPU_STENCIL_ZERO);
    } else {
        C3D_StencilTest(true,GPU_ALWAYS,write_one?1:0,1,1);
        C3D_StencilOp(GPU_STENCIL_KEEP,GPU_STENCIL_KEEP,GPU_STENCIL_REPLACE);
    }
    renderer.stencil_state=key;
}
bool render3ds_draw_triangles(const Render3dsVertex *vertices, size_t count,
                             Render3dsTexture *texture, bool alpha_blend)
{
    u32 command_words, command_used;
    GPUCMD_GetBuffer(NULL, &command_words, &command_used);
    if (!renderer.in_frame || !vertices || !count || count % 3 ||
        count > VERTEX_CAPACITY - renderer.stats.vertices_used ||
        command_used > command_words || command_words - command_used < 1024) {
        ++renderer.stats.rejected_draws;
        return false;
    }
    if (renderer.empty_clip)
        return true;
    const unsigned first = renderer.stats.vertices_used;
    memcpy(renderer.vertices + first, vertices, count * sizeof(*vertices));
    renderer.stats.vertices_used += count;
    texture_env(texture?(renderer.psx_blend?2:1):0);
    if (texture) {
        if(!renderer.texture_bound || renderer.bound_texture!=&texture->gpu) {
            C3D_TexBind(0, &texture->gpu);
            renderer.bound_texture=&texture->gpu;renderer.texture_bound=true;
        }
    }
    if(!renderer.psx_blend) {
        alpha_test(false,GPU_ALWAYS,0);
        C3D_StencilTest(false,GPU_ALWAYS,0,255,255);renderer.stencil_state=-1;
        C3D_AlphaBlend(GPU_BLEND_ADD, GPU_BLEND_ADD,
                  alpha_blend ? GPU_SRC_ALPHA : GPU_ONE,
                  alpha_blend ? GPU_ONE_MINUS_SRC_ALPHA : GPU_ZERO,
                  GPU_ONE, alpha_blend ? GPU_ONE_MINUS_SRC_ALPHA : GPU_ZERO);
        renderer.blend_state=-1;
    }
    if (renderer.psx_blend) {
        unsigned mode = renderer.psx_blend - 1;
        unsigned classes=texture?texture_coverage(texture):3;
        if(texture && classes!=3) {
            if(classes) {
                alpha_test(true,GPU_GREATER,0);
                psx_blend(classes==1?0:mode);psx_mask(classes==2);draw_arrays(first,count);
            }
        } else if(texture && (mode || !(renderer.psx_mask&1))) {
            /* ABE does not apply ABR to non-STP texels. These two disjoint
             * coverage passes stay inside this primitive's painter order and
             * reuse the same vertices/allocation. No object-specific masks. */
            alpha_test(true,GPU_GREATER,192); psx_blend(0); psx_mask(false); draw_arrays(first,count);
            /* Select STP with a*(1-a): both coverage endpoints stay exactly
             * zero, while the middle class remains nonzero after quantization.
             * Equality against one intermediate alpha byte is fragile on GPU. */
            texture_env(3);
            alpha_test(true,GPU_GREATER,0); psx_blend(mode); psx_mask(true); draw_arrays(first,count);
        } else {
            alpha_test(texture!=NULL,GPU_GREATER,0);
            psx_blend(mode); psx_mask(false); draw_arrays(first,count);
        }
    } else draw_arrays(first,count);
    return true;
}

bool render3ds_draw_psx_triangles(const Render3dsVertex *vertices, size_t count,
                                 Render3dsTexture *texture, unsigned blend)
{
    if (blend > 4) return false;
    renderer.psx_blend = blend + 1;
    bool ok = render3ds_draw_triangles(vertices, count, texture, false);
    renderer.psx_blend = 0;
    return ok;
}

bool render3ds_draw_psx_ordered(const Render3dsVertex *vertices,size_t count,
    const uint16_t *sizes,unsigned primitives,Render3dsTexture *texture,unsigned blend)
{
    if(!vertices || !sizes || !primitives)return false;
    size_t verified=0;
    for(unsigned i=0;i<primitives;i++) {
        if(sizes[i]!=3 && sizes[i]!=6)return false;
        verified+=sizes[i];
    }
    if(verified!=count)return false;
    bool split=texture && texture_coverage(texture)==3 && (blend || !(renderer.psx_mask&1));
    if(!split)return render3ds_draw_psx_triangles(vertices,count,texture,blend);
    unsigned offset=0,first=0,group=0;PsxBatchBounds bounds={0};
    for(unsigned i=0;i<primitives;i++) {
        unsigned n=sizes[i];const Render3dsVertex *v=vertices+offset;
        if(n==6 && psx_triangles_overlap(v,v+3)) {
            if(group && !render3ds_draw_psx_triangles(vertices+first,group,texture,blend))return false;
            if(!render3ds_draw_psx_triangles(v,3,texture,blend) ||
               !render3ds_draw_psx_triangles(v+3,3,texture,blend))return false;
            offset+=6;first=offset;group=0;continue;
        }
        PsxBatchBounds next=psx_batch_bounds(v,n);
        if(group && !psx_batch_disjoint(bounds,next)) {
            if(!render3ds_draw_psx_triangles(vertices+first,group,texture,blend))return false;
            first=offset;group=0;
        }
        bounds=group?psx_batch_union(bounds,next):next;
        group+=n;offset+=n;
    }
    return !group || render3ds_draw_psx_triangles(vertices+first,group,texture,blend);
}

static void finish_frame(bool present)
{
    if (!renderer.in_frame)
        return;
    /* CPU writes only; GPU never writes this buffer, so invalidation would
     * discard our data. Command-list flushing is delegated to libctru. */
    GSPGPU_FlushDataCache(renderer.vertices,
                         renderer.stats.vertices_used * sizeof(Render3dsVertex));
    if(renderer.native_frame)renderer.stats.native_parts++;
    if(renderer.native_frame && present) {
        /* Separate ordered command lists flush the render attachment before it
         * is sampled. GPU-produced VRAM is never flushed from the CPU cache. */
        C3D_FrameSplit(GX_CMDLIST_FLUSH);
        float u=(float)renderer.native_width/renderer.native_color.width,v=renderer.native_height/512.0f;
        unsigned present_width=renderer.native_height>240?320:renderer.native_width;
        float left=((renderer.display?320:400)-(int)present_width)/2.0f;
        float right=left+present_width;
        bool glow=ambient_enabled && !renderer.display && present_width==320 && left==40 && renderer.ambient_target;
        const Render3dsVertex quad[6]={
            {left,0,0,0,0,1,1,1,1},{right,0,0,u,0,1,1,1,1},{left,240,0,0,v,1,1,1,1},
            {right,0,0,u,0,1,1,1,1},{right,240,0,u,v,1,1,1,1},{left,240,0,0,v,1,1,1,1}};
        memcpy(renderer.present_vertices,quad,sizeof(quad));
        C3D_TexEnv *env=C3D_GetTexEnv(0);
        C3D_BufInfo *buffers=C3D_GetBufInfo();BufInfo_Init(buffers);
        BufInfo_Add(buffers,renderer.present_vertices,sizeof(Render3dsVertex),3,0x210);
        C3D_SetScissor(GPU_SCISSOR_DISABLE,0,0,0,0);
        C3D_StencilTest(false,GPU_ALWAYS,0,255,255);
        C3D_AlphaTest(false,GPU_ALWAYS,0);
        C3D_DepthTest(false,GPU_ALWAYS,GPU_WRITE_COLOR);
        if(glow) {
            /* Reduce both edge regions to just eight colours per side in an
             * 8x8 target. Constant U eliminates all horizontal structure;
             * sixteen additive taps average broad regions in both axes. */
            unsigned n=6;
            for(unsigned side=0;side<2;side++)for(unsigned sy=0;sy<4;sy++)for(unsigned sx=0;sx<4;sx++) {
                float x0=side?4.f:0.f,x1=x0+4.f;
                float base=side?u-40.f/renderer.native_color.width:0.f;
                float sample=base+(sx*10.f+5.f)/renderer.native_color.width;
                float shift=((int)sy*2-3)*v/64.f;
                float v0=shift>0?shift:0, v1=v+shift<v?v+shift:v;
                const Render3dsVertex q[6]={
                    {x0,0,0,sample,v0,.65f,.65f,.65f,.0625f},{x1,0,0,sample,v0,.65f,.65f,.65f,.0625f},{x0,8,0,sample,v1,.65f,.65f,.65f,.0625f},
                    {x1,0,0,sample,v0,.65f,.65f,.65f,.0625f},{x1,8,0,sample,v1,.65f,.65f,.65f,.0625f},{x0,8,0,sample,v1,.65f,.65f,.65f,.0625f}};
                memcpy(renderer.present_vertices+n,q,sizeof(q));n+=6;
            }
            for(unsigned side=0;side<2;side++) {
                float x0=side?360.f:0.f,x1=x0+40.f, sample=side?.75f:.25f;
                const Render3dsVertex q[6]={
                    {x0,0,0,sample,0,1,1,1,1},{x1,0,0,sample,0,1,1,1,1},{x0,240,0,sample,1,1,1,1,1},
                    {x1,0,0,sample,0,1,1,1,1},{x1,240,0,sample,1,1,1,1,1},{x0,240,0,sample,1,1,1,1,1}};
                memcpy(renderer.present_vertices+n,q,sizeof(q));n+=6;
            }
            if(renderer.ambient_mask_target) {
                /* Reuse the ambient's four horizontal samples per edge, but
                 * preserve every source row and keep the two edges separate. */
                for(unsigned side=0;side<2;side++)for(unsigned tap=0;tap<4;tap++) {
                    float x0=side?4.f:0.f,x1=x0+4.f;
                    float base=side?u-40.f/renderer.native_color.width:0.f;
                    float sample=base+(tap*10.f+5.f)/renderer.native_color.width;
                    const Render3dsVertex q[6]={
                        {x0,0,0,sample,0,1,1,1,1},{x1,0,0,sample,0,1,1,1,1},{x0,240,0,sample,v,1,1,1,1},
                        {x1,0,0,sample,0,1,1,1,1},{x1,240,0,sample,v,1,1,1,1},{x0,240,0,sample,v,1,1,1,1}};
                    memcpy(renderer.present_vertices+n,q,sizeof(q));n+=6;
                }
                for(unsigned side=0;side<2;side++) {
                    float x0=side?360.f:0.f,x1=x0+40.f,sample=side?.75f:.25f;
                    const Render3dsVertex q[6]={
                        {x0,0,0,sample,0,1,1,1,1},{x1,0,0,sample,0,1,1,1,1},{x0,240,0,sample,240.f/256.f,1,1,1,1},
                        {x1,0,0,sample,0,1,1,1,1},{x1,240,0,sample,240.f/256.f,1,1,1,1},{x0,240,0,sample,240.f/256.f,1,1,1,1}};
                    memcpy(renderer.present_vertices+n,q,sizeof(q));n+=6;
                }
            }
            GSPGPU_FlushDataCache(renderer.present_vertices,n*sizeof(Render3dsVertex));
            C3D_RenderTargetClear(renderer.ambient_target,C3D_CLEAR_COLOR,0x000000FF,0);
            C3D_FrameDrawOn(renderer.ambient_target);
            C3D_Mtx projection;Mtx_Ortho(&projection,0,8,0,8,1,-1,true);
            C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,renderer.projection_location,&projection);
            C3D_TexSetFilter(&renderer.native_color,GPU_LINEAR,GPU_LINEAR);C3D_TexBind(0,&renderer.native_color);
            C3D_TexEnvInit(env);C3D_TexEnvSrc(env,C3D_RGB,GPU_TEXTURE0,GPU_PRIMARY_COLOR,0);
            C3D_TexEnvFunc(env,C3D_RGB,GPU_MODULATE);C3D_TexEnvSrc(env,C3D_Alpha,GPU_PRIMARY_COLOR,0,0);
            C3D_TexEnvFunc(env,C3D_Alpha,GPU_REPLACE);
            C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_SRC_ALPHA,GPU_ONE,GPU_ONE,GPU_ZERO);
            draw_arrays(6,192);
            C3D_FrameSplit(GX_CMDLIST_FLUSH);
            if(renderer.ambient_mask_target) {
                C3D_RenderTargetClear(renderer.ambient_mask_target,C3D_CLEAR_COLOR,0x000000FF,0);
                C3D_FrameDrawOn(renderer.ambient_mask_target);
                Mtx_Ortho(&projection,0,8,0,256,1,-1,true);
                C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,renderer.projection_location,&projection);
                C3D_TexSetFilter(&renderer.native_color,GPU_NEAREST,GPU_NEAREST);
                C3D_TexBind(0,&renderer.native_color);
                /* The ambient draw consumed stage 0's dirty flag. Reacquire
                 * it so Citro3D uploads the mask's source/alpha operations. */
                env=C3D_GetTexEnv(0);C3D_TexEnvInit(env);
                C3D_TexEnvSrc(env,C3D_Alpha,GPU_TEXTURE0,GPU_TEXTURE0,0);
                C3D_TexEnvOpAlpha(env,GPU_TEVOP_A_SRC_R,GPU_TEVOP_A_SRC_G,GPU_TEVOP_A_SRC_ALPHA);
                C3D_TexEnvFunc(env,C3D_Alpha,GPU_ADD);
                C3D_TexEnv *e=C3D_GetTexEnv(1);C3D_TexEnvInit(e);
                C3D_TexEnvSrc(e,C3D_Alpha,GPU_PREVIOUS,GPU_TEXTURE0,0);
                C3D_TexEnvOpAlpha(e,GPU_TEVOP_A_SRC_ALPHA,GPU_TEVOP_A_SRC_B,GPU_TEVOP_A_SRC_ALPHA);
                C3D_TexEnvFunc(e,C3D_Alpha,GPU_ADD);C3D_TexEnvScale(e,C3D_Alpha,GPU_TEVSCALE_4);
                e=C3D_GetTexEnv(2);C3D_TexEnvInit(e);C3D_TexEnvScale(e,C3D_Alpha,GPU_TEVSCALE_4);
                e=C3D_GetTexEnv(3);C3D_TexEnvInit(e);
                C3D_TexEnvSrc(e,C3D_RGB,GPU_PREVIOUS,0,0);
                C3D_TexEnvOpRgb(e,GPU_TEVOP_RGB_SRC_ALPHA,GPU_TEVOP_RGB_SRC_COLOR,GPU_TEVOP_RGB_SRC_COLOR);
                C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ONE,GPU_ONE,GPU_ZERO);
                draw_arrays(210,48);
                for(unsigned i=1;i<=3;i++)C3D_TexEnvInit(C3D_GetTexEnv(i));
                C3D_FrameSplit(GX_CMDLIST_FLUSH);
            }
        } else GSPGPU_FlushDataCache(renderer.present_vertices,sizeof(quad));
        C3D_RenderTargetClear(renderer.display?renderer.bottom_target:renderer.target,C3D_CLEAR_COLOR,0x000000FF,0);
        C3D_FrameDrawOn(renderer.display?renderer.bottom_target:renderer.target);
        renderer.stats.lcd_presents++;
        C3D_Mtx present_projection;
        Mtx_OrthoTilt(&present_projection,0,renderer.display?320:400,240,0,1,-1,true);
        C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,renderer.projection_location,&present_projection);
        C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,GPU_ONE,GPU_ZERO);
        env=C3D_GetTexEnv(0);C3D_TexEnvInit(env);
        C3D_TexEnvSrc(env,C3D_Both,GPU_TEXTURE0,0,0);C3D_TexEnvFunc(env,C3D_Both,GPU_REPLACE);
        if(glow) {C3D_TexBind(0,&renderer.ambient_color);draw_arrays(198,12);}
        if(glow && renderer.ambient_mask_target) {
            C3D_TexBind(0,&renderer.ambient_mask);
            C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ZERO,GPU_SRC_COLOR,GPU_ONE,GPU_ZERO);
            draw_arrays(258,12);
            C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_ONE,GPU_ZERO,GPU_ONE,GPU_ZERO);
        }
        C3D_TexSetFilter(&renderer.native_color,GPU_NEAREST,GPU_NEAREST);
        C3D_TexBind(0,&renderer.native_color);
        draw_arrays(0,6);
#ifdef SH_3DS_GAME
        if(!renderer.display && counter_text[0]) {
            counter_build();
            if(counter_count) {
                /* C3D_GetBufInfo marks the state dirty only when called.
                 * The present-quad draw has already consumed that dirty bit;
                 * modifying the same struct alone leaves the GPU reading the
                 * six-vertex quad with the much larger text vertex count. */
                C3D_BindProgram(&renderer.program);
                C3D_FVUnifMtx4x4(GPU_VERTEX_SHADER,renderer.projection_location,&present_projection);
                C3D_AttrInfo *attrs=C3D_GetAttrInfo();AttrInfo_Init(attrs);
                AttrInfo_AddLoader(attrs,0,GPU_FLOAT,3);AttrInfo_AddLoader(attrs,1,GPU_FLOAT,2);
                AttrInfo_AddLoader(attrs,2,GPU_FLOAT,4);
                C3D_SetScissor(GPU_SCISSOR_DISABLE,0,0,0,0);
                C3D_StencilTest(false,GPU_ALWAYS,0,255,255);
                C3D_AlphaTest(false,GPU_ALWAYS,0);
                C3D_DepthTest(false,GPU_ALWAYS,GPU_WRITE_COLOR);
                C3D_TexEnvInit(env);C3D_TexEnvSrc(env,C3D_Both,GPU_PRIMARY_COLOR,0,0);
                C3D_TexEnvFunc(env,C3D_Both,GPU_REPLACE);
                C3D_AlphaBlend(GPU_BLEND_ADD,GPU_BLEND_ADD,GPU_SRC_ALPHA,GPU_ONE_MINUS_SRC_ALPHA,GPU_ONE,GPU_ZERO);
                BufInfo_Init(buffers);BufInfo_Add(buffers,counter_vertices,sizeof(Render3dsVertex),3,0x210);
                C3D_SetBufInfo(buffers);
                draw_arrays(0,counter_count);
                invalidate_draw_state();
            }
        }
#endif
    }
    osTickCounterUpdate(&renderer.cpu_timer);
    renderer.stats.cpu_prepare_ms = osTickCounterRead(&renderer.cpu_timer);
    C3D_FrameEnd(GX_CMDLIST_FLUSH);
    renderer.pending_draw=renderer.stats.draw_calls!=0;
    renderer.stats.command_buffer_usage = C3D_GetCmdBufUsage();
    renderer.in_frame = false;
    ++renderer.stats.frames;
}
void render3ds_end_frame(void) {finish_frame(true);}
void render3ds_end_psx_part(void) {finish_frame(false);}
bool render3ds_present_psx(void)
{
    if(!renderer.native_target || renderer.in_frame)return false;
    native_begin=true;
    bool begun=render3ds_begin_frame();native_begin=false;
    if(!begun)return false;
    renderer.native_frame=true;finish_frame(true);return true;
}

static bool valid_dimension(unsigned value)
{
    return value >= 8 && value <= 1024 && !(value & (value - 1));
}
static void flush_texture(Render3dsTexture *texture)
{
    render3ds_texture_psx_coverage(texture,3); /* Generic updates conservatively invalidate class hints. */
    PROFILE_START(start);
    C3D_TexFlush(&texture->gpu);
    PROFILE_END(GP_UPLOAD,start);
    PROFILE_COUNT(GC_UPLOADS,1);PROFILE_COUNT(GC_UPLOAD_BYTES,texture->gpu.size);
}

bool render3ds_texture_update_rgba8(Render3dsTexture *texture,
                                   const uint8_t *rgba, size_t stride)
{
    if (!renderer.active || renderer.in_frame || !texture || !rgba ||
        stride < (size_t)texture->gpu.width * 4 ||
        stride > SIZE_MAX / texture->gpu.height)
        return false;
    wait_idle();
    PROFILE_START(decode);
    for (unsigned y = 0; y < texture->gpu.height; ++y) {
        for (unsigned x = 0; x < texture->gpu.width; ++x) {
            const size_t offset = texture3ds_offset(texture->gpu.width, texture->gpu.height, x, y);
            texture3ds_write_rgba8((uint8_t *)texture->gpu.data + offset, rgba + y * stride + x * 4);
        }
    }
    PROFILE_END(GP_DECODE,decode);PROFILE_COUNT(GC_DECODES,1);
    flush_texture(texture);
    return true;
}

void render3ds_texture_linear(Render3dsTexture *texture,bool linear)
{
    C3D_TexSetFilter(&texture->gpu,linear?GPU_LINEAR:GPU_NEAREST,linear?GPU_LINEAR:GPU_NEAREST);
}
Render3dsTexture *render3ds_texture_create_rgba8(unsigned width, unsigned height,
                                              const uint8_t *rgba, size_t stride)
{
    if (!renderer.stats.ready || renderer.in_frame || !rgba ||
        !valid_dimension(width) || !valid_dimension(height) ||
        stride < (size_t)width * 4 || stride > SIZE_MAX / height)
        return NULL;
    Render3dsTexture *texture = calloc(1, sizeof(*texture));
    if (!texture)
        return NULL;
    if (!C3D_TexInit(&texture->gpu, width, height, GPU_RGBA8)) {
        free(texture);
        return NULL;
    }
    C3D_TexSetFilter(&texture->gpu, GPU_NEAREST, GPU_NEAREST);
    C3D_TexSetWrap(&texture->gpu, GPU_CLAMP_TO_EDGE, GPU_CLAMP_TO_EDGE);
    if (!render3ds_texture_update_rgba8(texture, rgba, stride)) {
        C3D_TexDelete(&texture->gpu);
        free(texture);
        return NULL;
    }
    texture->next = renderer.textures;
    renderer.textures = texture;
    renderer.stats.texture_bytes += texture->gpu.size;
    return texture;
}

void render3ds_texture_destroy(Render3dsTexture *texture)
{
    if (!texture || renderer.in_frame)
        return;
    Render3dsTexture **link = &renderer.textures;
    while (*link && *link != texture)
        link = &(*link)->next;
    if (!*link)
        return;
    wait_idle();
    C3D_TexBind(0, NULL);
    *link = texture->next;
    renderer.stats.texture_bytes -= texture->gpu.size;
    C3D_TexDelete(&texture->gpu);
    free(texture);
}

#ifdef SH_3DS_GAME
bool render3ds_texture_update_tiles(Render3dsTexture *texture,void *decode,
                                   unsigned x0,unsigned y0,unsigned x1,unsigned y1)
{
    if(!renderer.stats.ready || renderer.in_frame || !texture || texture->gpu.width!=256 ||
       texture->gpu.height!=256 || x0>=x1 || y0>=y1 || x1>32 || y1>32)return false;
    wait_idle();
    PROFILE_START(start);
    if(!game_texture_decode_tiles(decode,texture->gpu.data,x0,y0,x1,y1))return false;
    PROFILE_END(GP_DECODE,start);PROFILE_COUNT(GC_DECODES,1);
    /* A single aligned contiguous flush spans the modified tile rectangle.
     * Intervening unmodified tiles are safe to flush, with no extra fences. */
    unsigned first=(y0*32+x0)*256,bytes=((y1-1)*32+x1)*256-first;
    PROFILE_START(upload);
    GSPGPU_FlushDataCache((uint8_t*)texture->gpu.data+first,bytes);
    PROFILE_END(GP_UPLOAD,upload);
    PROFILE_COUNT(GC_UPLOADS,1);PROFILE_COUNT(GC_UPLOAD_BYTES,bytes);
    render3ds_texture_psx_coverage(texture,3);
    return true;
}
#endif
bool render3ds_texture_update_rows(Render3dsTexture *texture, Render3dsReadRow read, void *context)
{
    if (!renderer.stats.ready || renderer.in_frame || !texture || !read) return false;
    wait_idle();
    PROFILE_START(decode);
    uint32_t row[1024];
#ifdef SH_3DS_GAME
    if(read==game_texture_decode_row && texture->gpu.width==256 && texture->gpu.height==256) {
        if(!game_texture_decode_tiled(context,texture->gpu.data))return false;
    } else
#endif
    {
    for (unsigned y=0; y<texture->gpu.height; y++) {
        if (!read(context,y,(uint8_t*)row,texture->gpu.width)) return false;
        texture3ds_write_row(texture->gpu.data,texture->gpu.width,y,row,texture->gpu.width);
    }
    }
    PROFILE_END(GP_DECODE,decode);PROFILE_COUNT(GC_DECODES,1);
    flush_texture(texture);
    return true;
}

Render3dsTexture *render3ds_texture_create_rows(unsigned width, unsigned height,
                                               Render3dsReadRow read, void *context,
                                               unsigned *physical_width, unsigned *physical_height)
{
    if (physical_width) *physical_width = 0;
    if (physical_height) *physical_height = 0;
    if (!renderer.stats.ready || renderer.in_frame || !read || !width || !height || width > 1024 || height > 1024)
        return NULL;
    unsigned pw = 8, ph = 8;
    while (pw < width) pw *= 2;
    while (ph < height) ph *= 2;
    Render3dsTexture *texture = calloc(1, sizeof(*texture));
    if (!texture) return NULL;
    if (!C3D_TexInit(&texture->gpu, pw, ph, GPU_RGBA8)) { free(texture); return NULL; }
    C3D_TexSetFilter(&texture->gpu, GPU_NEAREST, GPU_NEAREST);
    C3D_TexSetWrap(&texture->gpu, GPU_CLAMP_TO_EDGE, GPU_CLAMP_TO_EDGE);
    PROFILE_START(decode);
    memset(texture->gpu.data, 0, texture->gpu.size);
    uint32_t row[1024];
#ifdef SH_3DS_GAME
    if(read==game_texture_decode_row && width==256 && height==256) {
        if(!game_texture_decode_tiled(context,texture->gpu.data)){C3D_TexDelete(&texture->gpu);free(texture);return NULL;}
    } else
#endif
    {
    for (unsigned y = 0; y < height; ++y) {
        if (!read(context, y, (uint8_t*)row, width)) { C3D_TexDelete(&texture->gpu); free(texture); return NULL; }
        texture3ds_write_row(texture->gpu.data,pw,y,row,width);
    }
    }
    PROFILE_END(GP_DECODE,decode);PROFILE_COUNT(GC_DECODES,1);
    flush_texture(texture);
    texture->next = renderer.textures; renderer.textures = texture;
    renderer.stats.texture_bytes += texture->gpu.size;
    if (physical_width) *physical_width = pw;
    if (physical_height) *physical_height = ph;
    return texture;
}

bool render3ds_draw_texture_region(Render3dsTexture *t,
    float x, float y, float width, float height,
    unsigned sx, unsigned sy, unsigned sw, unsigned sh, unsigned flips, bool blend)
{
    if (!t || !sw || !sh || width <= 0 || height <= 0 || flips > 3 ||
        sx > t->gpu.width || sw > t->gpu.width - sx ||
        sy > t->gpu.height || sh > t->gpu.height - sy) return false;
    float u0 = (float)sx / t->gpu.width, u1 = (float)(sx + sw) / t->gpu.width;
    float vt = 1.0f - (float)sy / t->gpu.height, vb = 1.0f - (float)(sy + sh) / t->gpu.height;
    if (flips & 1) { float tmp = u0; u0 = u1; u1 = tmp; }
    if (flips & 2) { float tmp = vt; vt = vb; vb = tmp; }
    const Render3dsVertex q[6] = {
        {x,y,0,u0,vt,1,1,1,1}, {x+width,y,0,u1,vt,1,1,1,1}, {x+width,y+height,0,u1,vb,1,1,1,1},
        {x,y,0,u0,vt,1,1,1,1}, {x+width,y+height,0,u1,vb,1,1,1,1}, {x,y+height,0,u0,vb,1,1,1,1}};
    return render3ds_draw_triangles(q,6,t,blend);
}
