# Original Block 3 overlays. This does not imply that integration is validated.
BLOCK3_MAPS := map4_s01 map4_s02 map4_s03 map4_s04 map4_s05
BLOCK3_LDFLAGS := $(foreach map,$(BLOCK3_MAPS),-Wl,-T,$(GAME_BUILD)/$(map).native.ld)
BRIDGE_OBJECTS += $(addprefix $(GAME_BUILD)/,twinfeeler_anim_infos.o floatstinger_anim_infos.o groaner_m4s02_anim_infos.o)

$(eval $(call SCHOOL_OVERLAY,map4_s01,MAP4_S01,Chara_Cybil.c map4_s01_2.c map4_s01_anim_info.c map4_s01_events_data.c map4_s01_header.c particle.c player.c unk_draw.c))
$(eval $(call SCHOOL_OVERLAY,map4_s02,MAP4_S02,Chara_AirScreamer.c Chara_Groaner.c Chara_Romper.c map4_s02.c map4_s02_anim_info.c map4_s02_events_data.c map4_s02_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map4_s03,MAP4_S03,map4_s03.c map4_s03_anim_info.c map4_s03_events_data.c map4_s03_header.c particle_acid.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map4_s04,MAP4_S04,Chara_Lisa.c map4_s04_2.c map4_s04_anim_info.c map4_s04_events_data.c map4_s04_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map4_s05,MAP4_S05,map4_s05.c map4_s05_anim_info.c map4_s05_events_data.c map4_s05_header.c particle_acid.c particle.c player.c unk_draw_m1s03.c))
