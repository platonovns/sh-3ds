#ifndef SH_GAME_SCREEN_H
#define SH_GAME_SCREEN_H
/* Native, unrotated PSX target: exact binary integer sample centers. */
static inline void game_screen_point(float *out,int x,int y)
{
    out[0]=x+0.5f;out[1]=y+0.5f;
}
static inline int game_screen_signed11(unsigned value) {return (int)((value&2047)^1024)-1024;}
static inline float game_screen_uv(int value) {return (value+0.5f)/256.0f;}
/* Split full-height screen overlays must reach the same widescreen edges as
 * an unsplit overlay. Return which horizontal edges the piece touches. */
static inline unsigned game_screen_overlay_edges(int x,int y,int w,int h,unsigned width,unsigned height)
{
    int left=-(int)width/2,right=left+(int)width,top=-(int)height/2;
    if(w<=0 || h<(int)height || y>top || x<left || x+w>right)return 0;
    return (x==left?1u:0u)|(x+w==right?2u:0u);
}
static inline int game_screen_triangle_outside(const float *a,const float *b,const float *c,
    int left,int top,int right,int bottom)
{
    return (a[0]<=left && b[0]<=left && c[0]<=left) ||
        (a[0]>=right && b[0]>=right && c[0]>=right) ||
        (a[1]<=top && b[1]<=top && c[1]<=top) ||
        (a[1]>=bottom && b[1]>=bottom && c[1]>=bottom);
}
/* PSX rejects oversized polygon triangles before draw-area clipping. Check each
 * half of a quad independently, using decoded 11-bit integer coordinates. */
static inline int game_screen_triangle_size_valid(int ax,int ay,int bx,int by,int cx,int cy)
{
    int minx=ax,maxx=ax,miny=ay,maxy=ay;
    if(bx<minx)minx=bx;
    if(cx<minx)minx=cx;
    if(bx>maxx)maxx=bx;
    if(cx>maxx)maxx=cx;
    if(by<miny)miny=by;
    if(cy<miny)miny=cy;
    if(by>maxy)maxy=by;
    if(cy>maxy)maxy=cy;
    return maxx-minx<=1023 && maxy-miny<=511;
}
#endif
