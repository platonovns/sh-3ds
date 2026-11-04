#if defined(SH_3DS_GAME)
/* The MAP6_S03 retail table is byte-identical to MAP5_S02. */
#define STALKER_ANIM_INFOS STALKER_M5S02_ANIM_INFOS
#endif
#include "inline_no_dmpsx.h"

#include <psyq/gtemac.h>

#include "bodyprog/bodyprog.h"
#include "bodyprog/math/math.h"
#include "bodyprog/player.h"
#include "main/rng.h"
#include "maps/map6/map6_s03.h"
#include "maps/particle.h"
#include "maps/characters/stalker.h"

#include "../src/maps/characters/stalker.c" // 0x800CEFCC
