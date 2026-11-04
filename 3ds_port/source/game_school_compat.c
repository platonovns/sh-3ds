/* Content-only native closure. Renderer, audio and command decoding stay owned
 * by the accepted baseline. These are existing PS1 presentation contracts. */
#include "game.h"
#include <psyq/libgpu.h>

void SetDrawStp(DR_STP* packet, int enable)
{
    /* Same original PsyCross producer, including the widened native OT tag. */
    setDrawStp(packet, enable);
}

void func_800892DC(s32 pattern, u8 amplitude)
{
    /* DualShock vibration, like func_800892A4/func_800894B8 in game_services.
     * New 3DS has no vibration actuator. This has no sound/gameplay effects. */
    (void)pattern;(void)amplitude;
}

/* Original Lakefront cutscene requests DualShock pattern 9. */
void func_800894DC(void)
{
    func_800892DC(9, 0xE0);
}
