# Block 5 resident overlays.
BRIDGE_OBJECTS += $(GAME_BUILD)/resort_anim_infos.o $(GAME_BUILD)/stalker_m5s02_anim_infos.o
BRIDGE_OBJECTS += $(addprefix $(GAME_BUILD)/,monster_cybil_anim_infos.o parasite_anim_infos.o flauros_anim_infos.o larval_stalker_anim_infos.o)
RESORT_MAPS := map5_s02 map5_s03 map6_s00 map6_s01 map6_s02 map6_s03 map6_s04 map7_s00 map7_s01 map7_s02 map7_s03
RESORT_LDFLAGS := $(foreach map,$(RESORT_MAPS),-Wl,-T,$(GAME_BUILD)/$(map).native.ld)
$(eval $(call SCHOOL_OVERLAY,map5_s02,MAP5_S02,Chara_Kaufmann.c characters.c map5_s02_2.c map5_s02_anim_info.c map5_s02_events_data.c map5_s02_header.c particle.c))
$(eval $(call SCHOOL_OVERLAY,map5_s03,MAP5_S03,Chara_Kaufmann.c map5_s03_2.c map5_s03_anim_info.c map5_s03_events_data.c map5_s03_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map6_s00,MAP6_S00,Chara_AirScreamer.c Chara_Groaner.c map6_s00.c map6_s00_anim_info.c map6_s00_events_data.c map6_s00_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map6_s01,MAP6_S01,Chara_Cybil.c Chara_Dahlia.c map6_s01_2.c map6_s01_anim_info.c map6_s01_events_data.c map6_s01_header.c particle.c player.c unk_draw_m1s03.c))

$(eval $(call SCHOOL_OVERLAY,map6_s02,MAP6_S02,Chara_Alessa.c map6_s02_2.c map6_s02_anim_info.c map6_s02_events_data.c map6_s02_header.c particle.c player.c unk_draw_m1s03.c))
$(eval $(call SCHOOL_OVERLAY,map6_s03,MAP6_S03,Chara_HangedScratcher.c Chara_Stalker.c map6_s03.c map6_s03_anim_info.c map6_s03_events_data.c map6_s03_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map6_s04,MAP6_S04,Chara_AlessaDahlia.c Chara_LarvalStalker.c Chara_MonsterCybil.c Chara_Stalker.c map6_s04_2.c map6_s04_anim_info.c map6_s04_events_data.c map6_s04_header.c particle.c player.c unk_draw_m1s01.c))
$(eval $(call SCHOOL_OVERLAY,map7_s00,MAP7_S00,Chara_Lisa.c map7_s00_2.c map7_s00_anim_info.c map7_s00_events_data.c map7_s00_header.c particle.c player.c))

$(eval $(call SCHOOL_OVERLAY,map7_s01,MAP7_S01,Chara_BloodyLisa.c Chara_GhostChildAlessa.c Chara_Lisa.c characters.c map7_s01_2.c map7_s01_anim_info.c map7_s01_events_data.c map7_s01_header.c particle_glass.c particle.c))
$(eval $(call SCHOOL_OVERLAY,map7_s02,MAP7_S02,Chara_Bloodsucker.c Chara_BloodyLisa.c Chara_Dahlia.c Chara_GhostChildAlessa.c Chara_GhostDoctor.c Chara_Kaufmann.c Chara_Lisa.c Chara_Stalker.c map7_s02_2.c map7_s02_anim_info.c map7_s02_events_data.c map7_s02_header.c particle.c player.c))
$(eval $(call SCHOOL_OVERLAY,map7_s03,MAP7_S03,Chara_Alessa.c Chara_BloodyIncubator.c Chara_BloodyLisa.c Chara_Cybil.c Chara_Dahlia.c Chara_Incubator.c Chara_Incubus.c Chara_Kaufmann.c Chara_LittleIncubus.c Chara_Unknown23.c chara_util.c map7_s03_2.c map7_s03_3.c map7_s03_anim_info.c map7_s03_events_data.c map7_s03_header.c particle.c player.c))
$(GAME_BUILD)/map7_s03/map7_s03_2.o $(GAME_BUILD)/map7_s03/map7_s03_3.o: ENGINE_CFLAGS += -Wno-error=incompatible-pointer-types
