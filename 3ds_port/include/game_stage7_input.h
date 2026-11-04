#ifndef SH_GAME_STAGE7_INPUT_H
#define SH_GAME_STAGE7_INPUT_H
/* Explicit opt-in diagnostic, independent of the development map shortcut.
 * Rows contain raw HID bits and real vblank duration. Never writes game/save/
 * camera/position state. No live-file polling in ordinary physical mode. */
static int stage7_input_enabled;
static int stage7_stop_route;
extern void Game3ds_ClassicView(unsigned classic);
extern void Game3ds_FpsLimit(unsigned fps);
static struct {unsigned keys,ticks;} stage7_pad_rows[32];
static unsigned stage7_pad_count,stage7_pad_row,stage7_pad_start,stage7_pad_poll;
static int stage7_move_active,stage7_move_x,stage7_move_z,stage7_move_yaw;
static unsigned stage7_move_start,stage7_move_timeout;
static uint32_t game_stage7_input_pad(int32_t x,int32_t z,int32_t yaw,unsigned state,unsigned sys)
{
    if(!stage7_input_enabled)return 0;
    unsigned now=game3ds_vblank_clock();
    if(stage7_move_active) {
        if(now-stage7_move_start>stage7_move_timeout){stage7_move_active=0;return 0;}
        if(state!=11 || sys!=0)return 0;
        int dx=stage7_move_x-x,dz=stage7_move_z-z;
        if((int64_t)dx*dx+(int64_t)dz*dz>(int64_t)1230*1230)return game_stage6_steer(dx,dz,yaw,0);
        int delta=((stage7_move_yaw-(yaw&4095)+2048)&4095)-2048;
        if(delta>128)return 1u<<4;
        if(delta< -128)return 1u<<5;
        stage7_move_active=0;return 0;
    }
    if(stage7_pad_row>=stage7_pad_count) {
        if(++stage7_pad_poll%30)return 0;
        FILE *f=fopen("sdmc:/3ds/silenthill/stage7_pad.txt","rb");if(!f)return 0;
        char command[16]={0};
        int has_command=fscanf(f,"%15s",command)==1;
        if(has_command && !strcmp(command,"STOP_ROUTE")) {
            fclose(f);remove("sdmc:/3ds/silenthill/stage7_pad.txt");
            stage7_stop_route=1;return 0;
        }
        if(has_command && !strcmp(command,"VIEW")) {
            unsigned classic;int valid=fscanf(f,"%u",&classic)==1 && classic<=1;
            fclose(f);remove("sdmc:/3ds/silenthill/stage7_pad.txt");
            if(!valid)game3ds_halt(456,"Stage 7 aspect comparison mode",0);
            Game3ds_ClassicView(classic);return 0;
        }
        if(has_command && !strcmp(command,"FPS")) {
            unsigned fps;int valid=fscanf(f,"%u",&fps)==1 && (fps==30 || fps==60);
            fclose(f);remove("sdmc:/3ds/silenthill/stage7_pad.txt");
            if(!valid)game3ds_halt(456,"Stage 8 FPS mode",0);
            Game3ds_FpsLimit(fps);return 0;
        }
        if(has_command && !strcmp(command,"MOVE")) {
            int valid=fscanf(f,"%d %d %d %u",&stage7_move_x,&stage7_move_z,&stage7_move_yaw,&stage7_move_timeout)==4 &&
                stage7_move_x>=-400*4096 && stage7_move_x<=400*4096 && stage7_move_z>=-400*4096 && stage7_move_z<=400*4096 &&
                stage7_move_yaw>=0 && stage7_move_yaw<4096 && stage7_move_timeout>0 && stage7_move_timeout<=7200;
            fclose(f);remove("sdmc:/3ds/silenthill/stage7_pad.txt");
            if(!valid)game3ds_halt(456,"Stage 7 move itinerary bounds",0);
            stage7_move_start=now;stage7_move_active=1;return 0;
        }
        rewind(f);
        stage7_pad_row=stage7_pad_count=0;
        unsigned keys,ticks;int n;
        while((n=fscanf(f,"%u %u",&keys,&ticks))==2) {
            if(stage7_pad_count==32 || !ticks || ticks>600 || (keys&~0xcfff)) {
                fclose(f);game3ds_halt(456,"Stage 7 pad itinerary bounds",stage7_pad_count);
            }
            stage7_pad_rows[stage7_pad_count].keys=keys;stage7_pad_rows[stage7_pad_count++].ticks=ticks;
        }
        fclose(f);remove("sdmc:/3ds/silenthill/stage7_pad.txt");
        if(n!=EOF || !stage7_pad_count)game3ds_halt(456,"Stage 7 pad itinerary syntax",0);
        stage7_pad_start=now;
    }
    if(now-stage7_pad_start>=stage7_pad_rows[stage7_pad_row].ticks) {
        stage7_pad_row++;stage7_pad_start=now;
    }
    return stage7_pad_row<stage7_pad_count?stage7_pad_rows[stage7_pad_row].keys:0;
}
#endif
