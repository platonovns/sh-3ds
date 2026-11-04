# Native FMV checkpoint — 28.10.2026

Статус: самостоятельная реализация для последующей интеграции. Аппаратная
приёмка не выполнялась. Ветка `codex/fmv-native`, изолированный каталог
`silent-hill-fmv/`. Исходная база — commit `518c44a9e`, восстановленный контекст
принятого `stage11a-cpu-B-src-8c51d74ee1feb7e0`; происхождение и SHA архивов
записаны в `fmv-baseline.json`. Точный FMV source ID находится в
`../3ds_port/reports/fmv-source-manifest.json`, commit — в receipt пакета.

## Исходные данные и формат

Единственный источник — пользовательский SLUS-00707 v1.1 BIN/CUE. FMV открывает
собственный `PsxDisc`, проверяет `ShDisc_Init` и разрешает LBA через
`ShDisc_Resolve`. Зафиксированный Stage 2 identity/table CRC исключает незаметное
применение американских ID к другому диску. Длина физического диапазона берётся
из проверенного канонического имени; `blockCount` у XA **не является длиной
файла в секторах**. В checkpoint нет BIN, кадров, PCM, перекодированных роликов
или игровых ресурсов. Отдельный формат/FFmpeg/SDL/OpenGL/libjpeg не требуются.

Найдены 21 файл с видео, суммарно 12860 кадров; девять предшествующих XA voice
банков 2044–2052 видео не содержат и FMV API их отвергает. Полный секторный
inventory: `../3ds_port/reports/fmv-inventory.json`; компактная таблица —
`3ds-fmv-inventory.md`. Все видеопотоки: **320×208, 15 fps, MDEC v2**, одинаковые
4-bit XA stereo **37800 Hz**, file/channel 1/1, coding=1.

Raw sector 2352 B: sync/MSF/mode 0..15; две копии XA subheader 16..23;
STR header 24..55; видеофрагмент **2016 B** с offset 56; остальное — padding/EDC.
STR header LE: magic 0x0160/0x8001, u16 chunk index/count, u32 frame number,
u32 compressed size **в байтах**, u16 width/height, затем 12 служебных байтов.
Кадр занимает восемь или девять видеофрагментов, первый chunk каждого кадра
лежит через десять физических секторов. Frame numbers начинаются с 1.
Frame-size максимум 16000 B; буфер assembly ограничен 18144 B.

На позиции 7 modulo 8 размещён XA sector либо нулевой сектор тишины. XA даёт
2016 stereo frames (4032 int16), то есть 8/150 секунды при 37800 Hz.
Предиктор ADPCM сохраняется между аудиосекторами. В M2 большая часть ролика
без XA, в других файлах встречаются короткие хвосты тишины. Нельзя склеить
только найденные аудиосекторы и считать их всей временной шкалой. M6/M7/ZC/ZZ
имеют хвосты/длины, для которых suffix/10 не равен точному числу кадров.

В старых PC `str_demux` комментариях встречаются 2292-byte chunks и трактовка
frameSize как halfwords. Здесь используются измеренные 2016 B и byte length;
на выбранных кадрах это даёт полный декодируемый поток без чтения padding.

## Контракт игры и продолжение событий

`open_main(file_idx, s16 num_frames)` — синхронный presentation-only вызов.
Перед ним завершается FS queue. Положительный второй аргумент задаёт предельный
номер кадра; ноль соответствует исходному PS1 `blockCount - 7`. Например,
обычный C1 заканчивается на 2060 при 2067 физических кадрах. Альтернативный
вызов C1(2060) **не делает seek к кадру 2060**: комментарий оригинала об offset
не соответствует условию выхода `frame_cnt >= max_frame`. Специальный seek
новая реализация не добавляет. PC BIN player при нуле играет до EOF; это
отличие PC реализации от PS1 контракта явно сохранено в документации.

`game_fmv_play` возвращает DONE=0, SKIPPED=1, APT EXIT=2, ERROR=-1. `open_main`
остаётся void: normal/START/error возвращают управление тому же вызывающему
коду. APT exit вызывает штатный `game3ds_halt` **после** очистки FMV.
Для M4 останавливаются SFX с RR, как в PC path; обычный XA отменяется при
входе в movie, как при смене CD stream. Остальные SPU voices/Core 2 продолжают
работать. Общая SPU архитектура и MIDI-драйвер не изменены.

Intro возвращает в MainMenu, New Game opening — в MainLoadScreen.
`SysState_Fmv_Update` выбирает `FILE_XA_ZC_14392 - g_MapEventParam`, после
возврата выставляет `disabledEventFlag`, переключает InGame и при необходимости
возвращает step=1. Эти callbacks/флаги/школьные события не изменялись.
Inventory содержит статические ссылки на карты. ZC имеет неявный eventParam=0;
для ZZ обычный статический вызов в доступном исходном дереве не найден.
Наличие файла на диске не выдаётся за доказательство его обычного вызова.

## Конвейер, звук и синхронизация

Один FMV worker владеет независимым disc handle, assembly, ADPCM history и
MDEC. Запрашивается Core 3 с priority 0x30, при отказе — default affinity -2.
Фактическая маска процессора записывается в `fmv_last.txt`. Основной поток
владеет NDSP channel 1, очередью вывода, APT/HID и CPU framebuffer.
Все передачи слотов используют acquire/release; pending buffers никогда
не освобождаются до завершения worker и очистки NDSP queue.

Stage 2 `CacheRange` читает максимум 32 raw sectors за приём. Добавлен только
необязательный `PsxDisc_OpenBuffered`; обычный `PsxDisc_Open` сохраняет прежние
настройки. Movie устанавливает stdio buffer 16 секторов **до первого чтения**,
чтобы newlib не дробил SD I/O на мелкие refill. Cache и cursor принадлежат
только movie descriptor, обычные game/audio resource descriptors не меняются.
Весь фильм в RAM не загружается. Очередь — четыре RGB кадра и восемь PCM
секторов, compressed frame только один. Аудио заполняется при demux, decoded
кадры заранее дают около 267 мс video lead; PCM ёмкость около 427 мс.

Video fork использует таблицы и вычисления существующего GPL PC `mdec.c`:
LE halfword/MSB bit reader → MPEG-1 run/level VLC/escape/EOB → quantization →
separable integer IDCT → column-major macroblocks Cr/Cb/Y0/Y1/Y2/Y3 → RGB24.
Нет frame malloc/byteswap copy. Prefix LUT уменьшен с 256 KiB до 2 KiB;
редкие длинные VLC ищутся в небольшой исходной таблице. DC-only IDCT имеет
точный быстрый путь, first-pass temporary — int32 с доказанной границей,
second pass остаётся int64. Неверная версия, размеры, quantizer, VLC,
недостаток bits или нарушенный chunk/frame order завершают movie ошибкой.
`adapt_fmv_mdec.py` воспроизводит fork из неизменённого PC source.

XA использует ровно уже принятый `game_xa_decode`, без второго ADPCM/resampler
движка. PCM идёт в свободный channel 1 существующего NDSP, native 37800 Hz
stereo, serial gain 80/127. Channel 0, ndsp callback, Core 2 SPU и его 44100-Hz
буферы сохраняют владельца. FMV не вызывает ndspInit/Exit и не меняет callback.

Master clock — **реально потреблённые NDSP samples**. PTS кадра
`(frame_number-1)*2520`; PTS XA slot `slot_index*2016`. Прочитанные сектора
без XA и последний неполный audio slot дополняются тишиной до точного
frame-limit ×2520. Double-read wave sequence ID исключает смешивание offset
соседних буферов. Прогресс completed buffers дополняется текущим sample position;
clock не уменьшается. Нет суммирования приблизительных sleeps и накопления
расхождения. При позднем кадре более одного frame period устаревшее изображение
пропускается, demux и аудио продолжаются. При реальном starvation часы стоят
на последнем проигранном sample и возобновляются вместе с PCM; бесконечные
очереди/скрытый drift не возникают. Длительная нехватка CPU/SD может замедлить
воспроизведение и остаётся предметом аппаратного измерения.

Старт после preroll минимум трёх PCM slots и готового первого кадра; аудио
запускается после его presentation. Последний PCM sample ограничен концом
ролика. Отсутствие прогресса 10 секунд вне suspend завершает movie ошибкой.

## Экран и lifecycle

Gameplay GPU flush/wait выполняется перед захватом scanout. Movie пишет
RGB24 в существующий rotated BGR8 top framebuffer: 320×208, x=40/y=16 в
400×240, чёрные поля, пиксель 1:1. Новые PICA shaders/textures/targets не нужны,
VRAM и gameplay render target остаются нетронутыми. После возврата обычный
рендер продолжает представлять свой target. Из game clock исключается время
блокирующего movie; окно игровых timing samples очищается.

START armed только после первого release, затем новый press останавливает
movie. Closing START поглощается до release с ограничением 30 vblanks.
Sleep/HOME hook приостанавливает movie channel/producer; resume возобновляет
их с тем же sample clock и сбрасывает watchdog. Штатный game-audio APT hook
продолжает независимо обслуживать channel 0.

На normal/START/APT/error: abort → join worker → unhook APT → pause/clear/reset
channel 1 → закрыть FILE/cache → освободить linear/heap. Точный порядок
освобождения linear относительно FILE независим: оба освобождаются после
join/clear; stdio memory живёт до fclose. Ошибка открытия/identity/init не
портит существующие disc/SPU descriptors. Итоговые лёгкие счётчики пишутся
в `sdmc:/3ds/silenthill/fmv_last.txt`, нормальный gameplay не профилируется.

## Память

ARM ABI бюджет сохранён в `fmv-arm-compile.json`: **867856 B movie heap** включает четыре
RGB24 по 199680 B, assembly/sector/PCM scratch, private disc state, queue
metadata и 37632 B stdio. Дополнительно 64512 B linear PCM, 75264 B временный
raw cache и 32768 B stack worker. Сумма **1040400 B (около 0,992 MiB)**;
точное число берётся из compiler-generated `game_fmv_memory_budget`.
Нет новых GPU/VRAM allocations. После movie всё это освобождается. Постоянно
остаются только примерно 2 KiB VLC prefix table и малые константные таблицы.
Уже существующие screen buffers и game/SPU/cache memory в эти числа не входят.

## Проверки и пределы результата

`fmv-offline.txt`: полная сборка 12860 кадров из 21 файла; по три RGB кадра
(начало/середина/конец) каждого файла, **63 побайтных совпадения с PC decoder**;
PCM реальных аудиосекторов сравнивается с отдельно извлечённой функцией PC
movie player, sample totals равны длительности каждого movie. ASan/UBSan,
1000 повреждённых VLC inputs, guards выходного RGB — PASS.

`fmv-lifecycle.txt`: production adapter с потоковым SDK test double; 13
сценариев: normal, held/released START skip, sleep/wake, APT exit, thread
failure, affinity fallback, I/O error, bad chunk, bad decode header, нет NDSP,
invalid ID, late presentation, audio starvation/recovery. Проверены join/clear
до free, точный итоговый sample clock и synthetic rotation/BGR/edge pixels.
Эти тесты не моделируют настоящий DSP/GSP/SD service.

`fmv-arm-codec.json`: четыре реальных кадра из C1/M2/M7/Z1 исполняются
скомпонованными ARM1176/VFP инструкциями в Unicorn и совпадают с host RGB;
два последовательных XA sectors — PCM и predictor history совпадают.
`fmv-arm-compile.json`: production и development entry ARM11 objects компилируются.
`fmv-internal-link.json`: полная внутренняя ARM ELF closure со сверенными base
objects и извлечёнными frozen B replacements, без неразрешённых strong symbols.
Внутренние ELF не являются игровой сборкой, не упаковываются в 3DSX и не
публикуются. Historical baseline identity в ELF не используется как FMV ID.

`fmv-throughput.txt`: 15 кадров из пяти файлов ×20 повторов, GCC -O2 x86_64,
CPU-time decode-only, без sanitizers/IO/presentation: **0,46–2,07 мс/кадр**
(примерно 483–2178 fps на хосте). Это **скорость хоста, не New 3DS**. Unicorn wall times также
не являются аппаратной производительностью. Они не доказывают соблюдение
66,67-мс frame budget на консоли.

Аппаратные вопросы для будущей объединённой проверки: реальный decode/upload
budget и Core 3 availability; SD stalls/preroll; NDSP sample-position phase,
отсутствие audible gaps и A/V drift на длинном C1/Z1; top-screen aspect/rotation;
настоящие HOME/sleep/resume и возврат к SPU/resource reads. Initial offline
реализацию эти вопросы не блокируют, hardware acceptance не заявляется.

## Интеграция после Stage 11B и School

1. Сначала сохранить завершённую общую Stage 11B + School source baseline.
2. Применить **только FMV commit/patch после 518c44a9e**, не импортировать
   baseline context commit и не подменять post-11B renderer старыми файлами.
3. Пересечения: `Makefile.game` (include fragment), `main_game.c` (clock/flush
   wrappers + compile-only developer entry), `game_audio.h`/`game_audio_ndsp.c`
   (единственный readiness accessor), `psx_disc.h`/`.c` (optional buffered open),
   `src/screens/stream/stream.c` (вместо presentation skip вызвать FMV).
   Эти маленькие hunks перенести вручную при конфликте. School maps/events,
   GTE, RGB5, texture cache, GPU submission и render_3ds.c не изменялись.
4. Сохранить в объединённой сборке принятые Core 2/F1 defines Stage 11A.
   Подключить `Makefile.fmv` после определения SDK_FLAGS/ENGINE_CFLAGS/OFILES.
   `FMV_NATIVE=1` включает три FMV objects и SH_3DS_FMV. Для исключения пути
   есть `FMV_NATIVE=0`; обычный default fragment — 1.
5. В изолированной копии повторить offline/ARM проверки. Инструменты используют
   существующий локальный toolchain и пользовательский BIN; development-only
   SDK fake не входит в production. `compile_fmv_arm.py` берёт **замороженные**
   flags из `fmv/compile-flags.json`, не mutable Stage 11B build flags.
6. Когда наступит этап аппаратной проверки, `FMV_DEV_MOVIE=2056` позволяет
   вызвать M2 напрямую при boot; IDs 2053/C1, 2058/M4, 2069/Z1 подходят для
   других проверок. Macro существует только в специальной developer сборке,
   после movie приложение завершает test entry, gameplay/save progression
   не запускаются. Сейчас такой 3DSX не создавался.
7. После объединения собрать один явно обозначенный hardware candidate и
   выполнить обязательную публикацию/HTTP manifest-size-SHA проверку согласно
   AGENTS.md. До этого FMV checkpoint не становится default SH Dev Launcher.

Ни принятые Stage 11A artifacts, ни активный Stage 11B/School checkout, ни
опубликованный launcher build этой задачей не изменялись.
