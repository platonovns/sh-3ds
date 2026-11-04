/* ARM fixture: use the real character transparency and VRAM transfer code. */
#include "bodyprog/bodyprog.h"
#include <string.h>

static s_CharaModel model;

void lighthouse_clut_probe_setup(void)
{
    memset(&model, 0, sizeof(model));
    model.texture.clutX = 320;
    model.texture.clutY = 480;
    g_WorldGfxWork.registeredCharaModels[Chara_Alessa] = &model;
}
