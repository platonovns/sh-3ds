#ifndef SH_GAME_STAGE6_INPUT_H
#define SH_GAME_STAGE6_INPUT_H
#include <stdint.h>
#include <stdio.h>
#include <math.h>
/* One-use development pad itinerary. Only normal HID bits cross to the game.
 * Positions are observed, never written; room changes still need real triggers.
 * Rows: world X, world Z, gate (wait for original transition after action).
 */
static struct { int x,z,gate; } stage6_points[48];
static unsigned stage6_points_count,stage6_leg,stage6_polls,stage6_cafe_age;
static int stage6_gate_armed;
static int game_stage6_input_load(void)
{
    FILE *f=fopen("sdmc:/3ds/silenthill/stage6_route.txt","rb");
    if(!f)return 0;
    char token[32]={0};
    int valid=fscanf(f,"%31s",token)==1 && !strcmp(token,"STAGE6_PAD_ROUTE");
    while(valid && stage6_points_count<48) {
        int x,z,gate;
        int n=fscanf(f,"%d %d %d",&x,&z,&gate);
        if(n==EOF)break;
        if(n!=3 || x< -400 || x>400 || z< -400 || z>400 || gate<0 || gate>1){valid=0;break;}
        stage6_points[stage6_points_count].x=x;
        stage6_points[stage6_points_count].z=z;
        stage6_points[stage6_points_count++].gate=gate;
    }
    fclose(f);remove("sdmc:/3ds/silenthill/stage6_route.txt");
    return valid && stage6_points_count ? 1 : -1;
}
static uint32_t game_stage6_steer(int32_t dx,int32_t dz,int32_t yaw,int run)
{
    int target=(int)(atan2f((float)dx,(float)dz)*651.898647f);
    int delta=((target-(yaw&4095)+2048)&4095)-2048;
    /* Keep moving during small corrections: low-speed emulation can step
     * across the narrow facing cone in one turn. A broad deadband instead
     * drifts into corridor walls. These are only ordinary pad combinations. */
    uint32_t forward=(1u<<6)|(run?(1u<<11):0);
    if(delta>40)return (1u<<4)|(delta<256?forward:0);
    if(delta< -40)return (1u<<5)|(delta> -256?forward:0);
    return forward;
}
static uint32_t game_stage6_input_pad(unsigned map,unsigned sys,int32_t x,int32_t z,int32_t yaw)
{
    stage6_polls++;
    if(sys==7 || sys==10)return stage6_polls%90==0 ? 2u : 0u;
    if(sys)return 0;
    if(map==1) {
        /* Free Cafe walking, short out-and-back; no pickups or exits forced. */
        unsigned age=stage6_cafe_age++%600;
        if(age<60)return 1u<<6;
        if(age>=180 && age<240)return 1u<<7;
        if(age>=300 && age<350)return 1u<<4;
        if(age>=420 && age<470)return 1u<<5;
        return 0;
    }
    /* The authored spotted-Cheryl scene moves Harry past the street approach.
     * As in the established Stage 5 itinerary, resume at the alley approach
     * instead of asking the pad driver to walk back through the redirect. */
    if(stage6_leg<2 && x< -20*4096 && z<132*4096)stage6_leg=2;
    if(stage6_leg>=stage6_points_count)return 0;
    int32_t dx=stage6_points[stage6_leg].x*4096-x,dz=stage6_points[stage6_leg].z*4096-z;
    int64_t distance=(int64_t)dx*dx+(int64_t)dz*dz;
    if(stage6_points[stage6_leg].gate) {
        if(stage6_gate_armed && distance>(int64_t)(32*4096)*(32*4096)) {
            stage6_leg++;stage6_gate_armed=0;return 0;
        }
        if(distance<(int64_t)(2*4096)*(2*4096))stage6_gate_armed=1;
        uint32_t pad=game_stage6_steer(dx,dz,yaw,0);
        if(stage6_gate_armed && stage6_polls%30==0)pad|=2u;
        return pad;
    }
    if(distance<(int64_t)3072*3072){stage6_leg++;return 0;}
    return game_stage6_steer(dx,dz,yaw,1);
}
#endif
