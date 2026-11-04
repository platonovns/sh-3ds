/* Original lens-flare producers, linked only by the ARM diagnostic. */
#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include "bodyprog/screen/screen_data.h"
#include "bodyprog/screen/screen_draw.h"
#include <stddef.h>

unsigned stage10_lens_layout(unsigned which)
{
    static const unsigned values[]={sizeof(DR_MOVE),sizeof(TILE),sizeof(POLY_FT4),
        offsetof(s_800C4818,field_A),offsetof(s_800C4818,field_2)};
    return values[which];
}
void stage10_lens_setup(unsigned buffer)
{
    Game3ds_BeginUpdate(GameState_InGame);Screen_Init(320,false);
    g_ActiveBufferIdx=buffer;
    GsClearOt(0,0,&g_OrderingTable0[buffer]);
    GsOUT_PACKET_P=(PACKET*)Game3ds_PacketBegin(buffer);
    D_800C4818=(s_800C4818){0};
    D_800C4818.field_C=(VECTOR3){0,0,512};
    D_800C4818.field_8=4096;D_800C4818.field_20=2048;
}
unsigned stage10_lens_seed(unsigned on_screen)
{
    unsigned char *start=(unsigned char*)GsOUT_PACKET_P;
    VECTOR3 position={on_screen?0:1000,0,512};
    func_8008D5A0(&position,2048);
    Game3ds_PacketValidate();return (unsigned char*)GsOUT_PACKET_P-start;
}
unsigned stage10_lens_draw(void)
{
    unsigned char *start=(unsigned char*)GsOUT_PACKET_P;
    D_800C4818.field_2=1;func_8008D78C();
    Game3ds_PacketValidate();return (unsigned char*)GsOUT_PACKET_P-start;
}
