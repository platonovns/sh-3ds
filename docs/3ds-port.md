# Silent Hill: технический аудит для New Nintendo 3DS

Дата: 24 октября 2026. Цель: native ARM11-приложение `.3dsx` на devkitARM/libctru, впоследствии — PICA200, звук, два экрана и stereoscopic 3D.

Аудируемая база: `SlickAmogus/silent-hill-decomp`, ветка `pc-port`, commit `5dafd8ab923baf9e9c00c99d4ccd3d31e99ea07b`. Рабочая ветка: `3ds-port`. PsyCross закреплён на `9f74c4c314251a7ed04d8c7e5906c782f0b342c7`. Все submodules инициализированы рекурсивно; их ревизии не изменены. В рамках задачи добавлен только этот документ.

Метод: чтение сборочных файлов, платформенных адаптеров и непосредственных потребителей их API; выборочное изучение console/ARM-веток через `git show`. Игровая логика и массивы игровых данных подробно не исследовались. Сборка и запуск игры не выполнялись; devkitARM, Make и CMake не обнаружены в PATH текущего окружения, переменные `DEVKITARM`/`DEVKITPRO` не заданы. Числа производительности и доступной памяти на устройстве пока не измерены. Игровые образы не скачивались, извлечение данных не запускалось.

## 1. Обзор архитектуры

Это native-порт декомпилированного C-кода, а не исполнение MIPS-бинарника. Совместимые реализации отдельных PSX-подсистем — GTE, SPU, VRAM и CD API — обеспечивают прежний контракт игры; их наличие не превращает проект в эмулятор всей консоли.

Основная цепочка:

```text
main_pc.c → начальная настройка памяти, указателей, региона, PsyCross и файлов
          → MainLoop() [src/bodyprog/sys/game_main.c]
          → engine + screen overlays + текущая map overlay
          → PsyQ API / PC compatibility shims
          → PsyCross: GTE / GPU command parser / SPU / CD / pad / timing
          → SDL2 + OpenGL/GLES + audio sinks + host filesystem
```

`src/main`, `src/bodyprog`, `src/screens` и `src/maps` содержат основную игру. `SH_PC_PORT` включает уже сделанные исправления адресации и host-адаптацию. Это не узкий переключатель ОС: под ним также находятся UI, modding и renderer enhancements. Поэтому новый `SH_3DS_PORT` разумно строить поверх необходимых `SH_PC_PORT`-совместимых участков, с явным выбором файлов и возможностей.

`main_pc.c` заменяет PSX `main`, переназначает overlay/buffer pointers, вызывает многочисленные initializer-функции восстановленных таблиц и затем `MainLoop()`. Эти инициализаторы нельзя потерять при написании компактного 3DS bootstrap. `map0_s00` всегда встроена; другие карты выбираются через `MapRegistry`/`MapOverlay_Load`. На desktop они загружаются как native DLL/SO, либо статически с переименованными символами.

Сохранить предполагается игровую state machine, combat/AI, форматы ресурсов, очереди FS, fixed-point координаты и интерфейсы PsyQ. Работоспособность конкретных функций после cross-compilation должна подтверждаться поэтапно.

Основания: [PC entry point](../pc_port/src/main_pc.c), [MainLoop](../src/bodyprog/sys/game_main.c), [map loader](../pc_port/src/map_overlay_loader.c), [registry](../pc_port/src/map_registry.c).

## 2. Значимые каталоги и файлы

| Путь | Значение для переноса |
|---|---|
| `pc_port/CMakeLists.txt`, `pc_port/build.sh`, `pc_port/build.bat` | Native desktop build, наборы исходников, defines, зависимости, map targets |
| Корневой `Makefile` | PSX matching/reconstruction pipeline; не основа `.3dsx` |
| `pc_port/maps/CMakeLists.txt`, `pc_port/tools/prefix_map_syms.py` | Изоляция одинаково названных символов карт, DLL/static варианты |
| `include/decomp/common.h`, `include/decomp/types.h`, `include/gpu.h` | Адреса scratchpad, типы, отключённые PC layout asserts, GTE macros |
| `pc_port/include/psyq/`, `pc_port/include/psyq_compat/libgs.h` | Приоритетные PsyQ compatibility headers; порядок include paths существенен |
| `pc_port/src/psx_memory.c`, `pc_port/include/psx_memory.h` | Host buffers вместо абсолютных адресов PSX |
| `pc_port/src/stubs/libgs_stub.c` | Реальная GS-адаптация, несмотря на имя: OT, кадры, timing; содержит SDL/GL |
| `pc_port/PsyCross/src/psx/` | `libgpu`, `libgte`, `libspu`, `libcd`, `libpad`, `libetc`, `libapi`, `libmcrd` |
| `pc_port/PsyCross/src/gpu/PsyX_GPU.cpp` | Разбор GPU packets/OT, vertices, splits, крупные desktop buffers |
| `pc_port/PsyCross/src/render/`, `include/PsyX/PsyX_render.h` | `GR_*`, GL/GLES, GLSL, framebuffer feedback; будущая граница PICA200 |
| `pc_port/PsyCross/src/gte/` | Программная GTE и таблицы математики; также PC precision extensions |
| `pc_port/PsyCross/src/audio/`, `include/PsyX/PsyX_audio.h` | SPU core, dispatch, XA stream, output/sink API |
| `pc_port/PsyCross/src/PsyX_main.cpp`, `src/pad/PsyX_pad.cpp` | SDL lifecycle, VBlank thread, pad buffers, input polling |
| `src/main/fsqueue_1.c`, `fsqueue_2.c`, `fsqueue_3.c`, `fileinfo.c` | Фактический CD/resource pipeline, file indices, post-load и loose overrides |
| `pc_port/src/{ipd,lm,dms,as_rodata}_reformat.c` | Преобразование дисковых offsets в native pointers и host layouts |
| `pc_port/src/xa_player*.c`, `src/fmv/` | Реплики, XA/STR/MDEC и desktop video overrides |
| `pc_port/build_gen/extracted_data/` | 43 уже отслеживаемых C-файла с извлечёнными map tables |
| `pc_port/src/pc_minimap.c`, `include/bodyprog/sys/joy.h` | Возможные точки будущего bottom-screen UI и контракт контроллера |

### Доступные console/ARM-примеры

В проверяемом checkout нет PSP backend. Его нет и среди полученных remote branch refs основного репозитория и PsyCross. README и комментарии console-кода упоминают PSP, но это не доказательство наличия доступной реализации. PSP-специфические optimizations или их готовность здесь не предполагаются.

Другие ветки доступны локально после clone; они **не включены** в `3ds-port`:

| Ветка и проверенный commit | Полезный материал | Предел применимости |
|---|---|---|
| `n64-port`, `40ea7c987254810ae3b7f13f93e3a28abdacdd82` | `n64_port/n64_gate.sh`, `src/dso_n64.c`, `src/heap_census_n64.c`, `src/pad_n64.c`, `src/audio_n64.c`; унаследованные `xbox_port/src/gpu_xbox.c`, `psx_vram.c` | Compile gate, один resident overlay, budget counters, раздельные OT decoder/GPU backend. N64 DSO loader зависит от libdragon; напрямую на 3DS не переносится |
| `ps3-port`, `75eaaaac4fee80f92a86372263c9f481c17279f4` | `ps3_port/include/ps3_hal.h`, `src/gpu_rsx.c`, `src/rsx_video.c`, `src/audio_out_ps3.c` | Разделение SDK/game headers и hardware buffers, flush перед сменой состояния. PowerPC/RSX-код не нужен ARM11 |
| `ios-port`, `ebef2b4130720d0b6b04797c29231ac24525fced` | `ios_port/CMakeLists.txt`, bootstrap/paths; static map path уже есть в текущей PC-базе | ARM64/GLES подтверждает предусмотренные платформенные варианты, но не ARMv6K/PICA200 |
| `android-port`, `a03d26a2cd0c5881b4b20fd2f109914681563fd0` | JNI CMake, platform storage/bootstrap | Пример отдельной оболочки над PC-кодом; SDL/GLES остаются зависимостями |

У console-веток другие версии PsyCross: например, gitlink N64 — `5c6d1acc9be3e5323bae3cd18ec21e1a7101e597`, PS3 — `d38a1c5433eeda6a6c1826b680e3db5b6c8022cb`. Выборочное заимствование требует сравнения API, а не массового cherry-pick.

Особенно полезны bounded texture cache и invalidation в `psx_vram.c`, разделение `gpu_xbox.c`/`gpu_nv2a.h` и наблюдение allocations в N64. Однако палитровый NV2A/RDP path не соответствует PICA200. В `audio_n64.c` прямо отмечены усечение длинных samples и отсутствие XA player; такой backend не годится как готовое решение звука. В `pad_n64.c` включён диагностический autostart — его нельзя копировать в пользовательский input.

Проверяемые ссылки: [N64 tree](https://github.com/SlickAmogus/silent-hill-decomp/tree/40ea7c987254810ae3b7f13f93e3a28abdacdd82/n64_port), [console VRAM cache](https://github.com/SlickAmogus/silent-hill-decomp/blob/40ea7c987254810ae3b7f13f93e3a28abdacdd82/xbox_port/src/psx_vram.c), [PS3 HAL](https://github.com/SlickAmogus/silent-hill-decomp/blob/75eaaaac4fee80f92a86372263c9f481c17279f4/ps3_port/include/ps3_hal.h).

## 3. Внешние зависимости и сборка

PC build: CMake ≥ 3.16, C11, C++17, обычно Ninja. Корневой Makefile обслуживает исходный PSX target и инструменты декомпиляции. Для native-порта не нужны оригинальный PSX compiler, MIPS objects или сборка дискового образа.

`pc_port/CMakeLists.txt` исключает PSX `main.c`/`memcpy.c`, включает engine/screens, стартовую карту и рекурсивно **весь** `pc_port/src`. PsyCross аналогично glob’ит C/C++ и требует SDL2/OpenAL. Для 3DS нужны явные source lists или target-specific filters: смены компилятора и `SH_USE_OPENGL=OFF` недостаточно. Этот option объявлен, но не делает текущие GL-файлы независимыми от GL.

| Зависимость | Как используется сейчас | Решение для первого игрового target |
|---|---|---|
| PsyCross, submodule `9f74c4c3…` | PsyQ совместимость, rendering, GTE, SPU, CD, timing/input | Сохранить API и переносимые cores; заменить host backends |
| SDL2 | Window/events, pad, timer/thread/mutex, audio; вызывается также из game shims | Прямой libctru backend; допустим узкий shim только для реально нужных оставшихся вызовов |
| OpenGL/GLES, glad; опционально ANGLE на Windows | GLSL, textures, framebuffer, renderer backend selection | Исключить; PICA200 через citro3d |
| OpenAL | Legacy SPU/XA, spatial output, отдельные UI sounds | Исключить из 3DS profile; software SPU → NDSP |
| libjpeg | Безусловная link-зависимость PC target для MJPG overrides | Не нужна ранним этапам; штатный STR отдельно |
| FFmpeg | Optional headers, runtime-loaded libraries для video overrides | `SH_FMV_FFMPEG=OFF`; исключить desktop decoder front end |
| rcheevos, submodule `2ad0b867…`; WinHTTP/libcurl | Achievements, HTTP, disc hashing | Выключить `SH_ENABLE_RETROACHIEVEMENTS`; не подключать сеть |
| Vendored Lua 5.4 | Randomizer; автоматически собирается при наличии исходников | Не включать в минимальный target; отдельного полного feature-off покрытия пока не гарантировано |
| stb_image/stb_truetype, miniz, xxHash, cgltf | Texture packs, UI/fonts, hashing, model replacements | Не основные требования игры; отложить вместе с соответствующими callers |
| Python/LLVM nm/objcopy | Generators, static overlay symbol prefixing | Только host build tools, если выбран этот map pipeline; ARM ELF обработку проверить отдельно |

Остальные submodules: `tools/asm-differ` (`50d160e…`), `decomp-permuter` (`b44b062…`), `m2c` (`041ed8b…`), `maspsx` (`0249ed2…`). Они инициализированы по условию задачи, но не нужны для запуска native `.3dsx`.

Наследовать `-fno-strict-aliasing -fwrapv`: они уже явно заданы upstream из-за type-punning и signed wrap в декомпиляции. Не включать `-ffast-math` без отдельного обоснования. Не переносить desktop warning suppressions вслепую: compile gate должен выделять реальные ABI/implicit declaration ошибки.

Источники: [PC CMake](../pc_port/CMakeLists.txt), [PsyCross CMake](../pc_port/PsyCross/CMakeLists.txt), [submodules](../.gitmodules), [COPYRIGHT.md](../COPYRIGHT.md). Лицензии неоднородны: GPL-3.0-or-later PC additions не означают выдачу лицензии на всю декомпиляцию или игровые материалы; notices компонентов нужно сохранять.

## 4. Границы платформенной абстракции

| Слой / контракт | Что сохранить | Что адаптировать или реализовать |
|---|---|---|
| Игра → PsyQ (`Gs*`, `Draw*`, `gte_*`, `Spu*`, `Cd*`, `Pad*`, `VSync`) | Названия, семантику, игровые callers | Реализацию ниже интерфейса |
| GPU packets → `GR_*` | OT traversal, primitive decode, draw environments, последовательность | PICA backend, texture cache и представление vertex stream; ограничить PC extensions |
| SPU core → PCM → `AudioSink` | SPU registers/voices/ADPCM/reverb и XA decode | NDSP sink, clocks, bounded buffering, lock adapter; backend enum/dispatch пока не знают NDSP |
| FS queue → CD sector reader | File indices, post-load, resource relocation | `sdmc:` root, sector I/O, EOF/errors, кэш чтения |
| `MapRegistry` → `MapOverlay_Load` | Выбор карты, header и lifecycle | Native code residency без desktop `dlopen` |
| PSX address → host buffer | `PSX_ADDR`, scratchpad mapping | Проверки диапазона/выравнивания, контроль оставшихся абсолютных адресов |
| Startup/timing/input | Необходимый порядок init, pad format, VBlank semantics | libctru lifecycle, HID, monotonic clock и synchronization |

Абстракции пока неполные. `main_pc.c`, `libgs_stub.c`, FMV, texture/UI modules напрямую включают SDL/GL; `PsyX_render.h` выбирает только GL/GLES и выдаёт `#error` для неизвестного renderer. `platform.h` тоже не содержит `__3DS__`. Понадобятся небольшие target guards и разделение host/backend compilation, даже при сохранении API.

PsyQ `open/read/write/close/lseek` в `libapi.c` имеют имена libc и иные контракты. Существующая hidden visibility защищает desktop dynamic linking, но не исключает конфликт с newlib внутри статически связанного `.3dsx`. Для 3DS нужны отдельные namespaced PSX wrappers/redirects; иначе stdio SD-карты может попасть в memcard shim.

SDK headers держать в HAL translation units, game/decomp headers — по другую сторону простого C-интерфейса. В частности, игра определяет собственные `bool`, `s32`, `u32`; совместимость с libctru следует проверить compile probes, а не предполагать по совпадению размеров.

## 5. Rendering architecture

Текущий путь: game geometry → software GTE → projected PSX primitives → OT → `libgpu.c`/`ParsePrimitivesLinkedList` → `GrVertex` и `GPUDrawSplit` → `DrawAllSplits` → `GR_*` → GL/GLES. `libgs_stub.c` поддерживает более высокий GS API. PC enhancements добавляют PGXP/view-space shadows, modern meshes, per-pixel flashlight, filtering, whole-map rendering и framebuffer effects.

PSX VRAM хранится на CPU как `unsigned short vram[1024*512]`: 1 MiB. Текстуры 4/8-bit indexed с CLUT либо 16-bit direct адресуются через tpage/clut. GL shader декодирует VRAM/палитру при sampling; desktop VRAM texture — RG8. Это нельзя механически повторить GLSL-кодом на PICA200: fragment-композиция задаётся TEV, а не произвольным desktop fragment shader. См. [citro3d texenv API](https://github.com/devkitPro/citro3d/blob/master/include/c3d/texenv.h).

Предлагаемый первый renderer:

- CPU GTE и OT order оставить; рисовать screen-space triangles через citro3d vertex shader и TEV modulation. Исходно — mono, штатная видимость/streaming, nearest filtering и классическое освещение.
- CPU shadow VRAM оставить authoritative для `LoadImage`/`MoveImage`/`StoreImage`; декодировать страницы по `(tpage, clut, format)` в поддерживаемую PICA texture, swizzle/upload и кэшировать. Записи в пиксели **и CLUT** должны инвалидировать зависимые записи кэша.
- Не путать PSX STP bit с обычным RGBA alpha. Нужны прозрачный нулевой texel, opaque texels и semitransparent texels; для смешанной страницы могут понадобиться отдельные passes с alpha test. Проверить все ABR: `(B+F)/2`, `B+F`, `B-F`, `B+F/4`, raw/modulated textures, clipping и texture window.
- Сохранять порядок прозрачных примитивов; batching только соседних совместимых draws. Изначально depth test отключён для обычной OT painter path. Кэш/vertex ring не переиспользовать до завершения чтения GPU.
- Сначала 320×240 content в центре верхних 400×240 с полями по 40 pixels. Widescreen и изменение projection отложить. Учесть ориентацию render targets/display transfer.

PICA не предлагает PSX CLUT textures напрямую: список [GPU texture formats](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/gpu/enums.h) содержит обычные color/luminance/ETC formats. Поэтому CPU decode cache предпочтительнее попытки перенести GL palette shader. RGBA5551 экономит память, но одного alpha bit недостаточно для всей STP-семантики; выбор формата и дополнительных passes требует отдельной проверки.

Важная несогласованность комментариев: PC CMake включает `PSYX_SKIP_FRAMEBUFFER_STORE` с пояснением об отсутствии readback, однако текущий renderer содержит `GR_StoreFrameBufferPsx`, `GR_RepackFrameToVramBuffers`, feedback samplers и scene-scratch logic. Нельзя считать framebuffer feedback ненужным. Его допустимо временно отключить для раннего milestone, затем проверить loading blur, dream/ghost effects, pause/save backgrounds и копии display pages.

Stereoscopic 3D — поздняя отдельная задача. Готовый PSX screen-space stream часто уже потерял глубину; простое копирование изображения в два глаза глубины не создаст. Нужны достоверные view-space/depth данные, две eye projections и отделение HUD/2D. Существующий PGXP/view-space tracking — источник идей, но его огромные таблицы не подходят 3DS. Решение должно быть ограниченным по памяти; stereo увеличит GPU/fill cost и число targets.

Основания: [libgpu](../pc_port/PsyCross/src/psx/libgpu.c), [GPU parser](../pc_port/PsyCross/src/gpu/PsyX_GPU.cpp), [renderer](../pc_port/PsyCross/src/render/PsyX_render.cpp), [render API](../pc_port/PsyCross/include/PsyX/PsyX_render.h).

## 6. Audio architecture

Звуковая логика игры в `src/bodyprog/libsd/` вызывает PsyQ `Spu*`/sound APIs. PsyCross `libspu.c` → `PsyX_SPUDispatch.cpp` выбирает legacy OpenAL либо software SPU. Текущая PC-конфигурация по умолчанию использует `authentic` software renderer; README или старые OpenAL-only схемы не отражают весь текущий путь.

`PsyX_SPUCore` backend-neutral: 512 KiB SPU RAM, 24 voices, PSX ADPCM, pitch/ADSR, mixing и связанные reverb implementations. `RenderFrames()` выдаёт PCM с канонической частотой 44100 Hz. Core не синхронизирует доступ самостоятельно. `PsyX_SPUSoftware.cpp` добавляет SDL mutexes и output callbacks; `PsyX_audio.cpp` управляет sinks SDL/WASAPI. Enhanced modes с double/high sample rates не нужны начальному 3DS profile.

XA — отдельный обязательный тракт: `xa_player_dispatch.c` → legacy/software player, sector decode/stream, подача XA в software SPU CD input. Используется отдельно открытый BIN handle; `g_FileXaLoc`, offsets, drain и модели seek/end timing влияют на синхронизацию реплик. Их следует сохранить. `xa_wav.c` относится к loose replacements. FMV имеет собственные video/audio paths, SDL threads/queues и GL presentation; одного переноса SPU для него недостаточно.

Рекомендация: сохранить core и XA decoder, добавить NDSP output adapter, изначально stereo PCM16, небольшой заранее выделенный ring из нескольких `ndspWaveBuf`. PSX ADPCM не равен DSPADPCM NDSP, поэтому напрямую отдавать исходные VAB blocks DSP нельзя. Сначала микшировать на CPU, NDSP использовать для вывода и согласования output rate. Частота SPU timeline и device consumption должны быть разведены явно.

Буферы — linear memory, cache flush перед передачей DSP, повторное заполнение только после `NDSP_WBUF_DONE`. Отдельно обработать недоступность DSP, suspend/resume, underruns и drain. При необходимости DSP component должен быть локально доступен из окружения пользователя; не распространять Nintendo firmware и не требовать звук для первого smoke target. Официальный [NDSP streaming example](https://github.com/devkitPro/3ds-examples/blob/master/audio/streaming/source/main.c) демонстрирует ring/flush; [NDSP channel API](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/ndsp/channel.h) определяет PCM/DSPADPCM formats.

Основания: [SPU core](../pc_port/PsyCross/src/audio/PsyX_SPUCore.h), [sink boundary](../pc_port/PsyCross/src/audio/PsyX_audio_sink.h), [software adapter](../pc_port/PsyCross/src/audio/PsyX_SPUSoftware.cpp), [audio config](../pc_port/src/pc_audio_config.c), [XA software player](../pc_port/src/xa_player_software.c).

## 7. Input architecture

Игра читает PSX raw pad buffer через `PadInitDirect`/`Joy_*`; PsyCross заполняет его из SDL keyboard/controller mapping. Digital buttons active-low, нейтральные axes — 128; pad ID различает digital `0x41` и analog `0x73`. Сохранять нужно именно этот формат, а не вводить HID-вызовы в combat/game logic.

3DS adapter: один `hidScanInput()` на input tick, `hidKeysHeld()` для состояния, Circle Pad/C-stick → clamp/deadzone → PSX axes. Edge detection оставить существующему игровому слою. HID на New 3DS использует IRRST; `hidCstickRead` — alias `irrstCstickRead`. Не инициализировать IRRST повторно без необходимости: это уже учитывает `hidInit()` ([HID implementation](https://github.com/devkitPro/libctru/blob/master/libctru/source/services/hid.c), [IRRST API](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/services/irrst.h)).

Начальная раскладка по физическим позициям: B→Cross, A→Circle, X→Triangle, Y→Square; D-pad→D-pad, L/R→L1/R1, ZL/ZR→L2/R2, Start/Select напрямую. Circle Pad→left stick, C-stick→right stick. Предусмотреть настройку и цифровой fallback для классического управления. Знаки Y, радиальная deadzone и чувствительность C-stick проверяются на устройстве. L3/R3 требуют альтернативной привязки; встроенной вибрации нет.

C-stick сам по себе не добавляет свободную камеру оригинальной игре: для неё потребуются существующие alternate-camera hooks, которые включаются позднее. Touch input изначально только для оболочки. Будущий bottom-screen map/inventory должен преобразовывать касания в ограниченные UI actions и сохранять правила паузы/меню; нельзя одновременно запускать две игровые state machines.

Основания: [pad backend](../pc_port/PsyCross/src/pad/PsyX_pad.cpp), [game pad layout](../include/bodyprog/sys/joy.h), [PC bindings/init](../pc_port/src/main_pc.c).

## 8. Filesystem и загрузка ресурсов

Главный runtime путь — `Fs_Queue*` → file table/LBA → `CdRead`/`CdReadSync` → PsyCross `libcd.c`, затем TIM/ANM post-load и relocation. `fs_pc.c` реализует простой stdio wrapper, но поиск его callers не показывает, что через него проходит основная игра. Поэтому перенести только `FsPC_ReadFile` недостаточно.

PC bootstrap выбирает образ, определяет регион и переназначает таблицы файлов. Текущий `main_pc.c` при отсутствии BIN завершает работу с ошибкой; заявленный в `fs_pc.h` extracted-directory fallback не равнозначен полноценному бездисковому пути. Loose files `gamedata/load/...` — дополнительные overrides с fallback к диску.

Данные CD и XA имеют разную геометрию: обычное чтение извлекает 2048-byte payload из raw Mode 2 sectors; XA player использует 2352-byte raw sectors и 2336-byte slice начиная с offset 16. `CdReadSync(1)` продвигает очередь по sector; изменения скорости/батчинга должны сохранять async completion/callback semantics. Не заменять raw BIN обычным ISO без проверки — XA/FMV данные могут потеряться.

Для 3DS предлагается `sdmc:/3ds/silenthill/` с `gamedata/`, `saves/`, `config.cfg` и логом; это будущая договорённость, сейчас таких путей в коде нет. Сохранить raw BIN reading через stdio/libctru FS, проверять short reads и границы destination, использовать небольшой sequential cache/read-ahead только после правильного baseline. У CD data, XA и FMV должны быть независимые cursors либо сериализованный reader с явными offsets.

`libapi.c` и `libmcrd.c` обеспечивают memcard compatibility поверх файлов `.MCD`; нужны writable save root, namespaced wrappers и корректные ready/error/completion statuses. Сохранения важны уже для прохождения startup memcard checks. Отсутствие SD или записи должно давать понятное состояние и выход/явный fallback, а не вечный busy loop.

Позднее локально потребуются: собственный поддерживаемый BIN/CUE, модели/текстуры/карты, ANM, VAB/sound banks, XA и STR. Сами файлы карты с PSX MIPS-кодом не исполняются на ARM: executable overlay code компилируется из C, а runtime/извлекаемые таблицы обрабатываются отдельно. В checkout уже есть generated map C tables; `extract_map_data.py` и `gen_map7_s03_boss_motion.py` для регенерации обращаются к локальному `disc_extract/VIN`. Их не запускать автоматически при сборке без данных. Сначала поддерживать один явно выбранный регион, затем проверять region remapping.

В `.3dsx`/RomFS допустимы собственные test patterns/shaders и необходимые свободно распространяемые материалы. Образ диска и извлечённые игровые ресурсы в пакет не включать. Первый milestone вообще не требует игровых данных.

Основания: [FS queue](../src/main/fsqueue_3.c), [CD implementation](../pc_port/PsyCross/src/psx/libcd.c), [simple FS wrapper](../pc_port/src/fs_pc.c), [memcard API](../pc_port/PsyCross/src/psx/libapi.c), [extraction tool](../pc_port/tools/extract_map_data.py).

## 9. Память New 3DS

Нельзя принять физические 256 MiB FCRAM за доступный приложению heap. Доступный объём, распределение обычного/linear heap и права зависят от launcher/режима процесса; их измеряет первый executable. Физическая VRAM — 6 MiB; значения отражены в [libctru os.h](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/os.h). New 3DS speedup включать через `osSetSpeedupEnable(true)` после проверки модели, но это не выдаёт приложению всю RAM или все CPU cores.

### Уже обнаруженные крупные allocations

| Объект | Размер / оценка | Следствие |
|---|---|---|
| `g_PsxRam` | **3 MiB**, несмотря на устаревший комментарий header про 2 MiB | 2 MiB address window + 1 MiB overflow guard; не сокращать до анализа всех FS destinations |
| `g_PsxScratchpad` | 4096 bytes; отдельно есть scratch buffer `libetc.c` | Выравнивание, mapping и lifetime требуют проверки |
| CPU PSX VRAM | 1 MiB | Оставить; учитывать decoded GPU copies отдельно |
| `s_shadow[1<<21]` | ≈48 MiB при ILP32 (`ShadowEntry` 24 bytes) | Desktop PGXP storage должен исчезнуть из минимального build |
| `s_vshadow[1<<21]` | ≈88 MiB при ILP32 (`VsEntry` 44 bytes) | View-space tracking недопустим в текущем размере |
| `g_vertexBuffer[1<<18]` | 17 MiB (`GrVertex` packed, 68 bytes) | Нужен bounded batch/ring; GL копия тоже стоит память |
| `s_farQuads[1<<18]` | ≈21 MiB (`PsyX_FarQuad` 84 bytes) | Whole-map pool исключить для штатного streamed profile |
| SPU RAM | 512 KiB + state/reverb/XA buffers | Реалистичная база, но это не весь audio footprint |
| `SH_STATIC_MAPS` | Upstream CMake сообщает ~198 MB `.bss` и ~4 MB `.text` в Windows verification build | Это чужое измерение сборки, не ARM-замер и не изолированная оценка одних карт |

Расчёты таблиц выполнены по полям текущих structs при 4-byte pointers/float/int. Только четыре перечисленных GPU pools дают около **174 MiB**, без прочих renderer/GTE/map buffers. Они объявлены без условного исключения этих массивов по `USE_PGXP`; runtime config=0 не освобождает `.bss`. Даже уменьшение pointer width не решает проблему. Итоговый ELF `size`/linker map обязан подтвердить отсутствие этих секций; нельзя полагаться на оптимизатор или desktop demand-zero.

Начальные **предлагаемые лимиты**, не измеренные потребности: 3 MiB PSX RAM; 1 MiB shadow VRAM; 2–4 MiB decoded texture cache; до 1 MiB vertex staging/ring; до 1 MiB GPU command buffers; до 2 MiB audio/XA/reverb working buffers. Отдельно посчитать `.text/.rodata/.data/.bss`, map state, normal heap, linear heap, stacks и framebuffer targets. Лимиты уточнять по реальному working set, избегая texture-cache thrashing.

Одна 256×256 RGBA8 page стоит 256 KiB; RGB5551 — 128 KiB. Цветовой target 400×240×4 — 375 KiB без depth/padding/дополнительных копий. Stereo и два экрана добавляют buffers. Текстуры могут находиться в GPU-доступной linear memory, а не обязательно целиком в 6 MiB VRAM; placement выбрать явно. [linear allocator](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/allocator/linear.h) требует парного `linearFree`, предоставляет `linearSpaceFree`; обычный `malloc` не заменяет GPU/DSP allocator.

Добавить позднее counters/high-water marks для heap/linear/textures/vertices/SPU/FS и обрабатывать allocation failures. Фрагментация и пиковое сосуществование старой/новой карты важнее среднего расхода. Для native map code сначала проверить статический registry с ограниченным набором карт; для полной игры исследовать разделяемую рабочую arena/повторное использование map BSS. Не начинать с собственного ARM runtime loader: `.3dsx` не предоставляет desktop DLL/SO loader, а размещение исполняемого кода, relocations и cache maintenance потребуют отдельного доказательства.

## 10. Ожидаемые проблемы переносимости

1. **ILP32 и layout.** ARMv6K little-endian ближе к PSX, чем LP64 desktop, но PC structs уже расширялись. `P_TAG`/OT_TAG, native pointers и resource offsets не обязаны совпадать с дисковыми структурами. `ipd/lm/dms_reformat` нельзя удалить только потому, что pointers снова 32-bit. Проверять `sizeof/offsetof` и relocation на синтетических buffers.
2. **Отключённые проверки.** `include/decomp/common.h` превращает `STATIC_ASSERT*` в no-op под `SH_PC_PORT`. Нужны отдельные ARM layout probes для ABI и serialized formats, без глобального возврата всех PSX asserts для изменённых PC structs.
3. **Alignment/UB.** Packed structs, word stores через cast, aliasing и signed shifts могли работать на x86. ARM11 не позволяет считать произвольный unaligned доступ безопасным. Проверять resource readers, scratch buffers, GPU attributes и boundary casts; сохранять wrap/alias flags, исправлять локально.
4. **Absolute pointers.** `PSX_ADDR()` маскирует адрес `&0x1FFFFF`, а не проверяет его. Overflow guard не доказывает корректность чтения. Оставшиеся `0x800...` function/data pointers, constructor fixups и raw map headers требуют проверки.
5. **Host API leakage.** SDL/GL headers в общих files; Win32/POSIX dynamic loading, Discord/plugins/HTTP; stdio/PSX symbol collision; basename/path/case и relative cwd assumptions.
6. **Toolchain.** GNU C extensions, implicit declarations, assembler `.set` aliases в generated motion data, symbol prefixing и constructors нужно проверить на ARM ELF. `map7_s03_boss_motion.c` уже выбирает ILP32 размер 12 bytes, но это не проверяет остальные таблицы.
7. **CPU budget.** Software GTE/SPU/CLUT conversion и per-primitive calls могут стать bottleneck. ARM64 и Raspberry Pi preprocessor paths не являются ARM11 оптимизацией. Double/high-rate precision extensions отложить; не обещать FPS до профиля на устройстве.
8. **GPU semantics.** PSX painter order, mixed STP, subtractive blending, draw offsets, texture windows, framebuffer feedback и дезеринг требуют отдельных visual cases. Desktop GLSL/shadows/postprocess напрямую не переносятся.
9. **Полнота игры.** Успешный boot стартовой карты не проверяет map transitions, поздние боссы, сохранения, XA/FMV и регионы. Отсутствующий overlay сейчас может давать NULL header; на 3DS это должна быть диагностируемая ошибка.

## 11. Предлагаемая архитектура 3DS

Добавлять небольшой target `3ds_port/`, не менять игровую логику и не переносить целиком другую console-ветку. Будущие имена ниже — план, файлов пока нет:

```text
3ds_port/Makefile + source manifest
  main_3ds.c          bootstrap, APT lifecycle, New3DS check, config/log roots
  hal_3ds.h           простой C ABI без пересечения SDK/decomp headers
  time_3ds.c          monotonic clock, VSync/callback scheduling
  pad_3ds.c           HID → существующий PSX pad buffer
  fs_3ds.c            SD paths, sector reader, save backing
  render_3ds.cpp      GR_* backend / citro3d, bounded texture/vertex storage
  audio_3ds.cpp       software SPU adapter / NDSP sink
  map_3ds.c          существующий MapOverlay contract, bounded map registry
```

`render_3ds` сначала обслуживает минимальную PSX primitive path. Предпочтение — сохранить PsyCross parser и интерфейс `GR_*`, условно исключив тяжёлые enhancements. Если isolation текущего parser потребует слишком широких изменений, сравнить его с console `gpu_xbox.c` и выборочно выделить совместимую облегчённую decode path; решение принимать по compile/memory evidence, не переписывать renderer заранее.

Software GTE остаётся CPU-side. Его PC precision callbacks должны иметь отключаемый вариант без огромных GPU tables. Software SPU core сохраняется; NDSP добавляется в существующий sink/dispatch либо через узкий target adapter. Ни SDL, ни OpenAL, ни FFmpeg не должны оказаться обязательными для минимального 3DS link.

### Потоки и время

Сейчас `PsyX_main.cpp` создаёт SDL interrupt/VBlank thread, вызывает callbacks; `libcd.c` имеет CD spooler, SPU adapter использует mutexes, FMV — decode worker/conditions, texture packs и achievements — дополнительные workers. Даже без вызова соответствующей функции compilation/link могут требовать SDL/std thread support.

Начальный вариант: главный game/render thread; input/lifecycle и совместимые callbacks обслуживаются в timing boundary; один audio worker при подключении звука, если main-thread filling не выдерживает deadlines. `LightLock`/events и libctru `threadCreate` использовать через HAL, без busy-wait и тяжёлого I/O внутри audio callback. Не размещать game/GTE state в конкурирующих threads без синхронизации.

Семантику `VSync(-1)`, ожиданий, callback frequency и NTSC/PAL сохранить отдельно от display refresh и render FPS. Не связывать один game tick с одним произвольным `C3D_FrameEnd`. Suspend/lid/HOME должны приостанавливать игровое время и звук без скачка timers после resume. Наличие четырёх cores New 3DS не гарантирует их доступность: ограничения описаны в [libctru thread API](https://github.com/devkitPro/libctru/blob/master/libctru/include/3ds/thread.h).

Bottom screen сначала показывает статус. Позднее отдельный read-only UI renderer читает состояние карты/инвентаря, а команды возвращает через игровой menu/input boundary. Stereo добавлять после mono correctness и производительности; HUD сохранять на screen plane.

## 12. Рекомендуемые библиотеки devkitPro

| Компонент | Назначение и порядок подключения |
|---|---|
| devkitARM + newlib + `3ds_rules`/3ds tools | ARM ELF → `3dsxtool` → `.3dsx`; optional SMDH через `smdhtool`; host инструменты и runtime не смешивать |
| libctru (`-lctru`) | Lifecycle/APT, HID/IRRST, SD FS, timers/threads/synchronization, NDSP, memory/cache operations |
| citro3d (`-lcitro3d`) | Основной PICA200 renderer; vertex shader через picasso, TEV, textures/render targets |
| citro2d (`-lcitro2d`) | Опциональный bottom-screen UI после базового renderer; учитывать общий GPU state/flush с citro3d |
| libm | Уже используемая C math; сохранять стандартную семантику |
| tex3ds | Host conversion собственных UI assets, если нужны; не обязательна для runtime PSX texture decode |

Официальный [application Makefile](https://github.com/devkitPro/3ds-examples/blob/master/templates/application/Makefile) задаёт `-march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft`, `-specs=3dsx.specs` и packaging rule. Это правильная исходная точка для smoke target. Для engine выбрать GNU C11/C++17 по существующим требованиям; template `-fno-exceptions/-fno-rtti` применять после проверки оставшихся C++ callers. При появлении C++ objects link выполнять C++ driver. Зависимости брать согласованным набором devkitPro, зафиксировать версии при первом успешном build.

SDL2/openal-soft/FFmpeg на первом этапе не рекомендуются: наличие ports этих библиотек само по себе не решает PICA renderer, memory и host API problems. Поддержку PNG/JPEG/ZIP добавлять только при конкретной необходимости UI/modding, не ради совпадения desktop link list. Официальные основы: [libctru](https://github.com/devkitPro/libctru), [citro3d](https://github.com/devkitPro/citro3d), [3ds-examples](https://github.com/devkitPro/3ds-examples).

## 13. Поэтапный план реализации

| Этап | Работа | Критерий завершения |
|---|---|---|
| 0. Toolchain smoke | Независимый `3ds_port` target, lifecycle, экранный статус, HID, лог, доступная память | `.3dsx` запускается на New 3DS и штатно возвращается в hbmenu без игровых данных |
| 1. Compile/ABI gate | Явный source manifest; engine/start map/GTE; HAL boundaries; excludes desktop features; layout probes | Каждый выбранный TU компилируется ARM compiler; отсутствуют случайные GL/SDL/OpenAL imports; память проверена по object/ELF map |
| 2. PsyQ/GTE synthetic harness | Timer/pad/VRAM contracts, core GTE vectors, при необходимости counting renderer/audio stubs | Результаты математики/OT/FS статусов совпадают с эталонными synthetic cases, errors наблюдаемы |
| 3. PICA baseline | Собственные triangle/quad/TIM-like patterns, CLUT changes, ABR, clipping, batch lifetime | Рисование hardware-accelerated, порядок и palettes корректны; измерены frame time/cache counters |
| 4. Локальные данные → boot | BIN sector reader, region/file table, startup init и memcard backend; сначала один регион | Логотипы/title и загрузка `map0_s00`, без MIPS execution и без необъяснимых read failures |
| 5. Стартовая playable scene | Streaming, player/controls, collision/camera, bounded allocations | Управляемый персонаж и стабильное время кадра; измеренный memory peak |
| 6. Переходы и полная игра | Сначала две карты; выбрать map residency по ARM linker map, затем остальные | Переходы без роста памяти/висячих pointers, save/load, late-map/boss regression route |
| 7. Audio/FMV | SPU→NDSP, XA pacing/drain, reverb, штатный STR/MDEC и согласованный video output | Музыка/SFX/реплики/FMV с корректной синхронизацией, без систематических underruns |
| 8. Bottom screen | Map/inventory view и touch navigation через существующий UI boundary | Правильные assets/state/pause rules, измерен дополнительный footprint |
| 9. Stereo и optimization | Ограниченный depth/view-space capture, left/right eye, HUD plane; profiling | Корректное stereo, slider=0 даёт mono; подтверждены frame/memory budgets на устройстве |

Аудио можно исследовать параллельно зрелому mono renderer, но полная playable-проверка требует обоих. Не фиксировать желаемые 30 FPS как доказанный результат: сначала измерить worst-case scenes. Проверки — synthetic fixtures без игровых данных плюс ручные маршруты с локальным диском пользователя; desktop audio core tests полезны как reference, но не заменяют ARM/hardware validation.

## 14. Риски и неизвестные

| Приоритет | Риск / неизвестное | Как снять |
|---|---|---|
| Критический | Текущий PsyCross footprint не помещается в разумный `.3dsx` profile | Compile-time feature isolation, ELF `size`/map, измерение normal/linear heap |
| Критический | Полная карта/overlay residency и duplicate symbols | Измерить два ARM overlays, проверить prefix/constructors; сначала static subset, затем bounded state arena или отдельно обоснованный loader |
| Высокий | PC enhancements переплетены с PsyQ compatibility и game hooks | Source manifest + compile/link gate, небольшие guards, API-preserving stubs только для отключённых features |
| Высокий | PSX blending/feedback не совпадёт с PICA | Синтетические ABR/STP/CLUT cases, затем реальные эффекты и pixel comparisons |
| Высокий | CPU GTE + SPU + texture decode перегрузят ARM11 | Измерять раздельно; ограничить cache misses и draw calls; ускорять только обнаруженные hot paths |
| Высокий | Save/stdio collision либо неверный busy/completion | Namespaced PsyQ I/O, synthetic save round-trip, startup без SD/с ошибкой записи |
| Высокий | Извлечённые C tables и resource relocation зависят от региона/ABI | Не регенерировать без собственного диска; проверить provenance, `sizeof/offsetof`, выбранный регион и переходы |
| Средний | NDSP component/launcher memory/CPU permissions различаются | Первый smoke target фиксирует окружение и service results; sound init failure не блокирует диагностику |
| Средний | Stereo depth недоступна после PSX projection | Маленький depth capture prototype только после mono; проверить 2D/world classification |
| Средний | Console ports устарели или содержат экспериментальные ограничения | Сравнивать pinned revisions и зависимости, не считать README test claims собственными результатами |

Не установлены: полный ARM image size, реальная доступная память `.3dsx`, необходимые cache sizes, стоимость SPU/reverb/MDEC, рабочая stereo depth path, совместимость всех карт и регионов. В этой задаче не подтверждалась даже cross-compilation; документ — обоснованный план, не заявление о готовом порте.

## 15. Самый маленький первый milestone с `.3dsx`

**Один самостоятельный data-free executable `silenthill_3ds.3dsx`, пока без запуска `MainLoop()` и без линковки всей игры.** Он проверяет только базовую среду будущего порта:

1. Сборка из devkitPro shell: будущая команда `make -C 3ds_port`; `3ds_rules`, ARMv6K/hard-float ABI, `.elf` и linker map → `.3dsx`, optional `.smdh`.
2. `gfxInitDefault()`, console на bottom screen, собственная заливка/статус сверху; цикл `aptMainLoop()`, HID polling, Start завершает приложение.
3. Показать New3DS detection, результат включения speedup, normal/linear memory statistics и Circle Pad/C-stick values. При отсутствии нужного сервиса — понятный статус, без падения.
4. По возможности создать каталог/короткий диагностический лог на SD; при отсутствии SD всё ещё работать с console. Собственный временный файл позволит проверить stdio, не обращаясь к BIN и saves.
5. Корректно освободить выделенные buffers/services и вернуться в hbmenu. Повторный запуск и закрытие крышки не должны зависать.

Критерий приёмки: `.3dsx` существует, имеет маленький измеренный footprint, запускается **на реальном New Nintendo 3DS**, отображает input/status, завершается и повторно запускается. Build-only успех фиксировать отдельно от hardware acceptance. PICA triangle — следующий небольшой milestone, звук — последующий; оба не нужны для доказательства packaging/lifecycle.

Этот milestone не реализован данным аудитом. Ни игра, ни build scripts, ни upstream `pc-port`, ни submodule revisions в рамках документационной задачи не изменяются.
