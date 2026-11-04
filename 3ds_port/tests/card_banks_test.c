#include "game_card_image.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(int argc,char **argv)
{
    assert(argc==3);
    const char *name="BASLUS-00707SILENT00";
    unsigned char one=17,two=89,got=0;
    assert(game_card_mount(argv[1]));
    int block=game_card_create(name,1);assert(block);
    assert(game_card_write(block,0x380,&one,1));
    assert(game_card_mount(argv[2]));assert(!game_card_find(name));
    block=game_card_create(name,1);assert(block);
    assert(game_card_write(block,0x380,&two,1));
    assert(game_card_mount(argv[1]));block=game_card_find(name);assert(block);
    assert(game_card_read(block,0x380,&got,1) && got==one);
    assert(game_card_mount(argv[2]));block=game_card_find(name);assert(block);
    assert(game_card_read(block,0x380,&got,1) && got==two);
    game_card_unmount();puts("PASS: separate card stores survive remount");return 0;
}
