/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * psx_memory.h - PSX memory emulation for PC port
 *
 * Maps PSX hardcoded addresses (0x80XXXXXX) to offsets within
 * a static 3 MiB buffer (2 MiB address window + 1 MiB overflow guard).
 */
#ifndef PSX_MEMORY_H
#define PSX_MEMORY_H

#include <stdint.h>

#define PSX_RAM_WINDOW_SIZE (2u * 1024u * 1024u)
#define PSX_RAM_SIZE (3u * 1024u * 1024u)
#define PSX_SCRATCHPAD_SIZE 4096u
extern uint8_t g_PsxRam[PSX_RAM_SIZE];

/* Host scratchpad is widened from the PSX's 1 KiB to 4 KiB. */
extern uint8_t g_PsxScratchpad[PSX_SCRATCHPAD_SIZE];

/* Convert a PSX address (0x80XXXXXX) to a PC pointer into g_PsxRam */
#define PSX_ADDR(addr) ((void*)(g_PsxRam + ((addr) & 0x1FFFFF)))

void PsxMemory_Init(void);

/* Capacity check for host spans, including the existing overflow guard.
 * PSX_ADDR deliberately retains upstream's 21-bit mirror semantics. */
static inline int PsxMemory_IsSpanValid(uint32_t addr, uint32_t bytes)
{
    return bytes <= PSX_RAM_SIZE - (addr & (PSX_RAM_WINDOW_SIZE - 1u));
}

#endif /* PSX_MEMORY_H */
