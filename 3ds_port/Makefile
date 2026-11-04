# Standalone devkitPro diagnostic application + explicit ARM11 engine closure.
.SUFFIXES:
.DEFAULT_GOAL := all

ifeq ($(strip $(DEVKITARM)),)
$(error Set DEVKITPRO and DEVKITARM; use a devkitPro shell with 3ds-dev installed)
endif

TOPDIR ?= $(CURDIR)
include $(DEVKITARM)/3ds_rules
include $(TOPDIR)/engine_sources.mk

TARGET := silenthill_3ds
BUILD := build
ARCH := -march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft
CFLAGS := -g -O2 -std=gnu11 -Wall -Wextra -Werror \
          -mword-relocations -ffunction-sections -fdata-sections \
          $(ARCH) $(INCLUDE) -D__3DS__
LDFLAGS = -specs=3dsx.specs -g $(ARCH) \
          -Wl,--gc-sections,--no-enum-size-warning,-Map,$(OUTPUT).map
# Game uses 32-bit enums, SDK uses short enums. The engine_gate.h boundary
# contains only fixed-width integers; no enum or game struct crosses into SDK.
LIBS := -lcitro3d -lctru -lm
APP_TITLE := Silent Hill 3DS
APP_DESCRIPTION := Stage 4.1 original FS post-load gate
APP_AUTHOR := Silent Hill 3DS contributors

ifneq ($(BUILD),$(notdir $(CURDIR)))

export OUTPUT := $(CURDIR)/$(TARGET)
export TOPDIR := $(CURDIR)
export VPATH := $(CURDIR)/source $(CURDIR)/shaders $(ENGINE_DIRS)
export DEPSDIR := $(CURDIR)/$(BUILD)
# Keep SDK and decomp types in separate translation units.
export OFILES := main.o render_3ds.o render_tests.o engine_gate.o psx_disc.o sh_disc.o psyq_file.o disc_gate.o psx_vram.o psx_tim.o tim_gate.o tim_selftest.o stage4_report.o foundation.shbin.o $(ENGINE_OBJECTS)
export LD := $(CC)
export INCLUDE := -I$(TOPDIR)/include -I$(CTRULIB)/include -I$(DEPSDIR)
export LIBPATHS := -L$(CTRULIB)/lib
export _3DSXFLAGS := --smdh=$(OUTPUT).smdh

.PHONY: all clean map-audit file-contract
all: $(BUILD)/psycross/.prepared build-identity
	@mkdir -p $(BUILD)
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(TOPDIR)/Makefile

.PHONY: build-identity
build-identity:
	@python3 tools/build_identity.py

$(BUILD)/psycross/.prepared: patches/psycross-arm11.patch patches/psycross-inputs.json tools/prepare_psycross.py \
                           $(addprefix ../pc_port/PsyCross/,$(PSYCROSS_INPUTS))
	python3 tools/prepare_psycross.py

map-audit: all
	python3 tools/audit_map.py $(CC) $(ENGINE_CFLAGS)

file-contract: all
	python3 tools/check_file_contract.py $(CC) $(ENGINE_CFLAGS)

stage4-audit: all
	python3 tools/audit_stage4.py $(CC) $(ENGINE_CFLAGS)

title-native-audit:
	python3 tools/audit_title_native.py $(CC) $(ENGINE_CFLAGS)

clean:
	@rm -f $(BUILD)/*.o $(BUILD)/*.d $(BUILD)/*.lst $(BUILD)/*.su \
	        $(BUILD)/*.shbin $(BUILD)/*_shbin.h \
	        $(TARGET).elf $(TARGET).3dsx $(TARGET).smdh $(TARGET).map
	@rm -rf $(BUILD)/psycross $(BUILD)/map0_s00-audit $(BUILD)/file-contract
	@rmdir $(BUILD) 2>/dev/null || true

else

.PHONY: all
all: $(OUTPUT).3dsx

$(OUTPUT).3dsx: $(OUTPUT).elf $(OUTPUT).smdh
$(OUTPUT).elf: $(OFILES)
$(OFILES): $(TOPDIR)/Makefile
$(ENGINE_OBJECTS) engine_gate.o: $(TOPDIR)/engine_sources.mk $(TOPDIR)/include/engine_profile.h
$(ENGINE_OBJECTS) engine_gate.o: CFLAGS = $(ENGINE_CFLAGS)
PsyX_GTE.o: CXXFLAGS = $(ENGINE_CXXFLAGS)
psx_disc.o sh_disc.o psyq_file.o disc_gate.o psx_vram.o psx_tim.o tim_gate.o tim_selftest.o render_3ds.o: CFLAGS += -mno-unaligned-access -fstack-usage
fsqueue_1.o fsqueue_2.o fsqueue_3.o fileinfo.o stage4_fs.o: CFLAGS = $(ENGINE_CFLAGS) -fstack-usage
render_3ds.o: foundation_shbin.h
main.o stage4_report.o: build_identity.h

.PRECIOUS: %.shbin
%.shbin.o %_shbin.h &: %.shbin
	$(bin2o)

-include $(DEPSDIR)/*.d

endif
