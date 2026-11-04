# First sewer and the Resort Area arrival overlay; integration is not yet validated.
SEWER1_MAPS := map5_s00 map5_s01
SEWER1_LDFLAGS := $(foreach map,$(SEWER1_MAPS),-Wl,-T,$(GAME_BUILD)/$(map).native.ld)
BRIDGE_OBJECTS += $(addprefix $(GAME_BUILD)/,hanged_scratcher_anim_infos.o groaner_m5s01_anim_infos.o)

$(eval $(call SCHOOL_OVERLAY,map5_s00,MAP5_S00,Chara_Creeper.c Chara_HangedScratcher.c map5_s00.c map5_s00_anim_info.c map5_s00_events_data.c map5_s00_header.c particle.c player.c unk_draw_800CB0D8.c))
$(eval $(call SCHOOL_OVERLAY,map5_s01,MAP5_S01,Chara_AirScreamer.c Chara_Groaner.c map5_s01.c map5_s01_anim_info.c map5_s01_events_data.c map5_s01_header.c particle.c player.c unk_draw_800CD20C.c unk_draw_m1s03.c))
