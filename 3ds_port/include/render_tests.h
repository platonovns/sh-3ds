#ifndef SH_RENDER_TESTS_H
#define SH_RENDER_TESTS_H

#include <stdbool.h>

bool render_tests_init(void);
bool render_tests_draw(unsigned frame);
void render_tests_shutdown(void);
bool render_orientation_init(void);
bool render_orientation_ready(void);
bool render_orientation_draw(void);

#endif
