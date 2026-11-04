#ifndef SH_RENDER_3DS_H
#define SH_RENDER_3DS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct Render3dsTexture Render3dsTexture;

/* Screen pixels, top-left origin; normalized PICA UV (U right, V up) and RGBA.
 * All RGBA upload APIs take native top-down rows; no asset-specific flips.
 * A future 320x240 logical adapter can add x=40 and clip to [40,360), with no
 * rescaling of coordinates or changes to this physical 400x240 target. */
typedef struct {
    float x, y, z;
    float u, v;
    float r, g, b, a;
} Render3dsVertex;

typedef struct {
    bool citro3d_ok, target_ok, shader_ok, buffer_ok, ready;
    const char *error;
    uint32_t command_buffer_bytes, vertex_buffer_bytes, vertex_capacity;
    uint32_t target_bytes, texture_bytes, frames, vertices_used, rejected_draws;
    float cpu_prepare_ms, gpu_queue_ms, command_buffer_usage;
    bool timing_valid;
    uint32_t idle_calls;
    uint64_t idle_ticks;
    float begin_wait_ms;
    uint32_t draw_calls;
    uint32_t readback_bytes, readback_copies, readback_direct_mismatches;
    uint32_t native_parts,lcd_presents;
} Render3dsStats;

bool render3ds_init(void);
void render3ds_shutdown(void);
const Render3dsStats *render3ds_stats(void);

/* One bounded buffer per frame. Begin waits for the previous GPU queue before
 * reusing it. Oversized draws fail without wrapping or overwriting live data. */
bool render3ds_begin_frame(void);
/* Rasterize PSX integer pixels before the final rotated/scaled presentation. */
bool render3ds_begin_psx_frame(unsigned width,unsigned height);
bool render3ds_select_vram_surface(bool select);
uint32_t render3ds_psx_surface_bytes(void);
/* Destination belongs to the frame, not to individual primitive producers. */
bool render3ds_set_display(unsigned display);
void render3ds_console_bottom(void);
void render3ds_counter(const char *text,unsigned style);
bool render3ds_resolve_psx(unsigned x,unsigned y,unsigned width,unsigned height,unsigned out_width,unsigned out_height,uint16_t *out,unsigned stride);
void render3ds_continue_psx_frame(bool preserve);
bool render3ds_read_psx(unsigned x,unsigned y,unsigned width,unsigned height,
                        uint16_t *out,unsigned stride);
bool render3ds_draw_triangles(const Render3dsVertex *vertices, size_t count,
                             Render3dsTexture *texture, bool alpha_blend);
/* Half-open rectangle in screen pixels; empty rectangles reject all draws. */
bool render3ds_set_scissor(int left, int top, int right, int bottom);
void render3ds_end_frame(void);
void render3ds_end_psx_part(void);
bool render3ds_present_psx(void);
void render3ds_ambient_enable(bool enabled);
void render3ds_wait_idle(void);
bool render3ds_draw_psx_triangles(const Render3dsVertex *vertices, size_t count,
                                Render3dsTexture *texture, unsigned blend);
/* GP0(E6): bit0 forces framebuffer mask, bit1 rejects masked destination. */
void render3ds_set_psx_mask(unsigned bits);
/* Conservative nonzero source classes: bit0 opaque, bit1 STP. */
void render3ds_texture_psx_coverage(Render3dsTexture *texture,unsigned classes);
void render3ds_texture_linear(Render3dsTexture *texture,bool linear);
bool render3ds_draw_psx_ordered(const Render3dsVertex *vertices,size_t count,
    const uint16_t *primitive_sizes,unsigned primitives,Render3dsTexture *texture,unsigned blend);

/* Call outside a frame. Create copies top-down RGBA8 rows into tiled linear
 * memory; caller retains its source. Update/destroy wait for pending GPU reads.
 * Dimensions must be powers of two in [8,1024]. No mipmaps or staging buffer. */
Render3dsTexture *render3ds_texture_create_rgba8(unsigned width, unsigned height,
                                              const uint8_t *rgba, size_t stride);
bool render3ds_texture_update_rgba8(Render3dsTexture *texture,
                                   const uint8_t *rgba, size_t stride);
void render3ds_texture_destroy(Render3dsTexture *texture);

/* Reusable streaming path: one <=4096-byte source row, zero-filled POT padding.
 * UVs: [0,logical_width/physical_width], [1-logical_height/physical_height,1].
 * Callback writes top-down RGBA8, returns true on success. */
typedef bool (*Render3dsReadRow)(void *context, unsigned y, uint8_t *rgba, unsigned width);
/* Update an existing allocation outside a frame; drains pending GPU reads. */
bool render3ds_texture_update_rows(Render3dsTexture *texture, Render3dsReadRow read, void *context);
bool render3ds_texture_update_tiles(Render3dsTexture *texture,void *decode,
                                   unsigned x0,unsigned y0,unsigned x1,unsigned y1);
Render3dsTexture *render3ds_texture_create_rows(unsigned logical_width, unsigned logical_height,
                                               Render3dsReadRow read, void *context,
                                               unsigned *physical_width, unsigned *physical_height);

/* Shared texture adapter: source rectangle in top-left texel coordinates,
 * converted once to PICA U=x/W, V=1-y/H. No texel copies. Flips are explicit
 * draw attributes (bit 0 U, bit 1 V), useful for sprites and diagnostics. */
bool render3ds_draw_texture_region(Render3dsTexture *texture,
    float x, float y, float width, float height,
    unsigned source_x, unsigned source_y, unsigned source_width, unsigned source_height,
    unsigned flips, bool alpha_blend);

#endif
