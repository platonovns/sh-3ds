# Content Block 2: Alchemilla Hospital

Независимая ветка `codex/alchemilla-content`, каталог `alchemilla-content/`.
Основа — замороженный Post-school `2782aeb20` (контент `6ae58172b`), который
уже включает School `65ab73346` поверх принятой Stage 11A B. Эта ветка не
сливалась с активной Stage 11B. Точные content commit, Source ID, SHA ELF,
patch/archive и пересечения файлов записываются при запечатывании в
`3ds_port/reports/alchemilla-checkpoint.json`.

## Границы и полное содержимое

Старт — нормальная MAP2_S02 после разводного моста. Оригинальный вход в
больницу: S02 event19/POI17 → MAP3_S00, pose из **S02 point19**. Конец —
восстановленная больница после Lisa и Dahlia, получен Antique Shop Key,
оригинальная S06 event8/POI31 → MAP2_S02, pose из **S06 point1**; обычное
управление перед следующей главой. Ключ магазина сохраняется до его исходного
Use на улице. MAP4_S01 не подключена.

Подключены все семь целых overlays: **MAP3_S00, S01, S02, S03, S04, S05, S06**,
485 исходных событий, оригинальные комнаты/лифты/двери/возвраты, карты и save
points. MAP2_S02 и S04 остаются из Post-school без изменений. Подробные пути,
175 переходов, 16 hospital Inventory Use records и граничный Use ключа магазина:
`3ds-alchemilla-progression.md` и
`3ds_port/reports/alchemilla-content-graph.json`.

Сохранены Basement Key, Plastic Bottle → Unknown Liquid, Turtle/Hatter/Cat/Queen
plates, Blood Pack, Basement Storeroom Key, Alcohol, Lighter, Video Tape,
Examination Room Key, Hammer, Antique Shop Key и исходные расходники/карты.
Pickup accept/decline, осмотр, Use, расход ключей, возврат извлеченных plates
и исходные door flags используют original Status/Inventory. Plate puzzle не
решается автоматически; неверные, неполные и извлеченные placements хранятся
в исходных flags. Blood Pack отвлекает трех Bloodsucker через оригинальный
callback; шкаф/Alcohol/Lighter открывают скрытый проход по исходным условиям.

Unknown Liquid необязательна для прохождения больницы: бутылка заменяется
предметом 102, flag206; жидкость не расходуется и сохраняется для Cybil.
Video Tape/VCR — исходный поврежденный XA/dialog callback, **не FMV decoder**;
flag254 и item остаются под оригинальной логикой. Никакой постоянный skip
этого события не добавлен.

Kaufmann, Alessa, Lisa, Dahlia сохраняют оригинальные actors, DMS, камеры,
сценарии/skip/completion и возврат управления. Creeper, Puppet/Dummy Nurse,
Puppet/Dummy Doctor, Bloodsucker компилируются вместе с исходными spawn,
animation, AI/control, collision и combat callbacks. Босса в блоке нет.

## Совместимость, FMV, звук и сохранения

Минимальные native изменения:

- Resident dispatch семи MAP3, build rules/identity и startup Init новых
  animation tables. Исходные функции игры не заменены портовыми сценами.
- Kaufmann/Lisa/Alessa/Bloodsucker tables и inline Nurse tables имеют native
  function pointers и исключены из PS1 DATA aliases. Nurse tuning сохраняет
  исходные значения всех полей. Для hospital Dahlia добавлена отдельная
  **DAHLIA_M3S06_ANIM_INFOS**: церковная таблица отличается по скоростям и
  не должна подменять ее. Подробности: `3ds-alchemilla-actors.md`.
- В семи headers исправлены повторные designators: slot0xF8 playerStub_F8 и
  slot0x154 charaCollisionReset; они больше не затирают callback0x68/0x104.
- Недостающие declarations/includes, точные pointer casts для original packet,
  rotation и effect interfaces, BGM layer data type; тот же ABI, что в School.
- Desktop proximity pickups, FPS scaling plate cursor/slide и debug logging
  исключены из 3DS; сохранены оригинальные PS1 ветки. Перевод исходного
  COLORS.TIM destination через PSX_ADDR остается включенным.

FMV dependency: **codex/fmv-native / e94a90a6b /
native-fmv-src-59d6e586ef70b529**. MAP3_S00 eventParam13 → M5_03140 (2059),
MAP3_S04 eventParam10 → M8_03039 (2062). Исходные SysState_Fmv/open_main,
block count и completion flags196/293 сохранены. Decoder не дублировался;
изолированный ELF сохраняет унаследованную presentation boundary до интеграции.

DMS HP1F03, DWSTWY, HSPTL3, HSPTL2, XA speech/VCR, BGM/SFX/ambience остаются
оригинальными. Stage 11A SPU/NDSP/Core2 не менялись. Реальный звук, movie
throughput и synchronization требуют последующей совмещенной проверки.

Persistent authority — **636-byte s_Savegame**: inventory, event flags,
maps, world/elevator/generator state, plates, hidden passage, Unknown Liquid,
NPC completion, enemy overlay bits, room/pose и Antique Key. Новых persistent
globals нет. Временные NPC/DMS/camera/puzzle cursor восстанавливаются исходными
init routines; solved state остается в save flags. Memory card transport не менялся.

## Офлайн-проверки и границы доказательств

Результаты: `alchemilla-arm.json`, `alchemilla-actors-arm.json`,
`alchemilla-runtime-arm.json`, `alchemilla-closure.json` и build manifest.
**PASS:** compile/link всех семи overlays, source/data closure, отсутствие
strong unresolved function imports (остаются девять штатных optional SDK weak
hooks), make dry-run семи native targets; **64** ARM component checks, включая
16 Use, ключи, отказ/включение generator, исходную кнопку четвертого этажа,
неверную/занятую/извлеченную/правильную расстановку plates, Bloodsucker init,
Unknown Liquid, hidden passage, FMV API, окончания NPC и **21** original
save/checksum roundtrip с отрицательной проверкой повреждения.
**PASS:** 846 actor table entries, 187 Harry entries против BIN и native
callbacks; 24 Nurse/Doctor damage/death cases на Easy/Normal/Hard.
Это сфокусированные nearby-state
component/resource проверки; полного синтетического прохождения нет.
GPU/SDK/audio и отдельные presentation waits используют обозначенные host
boundaries. Plate draw и map-effects teardown изолированы в компонентных
fixtures; runtime runner отдельно проверяет lifecycle представительных комнат.
Проверки не доказывают непрерывное прохождение, натуральный бой,
изображение, звук, FPS или аппаратную приемку.

Рост ELF sections относительно Post-school: text **+221248**, data **+53000**,
bss **+159128**, всего **+433376 байт**. Это статические sections, не измерение
heap/GPU working set или FPS на New 3DS.

**PASS:** четыре short original MainLoop/BIN checks, каждый с **20**
завершенными InGame updates в SysState_Gameplay и доступным управлением:
normal S00 room1 (S02 point19), Otherworld S03 room38 (MAP3_S02 point15), restored S06 room3 (MAP3_S04 point39), конечная
MAP2_S02 room15 (MAP3_S06 point1). Во всех случаях failure/invalid/exception
отсутствуют. Входы — явно синтетические nearby save-like fixtures с нужными
исходными flags; это не запись непрерывного пути между четырьмя комнатами.

Риски для принятой Stage 11B: MAP3_S02 world transition (`func_800D0608`)
использует original DR_AREA/DR_OFFSET/STP и экранные sprites; проверить границы
кадра/feedback после сцены Alessa. MAP3_S03 plate UI загружает COLORS.TIM и
смешивает textured sprites; проверить puzzle overlay и возврат к миру.
MAP3_S05 burning vines/hidden area содержит эффекты и частицы; проверить
освещение, texture lifetime и командный поток. Во всех MAP3 новые сцены DMS
и Nurse groups увеличивают resident sections и рабочие ресурсы. Это статические
риски, не наблюденные аппаратные дефекты. Renderer/PICA/RGB5/readback/feedback,
GTE/geometry/cache/GPU sync/profiler/uploader здесь не редактировались.

## Интеграция в будущую принятую Stage 11B

1. Начать отдельную integration branch от **будущей принятой Stage 11B**.
   Применить School `65ab73346` по его handoff; не переносить восстановленную
   11A baseline историю из этой ветки.
2. Применить Native-FMV `e94a90a6b` и Post-school content/audit diff
   `44997c1f3..6ae58172b` по их handoffs. Сохранить принятые Stage 11B
   renderer/audio/SDK/main objects и wrappers.
3. Применить только **`2782aeb20..<Alchemilla content commit>`**:
   `git apply --3way ../alchemilla-checkpoints/20261028/content.patch`.
   Content commit и hash patch находятся в receipt. Родительские School,
   Post-school и 11A commits повторно не сливать.
4. В Makefile.game сохранить все include: School/Post-school/Alchemilla до
   OFILES, соответствующие LDFLAGS после их определения и Native-FMV include
   в требуемом FMV месте. В game_map сохранить все прежние maps и добавить
   MAP3_S00..06; в game_native сохранить прежние Init и добавить новые.
   native_overlay exclusions и build identity списки объединять добавлением.
   Точные пересечения School/Post-school/Native-FMV и срез Stage 11B находятся
   в receipt; это не обещание отсутствия новых конфликтов после дальнейшей 11B.
5. Пересобрать новые MAP3/таблицы и затронутые dispatch/native source **с
   принятыми 11B flags и engine objects**. Архивный internal ELF служит офлайн
   свидетельством, не заменяет аппаратную сборку. Выполнить focused checks,
   совместить FMV и провести непрерывное реальное прохождение до street control.
6. Только на той будущей стадии создать одну совмещенную `.3dsx`, опубликовать
   через штатный launcher/server и выполнить hardware acceptance.

Офлайн-воспроизведение в текущем расположении: подготовить зависимости через
`prepare_alchemilla_offline.py`, затем `build_alchemilla.py`,
`test_alchemilla_arm.py`, `test_alchemilla_actors.py --game-elf
build/alchemilla/alchemilla-content.elf`, `test_alchemilla_runtime.py`.
`run_alchemilla_offline.sh` задает локальные devkitARM paths под Ubuntu WSL.
Подлинный BIN предоставляется локально для проверок и в checkpoint не входит.

`.3dsx` не создана; launcher не заменен; публикация не выполнялась.

Точные общие файлы с **School** и отдельно с **Post-school** совпадают:
`3ds_port/Makefile.game`, `3ds_port/source/game_map.c`,
`3ds_port/source/game_native.c`, `3ds_port/tools/build_identity.py`,
`3ds_port/tools/native_overlay.py`. С **Native-FMV** пересекается только
`3ds_port/Makefile.game`. Все остальные Alchemilla edits добавляются отдельно;
повторно используемые Creeper/Dahlia church исходники не изменены.
