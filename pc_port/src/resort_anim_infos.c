/* Retail animation variants specific to Resort and Boat overlays. */
#include "bodyprog/bodyprog.h"
#include <string.h>
extern s_AnimInfo KAUFMANN_ANIM_INFOS[46], DAHLIA_ANIM_INFOS[52], CYBIL_ANIM_INFOS[64], GROANER_ANIM_INFOS[48];
void KaufmannAnimInfos_Init(void);
void DahliaAnimInfos_Init(void);
void GroanerAnimInfos_Init(void);
s_AnimInfo KAUFMANN_M5S02_ANIM_INFOS[46], DAHLIA_M6S01_ANIM_INFOS[52], CYBIL_M6S01_ANIM_INFOS[64], GROANER_M6S00_ANIM_INFOS[48];
void ResortAnimInfos_Init(void)
{
    KaufmannAnimInfos_Init(); DahliaAnimInfos_Init(); GroanerAnimInfos_Init();
    memcpy(KAUFMANN_M5S02_ANIM_INFOS, KAUFMANN_ANIM_INFOS, sizeof(KAUFMANN_M5S02_ANIM_INFOS));
    memcpy(DAHLIA_M6S01_ANIM_INFOS, DAHLIA_ANIM_INFOS, sizeof(DAHLIA_M6S01_ANIM_INFOS));
    memcpy(CYBIL_M6S01_ANIM_INFOS, CYBIL_ANIM_INFOS, sizeof(CYBIL_M6S01_ANIM_INFOS));
    memcpy(GROANER_M6S00_ANIM_INFOS, GROANER_ANIM_INFOS, sizeof(GROANER_M6S00_ANIM_INFOS));
    KAUFMANN_M5S02_ANIM_INFOS[7].duration.constant=0x8000;
    DAHLIA_M6S01_ANIM_INFOS[8].duration.constant=0x3000;
    DAHLIA_M6S01_ANIM_INFOS[9].duration.constant=0x2000;
    DAHLIA_M6S01_ANIM_INFOS[10].duration.constant=0x2000;
    DAHLIA_M6S01_ANIM_INFOS[11].duration.constant=0x3800; DAHLIA_M6S01_ANIM_INFOS[11].endKeyframeIdx=166;
    DAHLIA_M6S01_ANIM_INFOS[12].duration.constant=0x5000;
    DAHLIA_M6S01_ANIM_INFOS[13].duration.constant=0x5000;
    DAHLIA_M6S01_ANIM_INFOS[15].duration.constant=0x8000; DAHLIA_M6S01_ANIM_INFOS[15].startKeyframeIdx=236;
    CYBIL_M6S01_ANIM_INFOS[33].endKeyframeIdx=276;
    CYBIL_M6S01_ANIM_INFOS[34].endKeyframeIdx=284;
    CYBIL_M6S01_ANIM_INFOS[35].startKeyframeIdx=284;
    GROANER_M6S00_ANIM_INFOS[5].duration.constant=0x18c00;
    GROANER_M6S00_ANIM_INFOS[13].duration.constant=0x18400;
    GROANER_M6S00_ANIM_INFOS[25].duration.constant=0x18400;
}
