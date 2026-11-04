#ifndef SH_GAME_FEEDBACK_H
#define SH_GAME_FEEDBACK_H
#include <stdint.h>
/* Internal draw identity: never a PSX texture page or a cache key. */
#define GAME_FEEDBACK_PAGE 0x10000u
#define GAME_STATUS_FONT_PAGE 0x20000u
/* Real producer/capture evidence; bounded ring, no hot-path file I/O. */
#define GAME_FEEDBACK_TRACE_WORDS 24
/* A same-frame SPRT sampling an offscreen render target is framebuffer
 * composition, not authored 2D artwork. Its UVs remain on the PSX pages. */
static inline int game_feedback_target_sprite(unsigned tx,unsigned ty,unsigned w,unsigned h,
    unsigned x,unsigned y,unsigned width,unsigned height)
{
    return tx>=x && ty>=y && w<=width && h<=height &&
        tx-x<=width-w && ty-y<=height-h;
}
static inline void game_feedback_target_vertex(float *v,unsigned page,unsigned x,unsigned y,unsigned margin,int extension)
{
    v[0]+=extension;
    v[3]=(v[3]*256.0f+(page&15)*64-x+margin+extension)/512.0f;
    v[4]=1.0f-((1.0f-v[4])*256.0f+(page&16)*16-y)/256.0f;
}
unsigned Game3ds_FeedbackTraceRead(unsigned index,uint32_t *out);
/* PSX texture modulation truncates in the 5-bit domain. Expanding to RGBA8
 * before multiplying 127/128 leaves bright pixels unchanged on readback. */
static inline uint16_t game_feedback_modulate(uint16_t word,unsigned r,unsigned g,unsigned b)
{
    unsigned red=((word&31)*r)>>7,green=(((word>>5)&31)*g)>>7,blue=(((word>>10)&31)*b)>>7;
    if(red>31)red=31;
    if(green>31)green=31;
    if(blue>31)blue=31;
    return (word&0x8000)|red|(green<<5)|(blue<<10);
}
/* Exact modulation/expansion lookup for one feedback draw color. Only 384
 * bytes of channel tables; zero and STP-black retain their distinct alpha. */
typedef struct {uint32_t color,valid,red[32],green[32],blue[32];} GameFeedbackDecode;
static inline void game_feedback_decode_init(GameFeedbackDecode *d,uint32_t color)
{
    if(d->valid && d->color==color)return;
    unsigned scale[3]={color&255,(color>>8)&255,color>>16};
    for(unsigned i=0;i<32;i++)for(unsigned c=0;c<3;c++) {
        unsigned n=(i*scale[c])>>7;if(n>31)n=31;
        uint32_t value=((n<<3)|(n>>2))<<(c*8);
        if(c==0)d->red[i]=value;else if(c==1)d->green[i]=value;else d->blue[i]=value;
    }
    d->color=color;d->valid=1;
}
static inline uint32_t game_feedback_decode_pixel(const GameFeedbackDecode *d,uint16_t word)
{
    uint32_t rgb=d->red[word&31]|d->green[(word>>5)&31]|d->blue[(word>>10)&31];
    return rgb|((word&0x8000)?0x80000000u:rgb?0xff000000u:0);
}
/* Feedback samples native pixels directly. The logical PSX framebuffer is
 * still stored in canonical VRAM for StoreImage/MoveImage and game consumers.
 * Repeated 400x240 -> 320x224 -> 400x240 nearest resolves are not invertible. */
static inline void game_feedback_vertex(float *v,unsigned page,unsigned width,unsigned height,
    unsigned logical_width,unsigned logical_height,int canvas_x,int canvas_y,unsigned origin_y)
{
    float sx=(float)width/logical_width,sy=(float)height/logical_height;
    float u=v[3]*256.0f-.5f+(page&15)*64;
    float y=(1-v[4])*256.0f-.5f+(page&16)*16-origin_y;
    v[0]=(v[0]-canvas_x-.5f)*sx;
    v[1]=(v[1]-canvas_y-.5f)*sy;
    v[3]=u*sx/512.0f;v[4]=1-y*sy/256.0f;
}
#endif
