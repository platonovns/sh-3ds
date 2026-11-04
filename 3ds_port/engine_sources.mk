# Explicit Stage 1B closure. No recursive source discovery or desktop libraries.
# Each game/PsyCross object is linked directly; verify_build.py audits it pre-GC.
ENGINE_OBJECTS := psx_memory.o rng.o memmove32.o fsmem.o \
                  PsyX_GTE.o libgte.o inline_c.o fsqueue_1.o fsqueue_2.o fsqueue_3.o fileinfo.o stage4_fs.o
ENGINE_DIRS := $(TOPDIR)/../pc_port/src $(TOPDIR)/../src/main \
               $(TOPDIR)/build/psycross/src/gte $(TOPDIR)/build/psycross/src/psx $(TOPDIR)/source
PSYCROSS_INPUTS := src/gte/PsyX_GTE.cpp src/gte/PsyX_GTE.h src/gte/rcossin_tbl.h \
    src/gte/ratan_tbl.h src/gte/sqrt_tbl.h src/psx/libgte.c src/psx/inline_c.c include/psx/inline_c.h include/psx/libgpu.h
ENGINE_INCLUDE := -I$(TOPDIR)/include \
    -I$(TOPDIR)/build/psycross/include/psx -I$(TOPDIR)/build/psycross/include \
    -I$(TOPDIR)/../pc_port/include -I$(TOPDIR)/../pc_port/include/psyq_compat \
    -I$(TOPDIR)/../include -I$(TOPDIR)/../include/decomp \
    -I$(TOPDIR)/../pc_port/PsyCross/include/psx -I$(TOPDIR)/../pc_port/PsyCross/include
ENGINE_FLAGS = -g -O2 -Wall -Wextra -Werror=implicit-function-declaration \
    -Werror=incompatible-pointer-types -fno-strict-aliasing -fwrapv -fsigned-char -fno-short-enums \
    -mno-unaligned-access -mword-relocations -ffunction-sections -fdata-sections \
    $(ARCH) $(ENGINE_INCLUDE) -include $(TOPDIR)/include/engine_profile.h
ENGINE_CFLAGS = $(ENGINE_FLAGS) -std=gnu11
ENGINE_CXXFLAGS = $(filter-out -Werror=implicit-function-declaration -Werror=incompatible-pointer-types,$(ENGINE_FLAGS)) \
    -std=gnu++17 -fno-exceptions -fno-rtti
