/* Native GS coordinate initialization; original vw_* owns hierarchy/camera. */
#include "game.h"
#include "game3ds.h"
#include <psyq/libgs.h>
#include <string.h>

GsCOORDINATE2 *D_800C42B8;
MATRIX GsIDMATRIX = {{{4096,0,0},{0,4096,0},{0,0,4096}},{0,0,0}};
MATRIX GsIDMATRIX2 = {{{4096,0,0},{0,4096,0},{0,0,4096}},{0,0,0}};
MATRIX GsWSMATRIX;
void GsSetLsMatrix(MATRIX *m)
{
    if (!m) game3ds_halt(450,"GsSetLsMatrix null",0);
    SetRotMatrix(m); SetTransMatrix(m);
}

void GsInitCoordinate2(GsCOORDINATE2 *parent, GsCOORDINATE2 *coord)
{
    if (!coord) game3ds_halt(450, "GsInitCoordinate2 null", 0);
    memset(coord,0,sizeof(*coord));
    coord->coord = coord->workm = GsIDMATRIX;
    coord->super = parent;
}
