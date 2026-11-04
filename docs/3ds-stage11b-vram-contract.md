# Stage 11B — canonical VRAM и framebuffer: контракт до смены authority

28.10.2026. Статический аудит текущего принятого B. Authority **не менялась**.
Этот документ фиксирует исходные зависимости, не доказывает GPU-resident POC.

| Читатель / писатель | Что наблюдается / меняется | Обязательство будущего GPU пути |
|---|---|---|
| `game_gpu.c:capture_frame` | Native PICA color и stencil → logical RGB5 display rectangle; generation++; dirty | Дождаться того же OT cut; сохранить nearest sample phase, Y flip, scaling, bit 15 из stencil и token/страницу |
| `StoreImage/StoreImage2` | capture затем произвольный canonical rectangle в PSX RAM / native stack | До возврата CPU должен увидеть актуальные RGB5/STP слова; никакого stale GPU alias |
| `MoveImage` и GP0 DR_MOVE | source canonical region, overlapping row-order memmove, destination generation/dirty | Материализовать source, сохранить overlap, порядок и обе PS1 framebuffer pages; нельзя заменить только визуальным blit |
| `ClearImage/ClearImage2` | GPU fence → CPU RGB5 fill → generation/dirty | CPU write отзывает GPU aliases; старая очередь не должна читать новые данные раньше barrier |
| `stage4_fs.c:LoadImage` | TIM image/CLUT и произвольные разрешённые RAM snapshots; flush/dirty **до** canonical write | Сохранить source validation, prior draws и порядок записи; destination может быть image, palette или framebuffer |
| `game_texture_decode_init` | Canonical CLUT, 16/256 entries с X wrap; zero/STP coverage | Любой GPU-owned overlap palette требует materialize/coherence перед этим CPU read |
| `game_texture_decode_row/tiles` | Canonical packed 4/8-bit image или RGB5 words; page X/Y wrap | Поддержать aliases через разные page/mode/CLUT keys, не только прямую 16-bit framebuffer page |
| `game_texture_invalidate` | Image и palette overlap для всех resident entries | Сохранить 8×8 dirty rectangle; CLUT консервативно инвалидирует весь зависимый output; нельзя считать generation полным flush |
| Submission pin/acquire | Все resident unique keys pinned до misses, затем immutable textures до GPU finish | Snapshot/generation и cache lifetime должны переживать ordered draws, включая partial submissions |
| `main_game.c:feedback_words/feedback_row` | Отдельный native-sized RGB5 snapshot, generation, CPU color modulation, special feedback texture | Сохранить version/extent/color, исходный RGB5/modulation recurrence и flush при изменении цвета; это отдельный alias от canonical display |
| `Game3ds_FramebufferCapture` | Canonical resolve, native snapshot, older draw-page seed, framing/feedback_ready | Не смешивать native 400-wide и logical 320-wide coordinates, draw_origin_y и last_frame.y, progressive/interlaced/bottom |
| `water.c:func_8008D850` | `StoreImage2` 2×1 из x=784/792,y=112; CPU проверяет `(pixel & 0x7fff)==0x7fff` | Точный seed, opposite buffer и temporal ordering; CPU ramp управляет исходными flare primitives |
| `world_draw.c:WorldGfx_CharaModelTransparentSet` | Читает 16×16 palette через StoreImage, меняет STP каждого слова, LoadImage назад | Реальная CPU-visible palette mutation; пропуск CPU coherence меняет прозрачность/маски |
| Events/load/mapscreen/Cafe | StoreImage в IMAGE_BUFFER/FS_BUFFER, затем LoadImage/MoveImage для переходов и feedback | Сохранить RAM snapshots и framebuffer history вне обычного world rendering |
| `psx_vram_store/texel/decode/crc`, TIM upload | Общие CPU read/write helpers; CRC/report и diagnostic users тоже читают canonical | При lazy materialization доступ должен иметь единый протокол; caller list проверяется по linked closure |
| `main_game.c:trace_primitives` | Debug CPU image/CLUT read для zero/STP/opaque counters | Диагностика не должна молча наблюдать stale words; явный materialize либо запрет такого trace |

Проверенные файлы: `3ds_port/source/game_gpu.c`, `main_game.c`, `render_3ds.c`,
`stage4_fs.c`, `psx_vram.c`, `psx_tim.c`, `game_texture_cache.c`,
`game_texture_decode.c`, `include/psx_readback_region.h`, `psx_game_pixel.h`,
`game_feedback.h`, `psx_batch.h`; CPU consumers в `src/bodyprog/water.c`,
`gfx/world_draw.c`, `bodyprog_80085D78.c`, `bodyprog_mapscreen_80066EB0.c`,
`events/events_util.c`, `events/game_sys_states.c`, `src/maps/map0_s01/`.
Другие не собранные карты с StoreImage не объявляются проверенными игровыми
маршрутами. Условные PC-only debug reads не доказывают активность на 3DS.

Семантика alpha: canonical word 0 → zero coverage; `0x8000` → видимый STP black;
nonzero без STP → opaque; nonzero со STP → semitransparent class. Texture alpha
0/128/255 и framebuffer stencil — разные представления. Формат RGBA5551 сам
по себе не кодирует все три texture класса. PS1 ABR применяется только к STP
для текстур; painter ordering, masked writes/tests и primitive boundaries
остаются обязательны. Геометрический depth в принятом backend выключен.

`readback_surface` кешируется по renderer generation, отдельно от canonical
VRAM generation; GPU-produced attachment переносится transfer engine в linear
color/mask с CPU invalidate. CPU-written decoded texture, напротив, требует
flush до sampling. Нельзя заменить один cache operation другим. Прежний
`FrameBegin` fence также защищает linear vertex reuse и освобождение textures.

Перед GPU-resident экспериментом ещё нужны: measured стоимость этой цепочки
после partial tiles; per-region version/authority state machine с alias rules;
отдельный oracle CPU reads/writes, palette overlaps, STP/mask и длинных
feedback sequences; реальные PICA color/precision/barrier проверки. CPU путь
остаётся reference/fallback. Обход canonical VRAM на основании одного
flashlight кадра этим аудитом не разрешается.
