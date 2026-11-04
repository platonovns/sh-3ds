# Old Silent Hill church/drawbridge -> Central Silent Hill arrival.
# Full Central streets + optional police, without extending into hospital.
POST_SCHOOL_MAPS := map2_s01 map2_s02 map2_s04
POST_SCHOOL_LDFLAGS := $(foreach map,$(POST_SCHOOL_MAPS),-Wl,-T,$(GAME_BUILD)/$(map).native.ld)
BRIDGE_OBJECTS += $(addprefix $(GAME_BUILD)/,dahlia_anim_infos.o romper_anim_infos.o)

# Reuse the School checkpoint's ordinary compiled-overlay rule, including
# private symbol namespace, original DATA aliases and dependency tracking.
$(eval $(call SCHOOL_OVERLAY,map2_s01,MAP2_S01,player.c map2_s01_2.c map2_s01_anim_info.c map2_s01_events_data.c map2_s01_header.c Chara_Dahlia.c particle.c))
$(eval $(call SCHOOL_OVERLAY,map2_s02,MAP2_S02,player.c map2_s02.c map2_s02_anim_info.c map2_s02_events_data.c map2_s02_header.c Chara_AirScreamer.c Chara_Groaner.c particle.c))
$(eval $(call SCHOOL_OVERLAY,map2_s04,MAP2_S04,player.c map2_s04.c map2_s04_anim_info.c map2_s04_events_data.c map2_s04_header.c particle.c))
