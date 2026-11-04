#ifndef SH_GAME_CARD_IMAGE_H
#define SH_GAME_CARD_IMAGE_H
#include <stddef.h>
#include <stdint.h>
#define GAME_CARD_BYTES 131072u
/* Raw PS1 card image, ordinary heap only. No game-state serialization. */
int game_card_mount(const char *path);
int game_card_mount_error(void);
void game_card_unmount(void);
int game_card_ready(void);
int game_card_validate(const uint8_t *image, size_t bytes);
int game_card_format(void);
int game_card_find(const char *name);
int game_card_create(const char *name, unsigned blocks);
int game_card_entry(unsigned block, char name[21], unsigned *bytes);
int game_card_read(unsigned block, unsigned offset, void *out, unsigned bytes);
int game_card_write(unsigned block, unsigned offset, const void *in, unsigned bytes);
int game_card_erase(const char *name);
int game_card_rename(const char *from, const char *to);
unsigned game_card_heap_bytes(void);
#endif
