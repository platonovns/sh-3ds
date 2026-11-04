# Source provenance

SH-3DS builds on the `pc-port` branch of SlickAmogus/silent-hill-decomp,
the upstream Silent Hill decompilation, and PsyCross. Those projects contain
separately authored code, reconstructed game logic, technical constants and
game-related data. See [COPYRIGHT.md](../COPYRIGHT.md), the root license,
submodule licenses and individual source notices for the terms and attributions
stated by their respective authors. The port does not grant rights to the
original game or purport to resolve the status of inherited material.

The repository includes data that is described in its source comments as
extracted from or reconstructed using original game files. For example,
`pc_port/build_gen/extracted_data/` contains map-overlay declarations inherited
from pc-port; some files are manually maintained. The 3DS build selects 39 of
the 43 map-data files. Several character animation and collision tables are
reconstructed or adapted for native pointers, and the port extends the
`g_AsRodataPsxRaw` collision data by 12 bytes identified in its source comment
as coming from the `MAP0_S01` overlay. Those data remain in the source tree.

The inherited PC-port tree also contains two title-screen TIM files and
language/font material with their own documented origins; they are not inputs
to the ordinary 3DS build. Presence in an upstream repository is not a
determination of redistribution rights. Conversely, matching reconstructed
values do not by themselves establish that a C table was copied as binary.

The 3DS application reads game resources from a user-provided compatible disc
image at runtime. The build compiles source data already in the repository and
does not require a game image. The custom CIA presentation inputs in
`3ds_port/packaging/` were created for SH-3DS and approved for inclusion by the
project author; they are separate from original game assets.
