#include "texture_layout.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static void check_image(unsigned width, unsigned height)
{
    const size_t bytes = (size_t)width * height * 4;
    uint8_t *image = malloc(bytes);
    assert(image);
    for (unsigned y = 0; y < height; ++y) {
        for (unsigned x = 0; x < width; ++x) {
            const uint8_t rgba[4] = {x & 255, y & 255, (x / 256) | ((y / 256) << 2), 137};
            const size_t offset = texture3ds_offset(width, height, x, y);
            assert(offset <= bytes - 4 && offset % 4 == 0);
            texture3ds_write_rgba8(image + offset, rgba);
        }
    }
    /* Decode in GPU address order, independently recovering coordinates from
     * tile and Morton bits. Any alias, gap, flip or channel error is visible. */
    for (size_t texel = 0; texel < bytes / 4; ++texel) {
        const unsigned tile = texel / 64;
        const unsigned m = texel % 64;
        const unsigned x = (tile % (width / 8)) * 8 +
            (m & 1) + ((m >> 1) & 2) + ((m >> 2) & 4);
        const unsigned gpu_y = (tile / (width / 8)) * 8 +
            ((m >> 1) & 1) + ((m >> 2) & 2) + ((m >> 3) & 4);
        const unsigned y = gpu_y;
        const uint8_t *p = image + texel * 4;
        assert(p[0] == 137 && p[1] == ((x / 256) | ((y / 256) << 2)));
        assert(p[2] == (y & 255) && p[3] == (x & 255));
    }
    free(image);
}

int main(void)
{
    assert(texture3ds_offset(8, 8, 0, 0) == 0);
    assert(texture3ds_offset(8, 8, 1, 0) == 4);
    assert(texture3ds_offset(8, 8, 0, 1) == 8);
    assert(texture3ds_offset(8, 8, 7, 7) == 252);
    for (unsigned w = 8; w <= 1024; w *= 2)
        for (unsigned h = 8; h <= 1024; h *= 2)
            check_image(w, h);
    puts("PASS: 64 texture shapes, full decode, RGBA channels, orientation and bounds");
    return 0;
}
