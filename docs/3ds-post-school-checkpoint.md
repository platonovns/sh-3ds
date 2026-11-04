# После школы: церковь и разводной мост

Независимый **offline integration checkpoint**, ветка
`codex/post-school-content`, рабочее дерево `post-school-content/`.
Source ID: **post-school-content-src-d9f536f248445526**.
Content commit: **6ae58172b0967c6b43d92e4b532fa2fca6c1ce6d**;
предшествующий audit commit: **1ab128d4d**. Эти два commit после `44997c1f3`
составляют переносимый content diff. Последующий receipt commit — только документы.
Внутренний ELF SHA-256:
`4c4a681a007fa3dca1b10a784efcaff0bab6f46d9bf6a46221158b04e3e5bf8f`.
Точный content commit, архив/patch SHA и пересечения сохранены в
`3ds_port/reports/post-school-checkpoint.json` после запечатывания.

Архив: `../post-school-checkpoints/20261028/post-school-checkpoint.zip`,
16927222 байта, 746 проверенных snapshot files; SHA-256
`efa3303dcf8a6b4792fc652d692093ba7beebdc68fcdd9be634263e36aad5eda`.
Patch SHA-256:
`e43dd3766c1a9f0fa01a6bb71147f1f4137828ce9fcaeac715e34633276eaadb`.
Побайтная проверка каждого архивного файла и reverse patch check — PASS.
При запечатывании в изменённых здесь существующих путях отличий активного
checkout от frozen 11A B не найдено; это снимок текущего состояния, а не
гарантия отсутствия будущих пересечений Stage 11B.

Основа — School `65ab73346` + документирующий `44997c1f3`, с принятым CPU
baseline Stage 11A B. FMV `e94a90a6b` ещё не применён. В Stage 11B ничего не
сливалось. `.3dsx` не создавался, публикации и замены launcher build нет.

## Выбранная глава и её покрытие

**Старт:** MAP2_S00 после школьных 132/134, с исходным K. Gordon Key.
**Конец:** MAP2_S02, normal Central Silent Hill, управление за разводным мостом;
следующая задача — путь к больнице и Alchemilla. В проверке это room 12.
Оригинальный S00 point 55 запускает переход, **destination pose берётся из
S00 point 56 до смены overlay**, а не из точки 56 нового S02. Это существенная
особенность retail dispatcher; у S02 всего 46 points.

Целая сюжетная цепочка: выход из школы → дом K. Gordon → Balkan Church →
Далия/Flauros/Drawbridge Key → пульт/выбор выключателя/движение моста → новый
район с обычным управлением. После пересечения моста глава останавливается;
дальнейшая больница не подключается ради искусственного расширения блока.

| Карта | Что подключено |
|---|---|
| MAP2_S00 | Уже resident в принятой базе: оригинальные дом/замок K. Gordon, наружные улицы, церковный вход, пульт, обе ветки запуска моста, мостовые collision/world-object states. Ни событие, ни геометрия не заменены shortcut |
| MAP0_S02 | Уже resident: оригинальные доступные интерьеры Old Silent Hill, в том числе соответствующая дому ветка, save и расходники |
| **MAP2_S01** | Новый resident overlay: вся церковь, Dahlia scripted actor, исходный DMS/dialog/START автомат, Flauros и Drawbridge Key, расходник, осмотр/замки, save point. **27 event records** |
| **MAP2_S02** | Новый resident overlay: полные улицы Central Silent Hill, спавны, предметы, возврат на мост, полиция, исходные запертые/поздние ветки hospital/antique. **41 event record** |
| **MAP2_S04** | Новый resident overlay: полный полицейский участок, обе доступные комнаты/осмотр/memos, карта, запасной Shotgun, расходники, save и исходные normal/alternate exits. **27 event records** |

Итого **95 новых событий**; все соответствующие original source files,
player/particle/animation/event/header/spawn/camera/point data включены.
Полиция — необязательная ветка полного района прибытия, она не продвигает
сюжет больницы. MAP2_S03 — исходный `NO_STAGE!`, нормальных входов нет;
он намеренно не добавлен.

Соседние главы остаются вне closure: MAP3_S00/MAP3_S06 и MAP4_S01,
поздний alternate exit полиции → MAP4_S02, sewer → MAP5_S00. Двери и условия
не переписаны ради этого checkpoint. Это частичное покрытие игры, не релиз,
в котором предлагается проходить дальше указанных границ.

## Предметы, события, враги, сохранения

- **K. Gordon Key** проходит исходный Inventory → Use handshake; original
  callback расходует ключ, открывает дверь и ставит карту/прогресс флаги.
- **Flauros** и **Drawbridge Key** используют Event_ItemTake/исходный Status,
  предметные модели UNQ64/UNQ48 уже поддержаны общим inventory code.
  Подтверждение/отказ, pickup flags и inventory grant остаются оригинальными.
  Flauros сохраняется для позднего сюжета, не превращается в произвольный Use.
- **Drawbridge Key → пульт** остаётся item trigger, затем original диалог
  подтверждения и движение моста. 164 — механизм активирован, 165/166 —
  завершение/открытое состояние. Исходник не удаляет этот ключ из inventory
  в этом callback; дополнительный расход не изобретался. Отказ от выключателя
  не открывает мост, повторная ветка включения тоже сохранена.
- **Полиция:** оригинальные memo/карта и запасной Shotgun с общим школьным
  pickup-флагом, чтобы не выдавать второе оружие. Двери/замки не обходятся.
- Новый **Romper** подключён полным исходным AI, native dispatch, spawn,
  movement/collision/jump/grab/attacks/player damage/weapon damage/death через
  существующий combat engine. Air Screamer/Groaner используют прежние native
  реализации. Нового босса в выбранном блоке нет.
- Новая **Dahlia** использует исходный actor/event/DMS control. Завершение
  диалога ставит 179/176 и hospital map marks, освобождает управление/камеру.
  Входной FMV ставит 181; во время сцены используется 182.

Persistent state остаётся в original **636-byte s_Savegame**: inventory,
eventFlags, paper maps, map/room/position, overlay enemy bits. Новых постоянных
портовых глобальных полей нет. При загрузке Map_WorldObjectsInit заново
восстанавливает bridge angle из 166; сохранённое прохождение не зависит от
случайного содержимого D_800F5344. Временные DMS timer/camera/NPC данные
переинициализируются исходными процедурами. Memory-card transport не менялся.

## FMV и изолированные compatibility changes

MAP2_S01 MAP_EVENTS[1]: **SysState_Fmv, eventParam 12 → FILE_XA_M6_02112**
(USA file ID 2060). После возврата исходный SysState_Fmv_Update ставит 181 и
сцена Далии продолжает progression. Вызов open_main сохранён. Его реализация
после интеграции — **codex/fmv-native / e94a90a6b /
native-fmv-src-59d6e586ef70b529**. Новый movie stub/decoder или permanent skip
не добавлялся. Историческая presentation boundary этой изолированной базы
осталась прежней; до FMV-интеграции этот ELF не является финальным gameplay
кандидатом. CHRC.DMS/ANM/обычная XA речь — отдельные исходные зависимости.

Минимальные правки:

- Resident dispatch трёх overlay в game_map; два Init в game_native;
  post_school_sources.mk; точное добавление новых исходников в build identity.
- DAHLIA_ANIM_INFOS (52) и ROMPER_ANIM_INFOS (44) — существующие seed tables
  pc_port с native function pointers. Они исключены из PS1 DATA aliases.
  Их байты проверены против соответствующих original BIN; тождество другим
  поздним версиям таблиц этим checkpoint не утверждается.
- В новых header исправлены повторные поля на playerStub_F8 (0xF8) и
  charaCollisionReset (0x154), чтобы не затирать соседние callback.
- Недостающие declarations/includes, BGM layer-limits cast и два согласования
  VECTOR/SVECTOR в Dahlia. Размеры и original state machine не менялись.
- 3DS использует исходные chunk checks для pickup; desktop proximity helpers
  исключены. В Romper desktop-only FPS corrections/logging исключены для
  3DS, остаются оригинальные PS1 ветки. Native AI dispatch table сохраняется.
- Две variable-duration записи Harry в S02 инициализируются нативной функцией
  сразу, по существующей ARM схеме; Windows constructor shim остаётся Windows.

Renderer/PICA, RGB5, feedback/readback, GTE, texture cache, GPU sync,
профилировщик/uploader Stage 11B и SPU Core 2 не редактировались.

## Офлайн-проверки и ограничения

- **PASS:** compile/link трёх native overlay и всего internal ELF с проверкой
  SHA неизменяемых School/11A B objects. Нет неразрешённых function imports.
- **PASS:** `make -n` по трём точным absolute native targets подтверждает
  интеграционные правила Makefile без исполнения сборки или after_build.
- **31 ARM component checks:** 295 original event records нового блока и S00,
  callback pointers, три Use handshake (включая сохранённый future antique lock),
  K. Gordon consumption, pickup accept/decline, original M6 API/flag return,
  normal/START completion Далии, timed bridge motion/decline/completion,
  **96** animation records против retail BIN, Harry variable pointers,
  Romper damage/death Easy/Normal/Hard, пять full save/checksum roundtrips,
  два восстановления геометрии моста после очистки временного значения.
- **Три short runtime checks:** original MainLoop, настоящий BIN, retail map,
  ANM/IPD loading/init/update; церковь room 1, город room 12, полиция room 14;
  по **20 завершённых original InGame update** с SysState_Gameplay и доступным
  управлением. Входы — явно синтетические nearby states. Начальная ошибочная
  fixture пыталась брать point 56 из S02; исправлена на original source S00
  arrival pose, игровой код для этого не менялся.

Отчёты: `post-school-arm.json`, `post-school-runtime-arm.json`,
`remaining-game-coverage.json`, `stage6-map2_s01/02/04-symbols.json` в
`3ds_port/reports/`. Это компонентные/ресурсные проверки, не непрерывное
прохождение. Dialog selection, audio, GPU/SDK и floor для damage fixture
используют обозначенные host boundaries. Реальные hit geometry/естественный
бой, все прогулки/комнаты/START моменты, изображение/звук и FPS/память на New
3DS требуют поздней совмещённой проверки. Ни новых graphics bugs, ни
производительности эти тесты не доказывают.

Рост ELF sections относительно School: text +133192, data +34632,
bss +65272 байт, всего **+233096 байт**. Это статические sections, не runtime
working set и не оценка heap/GPU memory на консоли.

## Интеграция в будущую принятую Stage 11B

1. Сохранить отдельную интеграционную ветку от **будущей принятой 11B**, не
   использовать эту 11A-копию как графическую основу. Применить School content
   commit `65ab73346` по его инструкции, не baseline recovery `6679d655a`.
2. Применить Native-FMV content `e94a90a6b` после его context base `518c44a9e`.
   Сохранить принятые 11B main/render/audio changes и его FMV adapters.
3. Применить **только diff `44997c1f3..<content_commit>`** этой ветки —
   `content.patch` в архиве; он включает audit/roadmap и контент. Не переносить
   родительскую историю/весь baseline. Если School уже применён как equivalent
   patch, наличие `44997c1f3` в истории не требуется: это база создания diff.
   Для локального расположения архива, из интеграционного checkout:

   ```text
   git apply --3way ../post-school-checkpoints/20261028/content.patch
   ```

   Либо cherry-pick двух content/audit commits после `44997c1f3`, перечисленных
   в истории ветки до `content_commit` из receipt. Документирующий receipt
   commit можно перенести отдельно; исходники игры он не меняет.
4. Общие файлы с School: **Makefile.game, game_map.c, game_native.c,
   native_overlay.py, build_identity.py**. Это дополнения поверх школьных:
   оставить школьные шесть overlay/четыре Init и добавить три overlay/два Init.
   В active Stage 11B потенциально общие build/dispatch/identity файлы;
   точное source comparison на момент запечатывания есть в checkpoint JSON.
5. С Native-FMV пересекается **только Makefile.game**. Оставить его FMV include
   на нужном месте после SDK/OFILES definitions. Наш post_school_sources.mk
   включается рядом с school_sources.mk **до OFILES**, POST_SCHOOL_LDFLAGS —
   после базового LDFLAGS. Эти include не должны заменять друг друга.
6. Взять CORE/SDK/render/audio objects, compiler flags и linker wrappers из
   принятой **11B**. Перекомпилировать game_map/game_native; добавить S01/S02/S04
   native objects и три `.native.ld`, dahlia_anim_infos.o/romper_anim_infos.o.
   При custom linker переносить именно эту content closure. Изменённый общий
   BGM include влияет и на будущие S04/S06 карты, поэтому dependency rebuild
   обязателен. Character data/AI изменения сохраняются общими для дальнейших глав.
7. Проверить полный новый source identity, compile/link, эти focused ARM checks
   и Native-FMV checks. `build_post_school.py` — **исторический internal ELF
   oracle**, не команда получения post-11B кандидата и не источник старых
   renderer objects для него. Пересобрать проверки под совмещённый ELF/флаги.
8. Только на последующей согласованной стадии создать **один combined 3DSX**,
   выполнить обычную обязательную публикацию/HTTP manifest-size-SHA проверку и
   hardware playthrough от школы до стабильного управления за мостом. В этой
   задаче аппаратная проверка/публикация не выполняется.

Воспроизведение здесь: подготовить existing local devkitARM/libctru env;
при отсутствии private inputs запустить `tools/prepare_post_school_offline.py`,
затем из `3ds_port`:

```text
python3 tools/build_post_school.py
python3 tools/test_post_school_arm.py
python3 tools/test_post_school_runtime.py
```

Первый script создаёт только `build/post-school/post-school-content.elf`.
Для sealed checkpoint сохранить source/report snapshot и School/frozen object
hashes. ZIP не содержит BIN/CUE, пользовательских сохранений или `.3dsx`.
