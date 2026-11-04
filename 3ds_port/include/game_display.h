#ifndef SH_GAME_DISPLAY_H
#define SH_GAME_DISPLAY_H
#ifndef SH_3DS_CLASSIC
#define SH_3DS_CLASSIC 0
#endif
#ifdef SH_3DS_PORT
extern unsigned game3ds_classic_view;
#define GAME_DISPLAY_CLASSIC game3ds_classic_view
#else
#define GAME_DISPLAY_CLASSIC SH_3DS_CLASSIC
#endif
typedef struct {unsigned display,width,height;int x,y;} GameDisplayPlan;
static inline int game_display_world(int world_state,int feedback_world,int background_2d,int cutscene)
{
    return (world_state || feedback_world) && !(background_2d && !cutscene);
}
/* Preserve GTE scale and one raster pixel per physical pixel. */
static inline GameDisplayPlan game_display_plan(unsigned width,unsigned height,int world,int bottom)
{
    GameDisplayPlan p={bottom?1u:0u,world && !bottom && !GAME_DISPLAY_CLASSIC?400u:320u,240,0,0};
    /* Interlaced PSX 2D pages store both fields (448 rows). Present those at
     * the original display aspect; never crop either field for the bottom. */
    /* Fullscreen 2D events can keep the InGame state (e.g. paper-map pickup).
     * Interlaced pages still contain both fields, regardless of that state. */
    if(height>240) {
        p.width=width;
        /* The original Status uses doubled field coordinates, not extra LCD
         * detail. Fold fields before rasterization, retaining its 224-line
         * authored canvas inside the native 320x240 lower screen. */
        if(bottom) {p.height=240;p.y=(240-(int)height/2)/2;}
        else p.height=height;
        return p;
    }
    p.x=((int)p.width-(int)width)/2;p.y=(240-(int)height)/2;return p;
}
#endif
