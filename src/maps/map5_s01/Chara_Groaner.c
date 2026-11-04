#include "inline_no_dmpsx.h"
#include <psyq/gtemac.h>
#include "bodyprog/bodyprog.h"
#include "bodyprog/math/math.h"
#include "bodyprog/player.h"
#include "main/rng.h"
#include "maps/map5/map5_s01.h"
#include "maps/particle.h"
#include "maps/characters/groaner.h"

#ifdef SH_3DS_GAME
extern s_AnimInfo GROANER_M5S01_ANIM_INFOS[48];
#define GROANER_ANIM_INFOS GROANER_M5S01_ANIM_INFOS
#endif

#include "../src/maps/characters/groaner.c" // 0x800E3294
