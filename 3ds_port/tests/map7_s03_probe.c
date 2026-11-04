#include "game.h"
#include "game3ds.h"
#include "bodyprog/bodyprog.h"
#include <string.h>

_Static_assert(sizeof(s_Savegame) == 636, "Retail save ABI");
extern u8 map7_s03_D_800F4805;
extern void map7_s03_func_800E3390(void);
extern void map7_s03_func_800E3C48(void);
extern void map7_s03_func_800E3D18(void);
extern void map7_s03_func_800DDBBC(s_SubCharacter*);
extern void map7_s03_func_800DFCE4(s_SubCharacter*);
extern void map7_s03_func_800DEBA8(s_SubCharacter*);

void map7_s03_probe_scene(unsigned kaufmann, unsigned cybil, unsigned step)
{
    Savegame_EventFlagClear(EventFlag_391);
    Savegame_EventFlagClear(EventFlag_449);
    if (kaufmann) Savegame_EventFlagSet(EventFlag_391);
    if (cybil) Savegame_EventFlagSet(EventFlag_449);
    map7_s03_D_800F4805 = step;
    map7_s03_func_800E3390();
}

unsigned map7_s03_probe_good(unsigned cybil)
{
    Savegame_EventFlagClear(EventFlag_449);
    Savegame_EventFlagClear(EventFlag_583);
    Savegame_EventFlagClear(EventFlag_585);
    Savegame_EventFlagClear(EventFlag_587);
    if (cybil) Savegame_EventFlagSet(EventFlag_449);
    map7_s03_D_800F4805 = 0;
    map7_s03_func_800E3C48();
    return !Savegame_EventFlagGet(EventFlag_587) ||
        !!Savegame_EventFlagGet(EventFlag_583) != !!cybil ||
        !!Savegame_EventFlagGet(EventFlag_585) == !!cybil;
}

unsigned map7_s03_probe_bad(unsigned cybil)
{
    Savegame_EventFlagClear(EventFlag_449);
    Savegame_EventFlagClear(EventFlag_584);
    Savegame_EventFlagClear(EventFlag_586);
    if (cybil) Savegame_EventFlagSet(EventFlag_449);
    map7_s03_D_800F4805 = 2;
    map7_s03_func_800E3D18();
    return !!Savegame_EventFlagGet(EventFlag_584) != !!cybil ||
        !!Savegame_EventFlagGet(EventFlag_586) == !!cybil;
}

unsigned map7_s03_probe_boss(unsigned incubus, unsigned lethal)
{
    s_SubCharacter *boss = &g_SysWork.npcs[2];
    memset(boss, 0, sizeof(*boss));
    Savegame_EventFlagClear(EventFlag_578);
    Savegame_EventFlagClear(EventFlag_582);
    boss->flags = CharaFlag_Hit;
    boss->health = Q12(100.0f);
    boss->damage.amount = lethal ? Q12(100.0f) : Q12(10.0f);
    boss->properties.incubus.bossFightTimer_F4 = Q12(30.0f);
    if (incubus) map7_s03_func_800DDBBC(boss);
    else map7_s03_func_800DFCE4(boss);
    if (!lethal) return boss->health != Q12(90.0f);
    if (incubus) {
        if (boss->health != 0 || boss->model.controlState != 12) return 1;
        boss->model.stateStep = 1;
        boss->properties.incubus.timer_E8 = -1;
        map7_s03_func_800DEBA8(boss);
        return boss->model.controlState != 13 || !Savegame_EventFlagGet(EventFlag_578);
    }
    return boss->health != NO_VALUE || boss->model.controlState != 5 || !Savegame_EventFlagGet(EventFlag_582);
}
