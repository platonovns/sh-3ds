# Original complete Alchemilla overlay closure; chapter stops before MAP4.
ALCHEMILLA_MAPS := map3_s00 map3_s01 map3_s02 map3_s03 map3_s04 map3_s05 map3_s06
ALCHEMILLA_LDFLAGS := $(foreach map,$(ALCHEMILLA_MAPS),-Wl,-T,$(GAME_BUILD)/$(map).native.ld)
BRIDGE_OBJECTS += $(addprefix $(GAME_BUILD)/,kaufmann_anim_infos.o lisa_anim_infos.o alessa_anim_infos.o bloodsucker_anim_infos.o puppet_nurse_data.o dahlia_m3s06_anim_infos.o)

$(eval $(call SCHOOL_OVERLAY,map3_s00,MAP3_S00,Chara_Kaufmann.c map3_s00_2.c map3_s00_anim_info.c map3_s00_events_data.c map3_s00_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map3_s01,MAP3_S01,Chara_Creeper.c map3_s01_anim_info.c map3_s01_events_data.c map3_s01_header.c map3_s01.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map3_s02,MAP3_S02,Chara_Alessa.c Chara_Creeper.c map3_s02_2.c map3_s02_anim_info.c map3_s02_events_data.c map3_s02_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map3_s03,MAP3_S03,map3_s03_anim_info.c map3_s03_events_data.c map3_s03_header.c map3_s03.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map3_s04,MAP3_S04,Chara_Lisa.c Chara_PuppetNurse.c map3_s04_2.c map3_s04_anim_info.c map3_s04_events_data.c map3_s04_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map3_s05,MAP3_S05,map3_s05_anim_info.c map3_s05_events_data.c map3_s05_header.c map3_s05.c particle.c unk_draw.c))
$(eval $(call SCHOOL_OVERLAY,map3_s06,MAP3_S06,Chara_Dahlia.c map3_s06_2.c map3_s06_anim_info.c map3_s06_events_data.c map3_s06_header.c particle.c player.c))

