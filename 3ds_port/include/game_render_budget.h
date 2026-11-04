#ifndef SH_GAME_RENDER_BUDGET_H
#define SH_GAME_RENDER_BUDGET_H
/* Cafe's two-character scene exceeds the Stage 5 2048-primitive bound.
 * Keep finite vertex/command storage and fail before crossing either bound. */
#define GAME_DRAW_LIMIT 3072u
#define GAME_VERTEX_LIMIT (GAME_DRAW_LIMIT * 6u)
#define GAME_COMMAND_BYTES (1024u * 1024u)
/* Native OT_TAG is eight bytes, rather than the retail four-byte tag. The
 * original 128 KiB PSX scratch partitions do not bound native packet bytes. */
#define GAME_PACKET_BYTES (256u * 1024u)
#define GAME_PACKET_GUARD_BYTES 2048u
#endif
