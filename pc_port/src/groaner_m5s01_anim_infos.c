/* USA MAP5_S01 variant: reset mutable native records at every overlay load. */
#include "bodyprog/bodyprog.h"
#include <string.h>

extern s_AnimInfo GROANER_ANIM_INFOS[48];
void GroanerAnimInfos_Init(void);
s_AnimInfo GROANER_M5S01_ANIM_INFOS[48];

void GroanerM5S01AnimInfos_Init(void)
{
    GroanerAnimInfos_Init();
    memcpy(GROANER_M5S01_ANIM_INFOS,GROANER_ANIM_INFOS,sizeof(GROANER_M5S01_ANIM_INFOS));
    GROANER_M5S01_ANIM_INFOS[5].duration.constant=0x18c00;
    GROANER_M5S01_ANIM_INFOS[13].duration.constant=0x18400;
    GROANER_M5S01_ANIM_INFOS[25].duration.constant=0x18400;
}
