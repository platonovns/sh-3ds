#include "render_tests.h"
#include "render_3ds.h"
#include "orientation_pattern.h"

#define TEXTURE_EDGE 32u

static Render3dsTexture *checker;
static Render3dsTexture *orientation;

static bool orientation_read_row(void *context, unsigned y, uint8_t *rgba, unsigned width)
{
    (void)context;
    if (width != ORIENTATION_EDGE || y >= ORIENTATION_EDGE) return false;
    for (unsigned x = 0; x < width; ++x) orientation_pattern_pixel(x,y,rgba+x*4);
    return true;
}
bool render_orientation_init(void)
{
    if (!orientation)
        orientation = render3ds_texture_create_rows(ORIENTATION_EDGE,ORIENTATION_EDGE,
                                                    orientation_read_row,NULL,NULL,NULL);
    return orientation != NULL;
}
bool render_orientation_ready(void) { return orientation != NULL; }
bool render_orientation_draw(void)
{
    if (!render3ds_begin_frame()) return false;
    bool ok = orientation != NULL;
    if (orientation)
        for (unsigned flips = 0; flips < 4; ++flips)
            ok = render3ds_draw_texture_region(orientation,48+(flips%2)*192,12+(flips/2)*120,96,96,
                                               0,0,ORIENTATION_EDGE,ORIENTATION_EDGE,flips,false) && ok;
    render3ds_end_frame();
    return ok;
}

bool render_tests_init(void)
{
    /* Asymmetric markers expose channel swaps, vertical flips and bad tiling. */
    unsigned char pixels[TEXTURE_EDGE * TEXTURE_EDGE * 4];
    for (unsigned y = 0; y < TEXTURE_EDGE; ++y) {
        for (unsigned x = 0; x < TEXTURE_EDGE; ++x) {
            unsigned char *p = pixels + (y * TEXTURE_EDGE + x) * 4;
            const unsigned char level = ((x / 4 + y / 4) & 1) ? 255 : 48;
            p[0] = p[1] = p[2] = level;
            p[3] = 255;
            if (y < 4) { p[0] = 255; p[1] = p[2] = 0; }
            if (x < 4) { p[0] = 0; p[1] = 255; p[2] = 0; }
            if (x >= 28 && y >= 28) { p[0] = p[1] = 0; p[2] = 255; }
        }
    }
    checker = render3ds_texture_create_rgba8(TEXTURE_EDGE, TEXTURE_EDGE, pixels, TEXTURE_EDGE * 4);
    render_orientation_init();
    return checker != NULL;
}

static Render3dsVertex vertex(float x, float y, float u, float v,
                              float r, float g, float b, float a)
{
    return (Render3dsVertex){x, y, 0, u, v, r, g, b, a};
}

static bool quad(float x, float y, float w, float h, Render3dsTexture *texture,
                 float r, float g, float b, float a, bool blend)
{
    const Render3dsVertex tl = vertex(x, y, 0, 1, r, g, b, a);
    const Render3dsVertex tr = vertex(x + w, y, 1, 1, r, g, b, a);
    const Render3dsVertex bl = vertex(x, y + h, 0, 0, r, g, b, a);
    const Render3dsVertex br = vertex(x + w, y + h, 1, 0, r, g, b, a);
    const Render3dsVertex triangles[] = {tl, bl, tr, tr, bl, br};
    return render3ds_draw_triangles(triangles, 6, texture, blend);
}

bool render_tests_draw(unsigned frame)
{
    if (!render3ds_begin_frame())
        return false;
    bool ok = true;
    /* Cells A/B/C across the top, D/E/F across the bottom. */
    const Render3dsVertex triangle[] = {
        vertex(16, 104, 0, 0, 1, 0, 0, 1),
        vertex(64, 16, 0, 0, 0, 1, 0, 1),
        vertex(112, 104, 0, 0, 0, 0, 1, 1)
    };
    ok &= render3ds_draw_triangles(triangle, 3, NULL, false);
    ok &= quad(144, 16, 96, 88, checker, 1, 1, 1, 1, false);

    /* Identical Z, depth disabled: later green/blue cover earlier red. */
    ok &= quad(272, 16, 80, 64, NULL, 1, 0.15f, 0.15f, 1, false);
    ok &= quad(288, 32, 80, 64, NULL, 0.15f, 1, 0.15f, 1, false);
    ok &= quad(304, 48, 80, 64, NULL, 0.15f, 0.15f, 1, 1, false);

    const Render3dsVertex modulation[] = {
        vertex(16, 136, 0, 1, 1, 1, 1, 1),
        vertex(16, 224, 0, 0, 0.2f, 0.2f, 1, 1),
        vertex(112, 136, 1, 1, 1, 0.2f, 0.2f, 1),
        vertex(112, 136, 1, 1, 1, 0.2f, 0.2f, 1),
        vertex(16, 224, 0, 0, 0.2f, 0.2f, 1, 1),
        vertex(112, 224, 1, 0, 0.2f, 1, 0.2f, 1)
    };
    ok &= render3ds_draw_triangles(modulation, 6, checker, false);
    ok &= quad(144, 136, 96, 88, checker, 1, 1, 1, 1, false);
    ok &= quad(160, 152, 64, 56, NULL, 1, 0, 1, 0.5f, true);

    /* Gray marks the full primitive; yellow must remain inside the white
     * frame. Magenta at the right is submitted AFTER resetting the scissor. */
    ok &= quad(272, 136, 112, 88, NULL, 0.18f, 0.18f, 0.18f, 1, false);
    ok &= quad(286, 150, 68, 60, NULL, 1, 1, 1, 1, false);
    ok &= render3ds_set_scissor(288, 152, 352, 208);
    ok &= quad(272, 136, 112, 88, NULL, 1, 0.8f, 0, 1, false);
    ok &= render3ds_set_scissor(0, 0, 400, 240);
    ok &= quad(368, 152, 16, 56, NULL, 1, 0, 1, 1, false);
    /* A one-second heartbeat also catches a stalled frame after resume. */
    ok &= quad(2, 118, 8, 4, NULL, (frame / 30) & 1, 1, 0, 1, false);
    render3ds_end_frame();
    return ok;
}

void render_tests_shutdown(void)
{
    render3ds_texture_destroy(orientation);
    orientation = NULL;
    render3ds_texture_destroy(checker);
    checker = NULL;
}
