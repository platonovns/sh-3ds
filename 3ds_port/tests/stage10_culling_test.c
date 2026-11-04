#include "game_screen.h"
#include <assert.h>
#include <stdio.h>
static float cross(const float *a,const float *b,float x,float y)
{return (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]);}
int main(void)
{
    unsigned count=0,rejected=0;
    for(unsigned phase=0;phase<2;phase++)for(unsigned i=0;i<81;i++)for(unsigned j=0;j<81;j++)for(unsigned k=0;k<81;k++) {
        float a[2]={i%9-2.0f+phase*.5f,i/9-2.0f+phase*.5f};
        float b[2]={j%9-2.0f+phase*.5f,j/9-2.0f+phase*.5f};
        float c[2]={k%9-2.0f+phase*.5f,k/9-2.0f+phase*.5f};
        count++;
        if(!game_screen_triangle_outside(a,b,c,0,0,4,4))continue;
        rejected++;
        if(cross(a,b,c[0],c[1])==0)continue;
        for(unsigned y=0;y<4;y++)for(unsigned x=0;x<4;x++) {
            float u=cross(a,b,x+.5f,y+.5f),v=cross(b,c,x+.5f,y+.5f),w=cross(c,a,x+.5f,y+.5f);
            /* Any possible covered sample, even one on an inclusive edge,
             * must survive. This is stricter than either raster fill rule. */
            assert(!((u>=0 && v>=0 && w>=0)||(u<=0 && v<=0 && w<=0)));
        }
    }
    printf("PASS: %u triangles, %u rejected, no visible sample removed\n",count,rejected);
}
