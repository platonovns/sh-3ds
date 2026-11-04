#include "game_card_image.h"
#include "game_display.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc,char **argv)
{
    assert(argc==3);
    if(!strcmp(argv[1],"refuse")) {assert(!game_card_mount(argv[2]));return 0;}
    assert(game_card_mount(argv[2]));
    assert(game_card_heap_bytes()==GAME_CARD_BYTES);
    if(!strcmp(argv[1],"create")) {
        assert(!game_card_find("BASLUS-00707SILENT00"));
        int block=game_card_create("BASLUS-00707SILENT00",1);assert(block==1);
        assert(!game_card_create("BASLUS-00707SILENT00",1));
        unsigned char data[640];for(unsigned i=0;i<sizeof(data);i++)data[i]=(i*37+11)&255;
        assert(game_card_write(block,0x380,data,sizeof(data)));
        assert(!game_card_write(block,8191,data,2));
        assert(!game_card_create("../escape",1));
        assert(!game_card_create("TOO_MANY_BLOCKS",16));
        char name[21];unsigned size;assert(game_card_entry(block,name,&size));
        assert(!strcmp(name,"BASLUS-00707SILENT00") && size==8192);
        for(unsigned i=1;i<15;i++) {char n[21];snprintf(n,sizeof(n),"FILE%02u",i);assert(game_card_create(n,1));}
        assert(!game_card_create("FULL",1));
        assert(game_card_erase("FILE01"));assert(game_card_create("REUSED",1)==2);
        assert(game_card_rename("REUSED","RENAMED"));assert(game_card_find("RENAMED")==2);
        assert(!game_card_rename("RENAMED","FILE02"));
    } else if(!strcmp(argv[1],"read")) {
        unsigned char data[640];int b=game_card_find("BASLUS-00707SILENT00");assert(b==1);
        assert(game_card_read(b,0x380,data,sizeof(data)));
        for(unsigned i=0;i<sizeof(data);i++)assert(data[i]==((i*37+11)&255));
        assert(!game_card_read(b,8192,data,1));
        assert(game_card_find("RENAMED")==2);
    } else if(!strcmp(argv[1],"write-fails")) {
        unsigned char value=99,old;assert(game_card_read(1,0x380,&old,1));
        assert(!game_card_write(1,0x380,&value,1));
        assert(game_card_read(1,0x380,&value,1) && value==old);
    } else assert(0);
    GameDisplayPlan classic=game_display_plan(320,224,0,0),wide=game_display_plan(320,224,1,0),bottom=game_display_plan(320,224,0,1);
    assert(classic.width==320 && classic.x==0 && classic.y==8);
    assert(wide.width==400 && wide.x==40 && wide.y==8 && !wide.display);
    assert(bottom.width==320 && bottom.height==240 && bottom.display && bottom.x==0);
    game_card_unmount();assert(game_card_heap_bytes()==0);
    puts("PASS");return 0;
}
