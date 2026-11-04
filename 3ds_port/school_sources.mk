# Original Midwich overlay closure. No forced route, flag writes, or debug entry.
SCHOOL_COMPLETION_MAPS := map1_s01 map1_s02 map1_s03 map1_s04 map1_s05 map1_s06
SCHOOL_COMPLETION_LDFLAGS := $(foreach map,$(SCHOOL_COMPLETION_MAPS),-Wl,-T,$(GAME_BUILD)/$(map).native.ld)
BRIDGE_OBJECTS += $(addprefix $(GAME_BUILD)/,cat_anim_infos.o creeper_anim_infos.o split_head_anim_infos.o locker_dead_body_anim_infos.o pc_timing.o game_school_compat.o)

define SCHOOL_OVERLAY
$(1)_SCHOOL_OBJECTS := $$(addprefix $$(GAME_BUILD)/$(1)/,$(3:.c=.o)) $$(GAME_BUILD)/$(1)/extracted.o
MAP_OBJECTS += $$(GAME_BUILD)/$(1).native.o
$$($(1)_SCHOOL_OBJECTS): $$(GAME_BUILD)/flags build/psycross/.prepared include/engine_profile.h
$$(GAME_BUILD)/$(1)/%.o: ../src/maps/$(1)/%.c
	@mkdir -p $$(dir $$@)
	$$(CC) $$(ENGINE_CFLAGS) -D$(2) -DSH_MAP_NAME=$(1) -MMD -MP -c $$< -o $$@
$$(GAME_BUILD)/$(1)/extracted.o: ../pc_port/build_gen/extracted_data/$(1)_extracted_data.c
	@mkdir -p $$(dir $$@)
	$$(CC) $$(ENGINE_CFLAGS) -D$(2) -DSH_MAP_NAME=$(1) -MMD -MP -c $$< -o $$@
$$(GAME_BUILD)/$(1).native.o: $$($(1)_SCHOOL_OBJECTS) tools/native_overlay.py ../configs/USA/maps/sym.$(1).txt
	$$(LD) -r -nostdlib $$(ARCH) $$($(1)_SCHOOL_OBJECTS) -o $$@
	python3 tools/native_overlay.py --object $$@ --map $(1)
$$(GAME_BUILD)/$(1).native.ld: $$(GAME_BUILD)/$(1).native.o
	@test -f $$@
$$(OUTPUT).elf: $$(GAME_BUILD)/$(1).native.ld
-include $$(wildcard $$(GAME_BUILD)/$(1)/*.d)
endef

$(eval $(call SCHOOL_OVERLAY,map1_s01,MAP1_S01,player.c map1_s01.c map1_s01_anim_info.c map1_s01_events_data.c map1_s01_header.c Chara_Stalker.c Chara_LarvalStalker.c Chara_Cat.c particle.c unk_draw_m1s01.c))
$(eval $(call SCHOOL_OVERLAY,map1_s02,MAP1_S02,player.c map1_s02.c map1_s02_anim_info.c map1_s02_events_data.c map1_s02_header.c Chara_Stalker.c Chara_Creeper.c particle.c particle_water.c))
$(eval $(call SCHOOL_OVERLAY,map1_s03,MAP1_S03,player.c map1_s03.c map1_s03_anim_info.c map1_s03_events_data.c map1_s03_header.c Chara_Stalker.c Chara_Creeper.c particle.c particle_water.c unk_draw_m1s03.c unk_draw_800CDCE0.c))
# S04 is the original sound-test overlay; no normal school edge enters it.
$(eval $(call SCHOOL_OVERLAY,map1_s04,MAP1_S04,player.c map1_s04.c map1_s04_anim_info.c map1_s04_events_data.c map1_s04_header.c particle.c))
$(eval $(call SCHOOL_OVERLAY,map1_s05,MAP1_S05,player.c map1_s05.c map1_s05_anim_info.c map1_s05_events_data.c map1_s05_header.c particle.c unk_draw.c unk_draw_m1s05.c))
$(eval $(call SCHOOL_OVERLAY,map1_s06,MAP1_S06,player.c map1_s06.c map1_s06_anim_info.c map1_s06_events_data.c map1_s06_header.c particle.c unk_draw_m1s05.c))
