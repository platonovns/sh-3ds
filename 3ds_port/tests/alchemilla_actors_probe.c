/* Isolated original damage-state inputs, never linked into a hardware build. */
#include "bodyprog/bodyprog.h"
#include "bodyprog/game_boot/game_boot.h"
#include "maps/characters/puppet_nurse.h"
#include <string.h>
extern void PuppetNurseData_Init(void);
extern void map3_s03_PuppetNurse_Init(s_SubCharacter*,bool);
extern void map3_s03_PuppetNurse_DamageHandle(s_SubCharacter*);
unsigned actor_probe_out[8];
void actor_probe_nurse(unsigned difficulty,unsigned variant,unsigned damage)
{
    memset(&g_SysWork,0,sizeof(g_SysWork));
    Settings_RestoreDefaults();
    GameBoot_SavegameInitialize(18,difficulty);
    PuppetNurseData_Init();
    s_SubCharacter* n=&g_SysWork.npcs[0];
    n->model.charaId=variant ? Chara_PuppetNurse : Chara_PuppetDoctor;
    n->model.stateStep=variant ? variant : 1;
    n->field_40=0;
    g_SavegamePtr->ovlEnemyStates[18]=0xFFFFFFFF;
    map3_s03_PuppetNurse_Init(n,variant==0);
    actor_probe_out[0]=n->health;
    n->damage.amount=damage;
    map3_s03_PuppetNurse_DamageHandle(n);
    actor_probe_out[1]=n->health;
    actor_probe_out[2]=n->model.controlState;
    actor_probe_out[3]=n->properties.puppetNurse.field_118;
    actor_probe_out[4]=g_SavegamePtr->ovlEnemyStates[18];
    actor_probe_out[5]=n->damage.amount;
    actor_probe_out[6]=n->model.anim.status;
    actor_probe_out[7]=(unsigned)n->properties.puppetNurse.field_124;
}
