"""Russian morning handoff, numbers read from exact released candidates and evidence."""
import json
from pathlib import Path
PORT=Path(__file__).resolve().parents[1];ROOT=PORT.parent
def read(name):return json.loads((PORT/'reports'/name).read_text(encoding='utf-8-sig'))
a,b=[read('stage11a-cpu-'+label+'-candidate.json') for label in ('A','B')]
bench=read('stage11a-cpu-arm-bench.json');host=read('stage11a-cpu-spu-bench.json');reg=read('stage11a-cpu-regression.json');cafe=read('stage11a-cafe-classification.json')
assert all(x['status']=='PASS' for x in reg['cases']) and cafe['map']==1
table='| Нагрузка ARM, 512 frames | F1: инструкции | CPU: инструкции | Изменение |\n|---|---:|---:|---:|\n'
for x,y in zip(bench['results']['F1']['rows'],bench['results']['CPU']['rows']):
 table+=f"| {x['workload']} | {x['instructions']:,} | {y['instructions']:,} | {(y['instructions']/x['instructions']-1)*100:.3f}% |\n"
host_table='| Host synthetic | F1 median µs | CPU median µs | F1 min–max | CPU min–max |\n|---|---:|---:|---:|---:|\n'
for x,y in zip(host['results']['F1'],host['results']['CPU']):
 host_table+=f"| {x['workload']} | {x['median_us']:.3f} | {y['median_us']:.3f} | {x['min_us']:.3f}–{x['max_us']:.3f} | {y['min_us']:.3f}–{y['max_us']:.3f} |\n"
build_table='| Кандидат | Embedded ID / source identity | Размер | SHA-256 .3dsx |\n|---|---|---:|---|\n'
for label,r in zip(('A','B'),(a,b)):build_table+=f"| {label} | `{r['build']}` | {r['size']} | `{r['sha256']}` |\n"
heavy=[s for s in cafe['submissions'] if s['primitives']>100]
single=int(cafe['batch_primitive_histogram'].get('1',0));batches=sum(cafe['batch_primitive_histogram'].values())
body=f'''# Stage 11A: ночной CPU pass, 28.10.2026

Достигнут следующий рубеж аппаратной проверки. A/B подготовлены; Stage 11A
**не завершён и не принят**. Stage 11B не реализовывался. Качественные отзывы
пользователя о F1 не превращены в измеренные аппаратные performance claims.

1. **SPU lifetime: владелец установлен.** В аппаратной паре 011/012 при той же
   школьной позе выросла работа молчащих voices с ненулевым pitch: 3 → 24,
   SPU block 1.8673 → 6.4567 мс. Число когда-либо KeyOn осталось 3. Title
   сохраняет это состояние, process restart его сбрасывает. Рост heap/cache,
   числа primitives или decode requests эту пару не объясняет. Старый Stage 10
   уже демонстрировал дорогой SPU; новая диагностика не является единственным
   источником проблемы. P0 не вернул холодную школьную скорость.

   **Точный writer на физической консоли всё ещё не подтверждён трассой.**
   ARM воспроизводит `control_change(0,1,0) → pitch_calc → SpuSetVoiceAttr`
   для всех 24 voices без KeyOn, в том числе в frozen R6. Это доказанный
   локальный путь и правдоподобное объяснение школьного события, а не запись
   реального школьного call path. Низкообъёмная трасса оставлена для утра.

2. **F1 остаётся ведущим вариантом и теперь включён по умолчанию.** F0 сохранён
   на SELECT+← вне recording window. Pitch/MIDI, KeyOn и reset не подавляются.
   Декодеры продвигаются с исходной sample chronology; идентичные never-KeyOn
   machines объединяются только в доказанном стационарном zero-envelope случае.
   Нет reset на Title и нет безусловного пропуска `env=0`. Положительная
   качественная проверка F1 сохранена как свидетельство, не как приёмка.

3. **Дальнейший SPU pass:** пары ADPCM nibbles с сохранением промежуточной
   saturation/history и ARM SSAT вместо ветвящегося int32→int16 clamp.
   Ширины mixer/interpolation, округления, reverb, ADSR и pitch не упрощались.
   Исполненные ARM-инструкции в точных ELF, один измеренный блок после прогрева:

{table}
   Это instruction counts Unicorn ARM1176, **не миллисекунды New 3DS**.
   Реальные VAB/KDT входят в ARM fixture; reverb_sfx включает исходный reverb
   и в этом fixture совпал по стоимости с sfx4. Блоки PCM совпали побайтно.
   Отдельный host benchmark: 7 повторов, 480 измеренных блоков по 512 frames;
   музыка здесь synthetic music-like, а не retail KDT:

{host_table}
   Host elapsed подвержен шуму и не определяет выбор оптимизации ARM11.
   Сохранён также первоначальный шумный прогон. Решение оставить изменение
   опирается на точность и детерминированное сокращение ARM-инструкций;
   аппаратная длительность блока остаётся открытой.

4. **PCM/state:** 1 984 checkpoints, 1 077 117 648 сериализованных байт на режим
   frozen/F0/F1 — точное совпадение. Покрыты RAM/reverb overlap, конец ADPCM,
   PMON/noise/sweeps, split/null output, границы RR, изменения регистров и будущий
   KeyOn. ARM whole native core: 531 064 байта, одинаковый SHA в F0/F1.
   9 retail SFX cases совпали с сохранённым oracle; все 726 XA requests,
   simultaneous KDT, 30/unlocked PCM, seek/cancel/stop прошли. NDSP:
   44.1 kHz stereo PCM16, 4×512 frames; pause nesting и join-before-free верны.

5. **Core 2:** B переносит целиком существующий SPU worker. A сохраняет `-2`
   (на прежнем New 3DS наследовался Core 0), B запрашивает 2. Stack 32 KiB,
   priority 0x18, queue и XA thread прежние. ARM ABI проверил оба аргумента.
   Requested/observed core, block/render histograms, p95/p99 intervals/max,
   budget exceedances, depths, starves/drop и main/SPU lock waits записываются
   существующим recorder. Фактическое выполнение B на Core 2 и его выигрыш
   **не доказаны эмулятором**. B остаётся экспериментальным аппаратным A/B.
   Старый аппаратный one-shot probe уже исполнялся на Core 2
   (`cpu_probe_2=1,1,2,0`); это подтверждает доступность ядра в том окружении,
   но не стоимость и надёжность полного SPU worker.

6. **Фонарь, CPU:** dirty image теперь сохраняет консервативное объединение
   8×8 tile bounds. Любая затронутая CLUT требует полного decode; последующая
   запись учитывается даже у уже dirty entry. Decoder обновляет только эти
   тайлы существующего output; CPU cache flush ограничен одним выровненным
   диапазоном, включающим все изменённые тайлы. Каноническая VRAM, поколения,
   STP/mask, копирования и GPU fences сохранены. Нет GPU-resident feedback.

   ASan/UBSan: 7 680 multi-write transactions, 4 164 partial uploads — точны
   полной декодировке; плюс исходные 99 decode pages, 1 800 RGB5 resolves и
   8 388 608 feedback color/modulation cases. Синтетическая запись 320×224
   затрагивает 1 120 вместо 2 048 тайлов двух 16-bit pages. Это объём работы
   конкретного offline случая, не измеренное ускорение школьного кадра.

7. **Cafe:** один pin/acquire на уникальный `(page,CLUT)` внутри submission;
   все resident keys закрепляются до misses. Повторные draws получают тот же
   указатель. Порядок и существующее adjacent batching сохранены. Renderer
   пропускает одинаковый нормализованный scissor; state cache инвалидируется
   на frame boundaries. 3 000 ARM draw-команд сохранили один SHA потока,
   pin/acquire 3 000 → 24 в fixture; allocations 8 → 8. Scissor: 102 400
   сравнений с frozen F1, SDK calls 16 616 → 2 071 при одинаковом результате.

   Подлинный nearby Cafe **map 1** классифицирован отдельно: {len(cafe['commands'])}
   primitives, {len(cafe['submissions'])} submissions; в непустой сцене
   {min(s['primitives'] for s in heavy)}–{max(s['primitives'] for s in heavy)}
   primitives и {min(s['keys'] for s in heavy)}–{max(s['keys'] for s in heavy)}
   ключей. Single-primitive batches: {single}/{batches}. JSON содержит producer
   (packet-link caller), тип, page/CLUT, ABR, palette STP hint, mask/scissor и
   причины разрыва batch. Hint покрывает всю live palette, не фактический
   raster footprint. У неназванных producers effect/fog остаётся unresolved.
   Это начало сцены, не полный Cybil dialogue и не аппаратное время.
   Ранний ошибочный MAP0 probe исключён из Cafe результатов.
   У `Gfx_MeshDraw` 18 392 opaque G4 и 18 392 additive textured GT4:
   чередование ordered color/texture passes объясняет большую долю одиночных
   batches. Удаление ABR bits из key не уменьшило unique keys данного trace;
   этот вариант не добавлялся в runtime. Объединение самих passes — отдельная
   гипотеза Stage 11B с pixel oracle, не ночная реализация.

8. **CPU/GTE:** pure leading-zero helper заменён на guarded builtin CLZ.
   Все 33 класса старого smear-алгоритма и 2 000 000 uint32 значений точны;
   8 271 результатов linked ARM normalization/division совпали. Helper:
   14 → 2 ARM instructions including return. Matrix/FIFO/FLAG и порядок
   последовательных GTE операций сохранены. Массовую memoization матриц или
   transforms не вводил: одинаковые входные vectors ещё не доказывают равенство
   полного состояния глобальных регистров. World/update, primitive conversion
   и количество draw-команд остаются кандидатами на следующий профиль.

9. **Core 3:** production job и кандидат C не созданы. После частичного decode
   нет свежего аппаратного доказательства выгодной coarse задачи. Immutable
   image/CLUT snapshot, отдельный output, generation check и ожидание перед
   GPU submission требуют копирования/памяти/синхронизации. Citro3D остаётся
   на renderer thread. Следующий шаг — измерить остаточную decode стоимость A.

10. **Память:** A/B BSS 6 907 092 байта: +12 672 к F1 trace+fix. Data одинакова,
    150 332 байта; text A 1 144 012, B 1 143 996. Новых heap/linear/VRAM
    allocations и новых threads нет; SPU object layout прежний. Дополнение
    относится к bounded draw metadata/dirty bounds/state. Hardware 011→012:
    heap used 487 880, free chunks 28 160, linear free 15 278 848, VRAM free
    3 426 304, cache 47, renderer textures 48, threads 6 — стабильны. Это
    не абсолютное доказательство отсутствия любой утечки вне тех окон.
    Largest contiguous linear/VRAM allocation API недоступен: разрушающих
    пробных allocations в игре нет. Новое долгое memory поведение ждёт New 3DS.

11. **Регрессии:** {len(reg['cases'])} групп ARM прошли на точном A или явных
    nearby scene probes с теми же CPU объектами. Boot/Title/New Game/MAP0,
    packet limits, Status, feedback transitions, particles/lines/lens, controls,
    pause, inventory, town/school load на disposable copies, Cafe и normal/quick
    reload проверены. Map binding проверен; полного нового визуального map
    roundtrip здесь не заявляю. Звук и suspend/resume SDK lifecycle имеют
    отдельные тесты. Golden card SHA сохранён. Аппаратные sleep/audio/GPU
    fidelity и длительное падение FPS автоматическими ARM tests не принимаются.
    Дополнительно прошли 100 000 cache churn cycles и ASan/UBSan card tests:
    cross-process persistence, 9 повреждённых образов, interrupted replacement
    и failed-write preservation. Оба опубликованных .3dsx дошли до Title в
    Azahar с first_failure=0. NDSP там не запустился: `ndspInit=-662657030`,
    точно как у сохранённого F1. Это Boot/Title check без аудио и без запуска
    Core 2 SPU worker; визуальная приёмка также не заявляется.

12. **Неудачные проверки/непринятые выводы:** ранний host timing был шумным;
    его нельзя выдавать за ускорение. Внутренний scene relink сначала не
    заменял вложенные engine objects и попадал в MAP0; добавлены symbol/map
    assertions, правильный Cafe прогнан заново. Старый inventory runner ждал
    Cafe без маршрута из MAP0: использован явный cleared-Cafe probe. Проверка
    embedded ID поймала stale main object; cache dependency исправлена до
    выпуска .3dsx. Ни один из этих внутренних ELF не опубликован как игра.
    Не оставлено мёртвых runtime вариантов неуспешной оптимизации.

13. **Аппаратные кандидаты:**

{build_table}
    Source provenance и hashes всех исходных/base objects находятся в manifest
    каждого кандидата; F1 checkpoint и frozen Stage 10 сохранены. Сервер имеет
    проверенные `/candidates/A/` и `/candidates/B/`, default A.

14. **Точная разница A/B:** 20 частных CPU objects побайтно одинаковы. Различны
    только `main_game.o` (embedded ID) и `game_audio_ndsp.o` (core argument).
    Все base objects и исходные source hashes одинаковы. Между A/B не менялись
    SPU алгоритм, renderer, XA, priority, block size, диагностический режим или
    сценарий cold default F1.

15. **Утро:** инструкция [STAGE11A-CPU-MORNING-RU.md](../3ds_port/reports/STAGE11A-CPU-MORNING-RU.md).
    A: school ON early/через две минуты, Title→New Game; B: та же школа.
    Затем коротко outdoor/Cafe/town и звук. SELECT+↓ пишет 20–30 s окна.
    Один PC selector загружает B; затем launcher backup переключает A/B без SD.
    После всех запусков можно забрать логи одним пакетом. Анализатор выводит
    percentile intervals с реальной шириной histogram bucket 0.1 мс.

16. **Новая provisional CPU модель:** текущих аппаратных F1 timing windows
    ещё нет. Исторические F0 school 011: update 8.6654, world 7.0245,
    primitive 11.3441, decode 4.1486, flush 0.9919, command 2.2005 мс/кадр;
    это inclusive/preempted scopes, не слагаемые. Старый degraded Cafe 003:
    command 27.6251 мс и около 1 509 batches/frame — историческая мотивация,
    не прогноз текущего F1. Qualitative hardware F1, Azahar checkpoints,
    host elapsed и ARM instruction counts хранятся раздельно. Новую абсолютную
    стоимость SPU/world/GTE/resolve/decode/commands/XA/resource даст утренний
    recorder, а не пересчёт процентов старой деградировавшей модели.
    [Stage 11B handoff](3ds-stage11b-cpu-handoff.md) обновлён; реализации нет.

17. **Что мешает приёмке:** аппаратная длительная стабильность fast path и
    block mean/tails, переход Title→New Game, слуховая проверка SFX/music/XA и
    будущих KeyOn, наблюдённое ядро/очереди/lock tails B и новые CONTROL окна.
    Реальный школьный writer нужно разрешить по оставленной pitch trace.
    Диагностика bounded: ring 64 events, history 32, никаких растущих списков;
    внутренний per-sample SPU profiler выключен. Это исключает её накопление
    как объяснение обнаруженного роста, но не доказывает нулевую постоянную
    стоимость: P0/P1 сравнение при необходимости остаётся доступным.
'''
(ROOT/'docs/3ds-stage11a-cpu-overnight.md').write_text(body,encoding='utf-8')
print('docs/3ds-stage11a-cpu-overnight.md')
