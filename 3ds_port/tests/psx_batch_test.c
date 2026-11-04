#include "psx_batch.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    Render3dsVertex a[3]={{.x=0,.y=0},{.x=10,.y=0},{.x=0,.y=10}};
    Render3dsVertex b[3]={{.x=10,.y=0},{.x=10,.y=10},{.x=0,.y=10}};
    assert(!psx_triangles_overlap(a,b)); /* The two halves of a normal quad. */
    assert(psx_triangles_overlap(a,a));
    b[0].x=5;b[0].y=0;assert(psx_triangles_overlap(a,b));
    b[0].x=20;b[0].y=20;b[1].x=30;b[1].y=20;b[2].x=20;b[2].y=30;
    assert(!psx_triangles_overlap(a,b));
    assert(psx_batch_disjoint(psx_batch_bounds(a,3),psx_batch_bounds(b,3)));
    b[1]=b[0];b[2]=b[0];assert(!psx_triangles_overlap(a,b));
    puts("PASS: overlap detection, shared edges, separated geometry and degenerate triangles");
}
