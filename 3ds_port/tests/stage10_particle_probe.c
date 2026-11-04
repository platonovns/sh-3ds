#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_data.h"
#include "psx_memory.h"
#include <string.h>
unsigned stage10_particle_packet(void)
{
    static s_MapOverlayHdr overlay;
    static s_MapHdr_field_4C effect;
    static q19_12 wind;
    MATRIX identity={{{4096,0,0},{0,4096,0},{0,0,4096}},{0,0,0}};
    overlay.unkTable1_4C=&effect;overlay.windSpeedX=overlay.windSpeedZ=&wind;
    g_pMapOverlayHeader=&overlay;
    memset(&effect,0,sizeof(effect));memset(PSX_SCRATCH,0,1024);
    effect.field_4.vz_4=Q12(4.0f);effect.field_A=20;
    effect.field_10.field_0=64;
    s_func_80064334 *scratch=PSX_SCRATCH;scratch->field_0.field_2C=160;
    g_SysWork.field_2388.field_154.effectsInfo_0.field_0.field_0=0;
    g_DeltaTime=0;
    InitGeom();SetRotMatrix(&identity);SetTransMatrix(&identity);SetGeomOffset(0,0);SetGeomScreen(160);
    g_ActiveBufferIdx=0;GsClearOt(0,0,&g_OrderingTable0[0]);
    POLY_FT4 *first=(POLY_FT4*)PSX_ADDR(0x801A2600),*out=first;
    func_80064334(&out,0);
    GsDrawOt(&g_OrderingTable0[0]);
    return (PACKET*)out-(PACKET*)first;
}
