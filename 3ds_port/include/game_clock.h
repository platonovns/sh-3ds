#ifndef SH_GAME_CLOCK_H
#define SH_GAME_CLOCK_H
#include <stdint.h>
/* Independent system ticks, including work between explicit VSync calls.
 * Splitting seconds/remainder avoids overflow during long sessions. */
static inline uint32_t game_clock_units(uint64_t elapsed, uint32_t ticks_per_second, uint32_t units_per_second)
{
    return (uint32_t)((elapsed/ticks_per_second)*units_per_second+
        ((elapsed%ticks_per_second)*units_per_second)/ticks_per_second);
}
#endif
