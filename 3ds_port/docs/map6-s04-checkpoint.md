# MAP6_S04 playtest boundary

The original MAP6_S03 exit enters MAP6_S04. Its event table retains the park,
carousel, Cybil battle, both Cybil outcomes, Alessa/Dahlia/Flauros sequence,
and the original flag-451 exit targeting MAP7_S00. MAP7 is not resident in this
candidate; the boundary ends at its transition.

Unknown Liquid use follows the original inventory distance/state check and
sets flag 448. The rescue scene sets 449 and 450; the death scene sets 447
and 450. The retail 636-byte save layout is unchanged. The S04-specific
Stalker and Dahlia animation tables are relocated from the original overlay;
native Cybil, parasite, Flauros and larval animation tables are initialized on
map binding. The Alessa and larval shared tables were checked against disc.

Hardware validation required: enter from the second sewer; traverse the park;
play the carousel and battle; exercise the applicable Unknown Liquid/rescue
or death path; confirm the Alessa/Dahlia scene, flags, audio, effects, saves,
controls and transition to the MAP7 boundary. This checkpoint is not a full
hardware playthrough or MAP7 integration.
