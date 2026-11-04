#include "orientation_pattern.h"
#include "texture_layout.h"
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv)
{
    if (argc != 2) return 1;
    uint8_t tiled[ORIENTATION_EDGE * ORIENTATION_EDGE * 4] = {0};
    FILE *ppm = fopen(argv[1], "wb");
    if (!ppm) return 2;
    fprintf(ppm, "P6\n32 32\n255\n");
    for (unsigned y = 0; y < ORIENTATION_EDGE; ++y)
        for (unsigned x = 0; x < ORIENTATION_EDGE; ++x) {
            uint8_t pixel[4]; orientation_pattern_pixel(x,y,pixel);
            if (fwrite(pixel,1,3,ppm) != 3) return 3;
            texture3ds_write_rgba8(tiled + texture3ds_offset(32,32,x,y),pixel);
        }
    if (fclose(ppm)) return 4;
    return fwrite(tiled,1,sizeof(tiled),stdout) == sizeof(tiled) ? 0 : 5;
}
