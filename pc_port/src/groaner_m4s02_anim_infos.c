/* MAP4_S02 Groaner animation variant. Three durations differ from the
 * shared MAP2 seed in the USA retail overlay; keep both tables independent. */
#include "bodyprog/bodyprog.h"
#include <string.h>

extern s_AnimInfo GROANER_ANIM_INFOS[48];
s_AnimInfo GROANER_M4S02_ANIM_INFOS[48];

void GroanerM4S02AnimInfos_Init(void)
{
    memcpy(GROANER_M4S02_ANIM_INFOS, GROANER_ANIM_INFOS, sizeof(GROANER_M4S02_ANIM_INFOS));
    GROANER_M4S02_ANIM_INFOS[5].duration.constant = 0x18c00;
    GROANER_M4S02_ANIM_INFOS[13].duration.constant = 0x18400;
    GROANER_M4S02_ANIM_INFOS[25].duration.constant = 0x18400;
}
