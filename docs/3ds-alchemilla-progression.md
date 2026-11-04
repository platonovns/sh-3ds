# Alchemilla: targeted progression audit

Срез: 28.10.2026, исходники MAP3_S00..MAP3_S06 и только граничные события MAP2_S02. Это уточнение существующего `3ds_port/reports/remaining-game-coverage.json`, а не повторный аудит оставшейся игры. Машиночитаемый граф находится в `3ds_port/reports/alchemilla-content-graph.json`. Аппаратная приемка и достижимость всех ветвей из конкретного сохранения этим анализом не утверждаются.

## Две важные особенности данных

1. `SysState_LoadOverlay` меняет `g_SavegamePtr->mapIdx` и вызывает `GameBoot_MapLoad`. `SysState_LoadRoom` сохраняет overlay, а его поле `mapIdx` передает в `Bgm_TrackChange`. Это видно в `src/bodyprog/events/game_sys_states.c:1259`. Нельзя превращать каждое имя `MapIdx_*` в переход главы.
2. Базовый coverage ошибочно разрешает 16 callback labels в MAP3_S01. Источник истины — порядок `g_MapEventFuncs` в `map3_s01_header.c:23`: 5 elevator, 6 осмотр жидкости, 7 использование бутылки, 8 получение бутылки, 9 hospital map, 10 basement map, 11 basement key, 12 generator, 13 newspaper, 14 generator already on. Исходная event table правильная; исправлять ее по ошибочным labels отчета нельзя. Targeted graph берет callbacks непосредственно из header.

Примеры ложных межглавных переходов: MAP3_S00 event 6 с `mapIdx=MAP6_S01`; MAP3_S02 event 1 с `MAP0_S02`; MAP3_S04 event 10 с `MAP5_S02`; MAP3_S06 events 23..26, 29..30 с `MAP3_S01`. Все они `LoadRoom`, а не `LoadOverlay`.

## Точная граница задачи

Начало: на улице MAP2_S02 (overlay 12), до первого входа в Alchemilla, без `EventFlag_295`. Событие 19, `TouchObbFacing/Button`, POI 17, загружает MAP3_S00 (overlay 15), `eventParam=19`. Arrival берется из **таблицы исходящего MAP2_S02**, point 19: X=28.4, Z=146.8, `PaperMapIdx_FogHospital1F`, `triggerParam0=192`, `triggerParam1=19`. Сам street POI 17: X=139.8, Z=-13.0. Перед обычным входом стоит event 18 с тем же POI и arrival: если `295` уже выставлен, он загружает восстановленную MAP3_S06, а не повторяет Kaufmann.

Конец: восстановленная MAP3_S06 (overlay 21), завершена Dahlia, получен `InvItemId_AntiqueShopKey`, игрок обычной дверью выходит на MAP2_S02. Event 8, POI 31 (28.4,146.8), `LoadOverlay`, `eventParam=1`, arrival из **MAP3_S06** point 1: X=139.8, Z=-13.0, `PaperMapIdx_FogCentralTown`, `triggerParam0=64`, `triggerParam1=16`. Наличие ключа не является условием самой выходной двери; это условие полного содержательного завершения отрезка.

После этой границы на MAP2_S02 event 10, POI 7, Inventory Use AntiqueShopKey вызывает `func_800E9D54`, удаляет ключ и устанавливает `EventFlag_M2S02_AntiqueShopOpen`. Только затем event 11 открывает MAP4_S01 с arrival 8. Это граница следующей главы; ее внутренности не входят в данный audit. POI магазина: X=-216.7, Z=108.2. Удалять ключ на выходе из больницы или автоматически открывать магазин нельзя.

## Оригинальная последовательность

| Overlay | Содержание и обязательный результат |
| --- | --- |
| MAP3_S00 / 15 | Reception и Kaufmann. Дверь event 6 выставляет 195 через механизм LoadRoom disabled flag; FMV 13 (`FILE_XA_M5_03140`) выставляет 196; callback 4 продолжает DMS `HP1F03`, завершает 197 и 198. После этого переходы в S01 через POI 2/1/0 с arrival 3/7/6 подчиняются соответствующим флагам дверей. |
| MAP3_S01 / 16 | Basement key -> basement door -> generator -> elevator. Получение bottle и UnknownLiquid является отдельной опциональной ветвью. Осмотр закрытых выходов этажей отмечает flags, необходимые для появления дополнительной кнопки лифта. |
| MAP3_S02 / 17 | Alessa и изменение больницы. Callback 5, DMS `DWSTWY`, завершает 237. Автоматический LoadRoom event 1 выставляет 238; его `mapIdx=MAP0_S02` — BGM. POI 14 -> S03, arrival 15. |
| MAP3_S03 / 18 | Палаты, Bloodsucker, Cat/Turtle/Hatter, BloodPack, Lighter, Alcohol, BasementStoreroomKey, plate door, optional VCR. Лифт связывает S03/S04/S05 через общие flags 212..223. |
| MAP3_S04 / 19 | Queen plate; проходы к остальной больнице; ExaminationRoomKey открывает дверь Lisa. Вход выставляет 292; FMV 10 (`FILE_XA_M8_03039`) -> 293; callback 4 с Lisa/HSPTL3 -> 294; автоматический переход S06 arrival 39. |
| MAP3_S05 / 20 | Подвал: storeroom key, сдвиг шкафа, alcohol + lighter на лозах, скрытый проход, ExaminationRoomKey. Optional VideoTape, Hammer, сюжетный осмотр изображения Alessa. |
| MAP3_S06 / 21 | Возвращение в обычную больницу, Dahlia/HSPTL2, флаги 297 и 295, получение AntiqueShopKey (296), выход в MAP2_S02. |

Порядок S03/S04/S05 не линейный: обычные проходы и выбор этажа в лифте создают возвраты. Полные исходные условия всех LoadRoom/LoadOverlay ребер сохранены в JSON; room edges не надо сворачивать в однонаправленный маршрут.

## Предметы, Inventory Use и развилки

Обязательные для исходного пути:

- BasementKey: S01 pickup callback 11 (`func_800D279C`), флаг 209. У двери POI 10 есть Button и Item варианты callback 4; ключ удаляется, устанавливаются 210 и `EventFlag_MapMark_585`. Door edges 10 <-> 15 читают именно MapMark_585. Generator callback 12 устанавливает 211, elevator door events проверяют питание.
- Четыре plates: Queen в S04 (241), Turtle/Hatter/Cat в S03 (242/243/244). BloodPack pickup=249; Use у S03 POI 87, callback 17 (`func_800D2CDC`), отвлекает трех Bloodsucker и выставляет 250. Состояние NPC и collision/render flags восстанавливаются по 250; одного снятия модели недостаточно. Hatter остается отдельным pickup у POI 78.
- Plate door: S03 POI 71, Item events для Turtle/Hatter/Cat/Queen вызывают callback 7. Пустые/занятые гнезда, отмена и извлечение — части оригинальной мини-игры, а не одноразовая проверка наличия всех plates.
- BasementStoreroomKey pickup в S03=255. В S05 POI 11 есть Button/Item callback 3, удаляющий ключ и устанавливающий 256 плюс `EventFlag_MapMark_FogHospital3F_NearElevatorBroken`; последующие room edges проверяют именно этот MapMark.
- Lighter (252), DisinfectingAlcohol (251). Сдвинуть шкаф S05 POI 41 -> 282; он открывает room edge 16 <-> 17. На лозах POI 18 сначала Use Alcohol -> 283, затем Use Lighter -> 284. Lighter без alcohol дает отдельную неуспешную реакцию callback 5; после alcohol Button вызывает промежуточный осмотр callback 7. Только 284 открывает POI 18 -> point 19. Обратный проход POI 20 -> point 18 сохранен отдельно.
- ExaminationRoomKey pickup в S05=257. S04 POI 5 Button/Item callback 3 удаляет ключ и устанавливает 258 плюс `EventFlag_MapMark_AltHospital1F_WomensBathroomBroken`. Следующая дверь — LoadRoom, а не переход в MAP5_S02.
- AntiqueShopKey pickup в S06=296 разрешен флагом 297 (Dahlia оставила ключ). Два Button события POI 37/38 ведут в callback 6, `func_800D17D8`. Флаг 295 выбирает восстановленную больницу при повторном входе с улицы; 297 и 296 решают другие задачи и не взаимозаменяемы.

Опциональные, но сохраняемые возможности:

- PlasticBottle: S01 callback 8, pickup flag 205. Четыре Use события S01 points 57..60, callback 7 **MapEvent_UseBottleOnLiquid**, требуют Bottle и выключены после 206. Осмотр без бутылки — callback 6, выставляет 204, но не дает предмет. Использование удаляет Bottle и добавляет `InvItemId_UnknownLiquid` (102), выставляя 206 (`map3_s01.c:202`). Это опционально для выхода из больницы, но влияет на позднюю возможность спасения Cybil: `Inventory_ItemUse` в `item_screens_2.c:1256` проверяет UnknownLiquid на MAP6_S04. Нельзя очищать его при Otherworld, FMV, Lisa, Dahlia или street handoff; flag 206 сам по себе не заменяет inventory item.
- VideoTape pickup S05=253. Use у VCR S03 POI 74 -> callback 12; прослушивание поврежденной записи устанавливает 254. Это callback/audio sequence, не SysState_Fmv. Он не нужен для ExaminationRoomKey и возврата в обычную больницу.
- Hammer pickup S05=289, optional melee weapon. Maps (207 общий hospital map, 208 basement map), аптечки, напитки, патроны, ampoule и сюжетные осмотры также остаются реальными исходными pickups/сообщениями.
- S05 событие 18: 259 -> callback 12 (`func_800D6D1C`) -> 260, изображение `ALESSA.TIM` и voiced messages 18/19. Не следует подменять этот эпизод FMV или считать вторым NPC Alessa.

## Сохранение plate puzzle и лифта

S03 хранит placements в **16 event bits** 265..280: `265 + plateIndex * 4 + slotIndex`, plateIndex Turtle=0, Hatter=1, Cat=2, Queen=3. На открытии интерфейса flags заново читаются в `D_800D8140[4]`; 8 означает пустоту. Извлечение возвращает соответствующий inventory item и очищает только занятый bit. Отмена установки возвращает выбранный plate. Решение — `D_800D8140[i] == i` для всех четырех i, затем `EventFlag_MapMark_713` (числовой 1577). По оригинальной таблице `D_800D6B40` slots: 0 верхний правый (207,42), 1 нижний правый (207,166), 2 нижний левый (84,166), 3 верхний левый (84,42); диагональные solution bits 265,270,275,280. Решение открывает room door POI 46 <-> 71. Сохранение только solved bit теряет частичную расстановку и возврат предметов.

Общая реализация лифта `include/maps/shared/sharedFunc_800D15F0_3_s01.h` использует flags 212..215 для состояния прибытия/дверей, 216..219 для выбора этажа, 220..223 как блокировки/одноразовые disabled flags переходов. При открытии панели 216..223 очищаются; при завершении поездки 212..215 перестраиваются. Это часть сохранения и перехода, а не независимые открытые двери. В S01 дополнительная кнопка появляется после обоих map marks `AltHospital2F_OperatingPrepRoomArrow` и `AltHospital2F_CorridorMidArrows`; ее выбор (CHECK_IDX=5) выставляет 224 и ведет в S02 arrival 56. Не заменять это автоматическим переходом сразу после generator.

Shared 199/207 используются S00/S01/S06: предмет/карта, уже подобранные до Otherworld, не должны появляться снова после восстановления. Сохранение должно сохранять весь event bitset, inventory (включая UnknownLiquid и выбранное оружие), paper-map state, placements, flags дверей/генератора/шкафа/лоз, NPC progression, текущий overlay и player pose. В JSON присутствуют реальные save points и исходные event params, включая S00/S06 save location 10, S03 location 11 и S04 location 12.

## NPC, FMV и звук

Kaufmann (S00), Alessa (S02), Lisa (S04), Dahlia (S06) используют собственные персонажи, DMS transforms и синхронные камеры. DMS files: `HP1F03.DMS`, `DWSTWY.DMS`, `HSPTL3.DMS`, `HSPTL2.DMS`. FMV ровно два в этом срезе: index 13/M5_03140 и index 10/M8_03039; последующая сцена NPC — отдельный callback и должна выполняться также после skip FMV.

Voiced text tables: Kaufmann `D_800D256C/D_800D24F0`, Lisa `D_800D5A3C/D_800D599C`, Dahlia `D_800D2736/D_800D26D0`, VCR `D_800D6BDA/D_800D6B54`, basement scene `D_800DAC74/D_800DAC70`. Не заменять их только субтитрами. Важные ambient/SFX включают generator 1495/1503, plate 1524 и unlock 1343, Bloodsucker 1525/1527, cabinet 1535, burning vines 1533/1534 и Lisa/headache 1522. Native callbacks должны обслуживать XA/audio waits, иначе сцены могут навсегда ждать завершения звука.

Враги: Creeper в S01/S02/S05, PuppetNurse/DummyNurse и Bloodsucker в S03, PuppetDoctor/DummyDoctor в S04. Chara group identifiers, оригинальные spawns, модели и animation data нужны вместе с geometry; placeholder room traversal не доказывает перенос содержимого.

## Кандидаты для узких компонентных проверок

1. Сопоставить **все** eventParam с actual callback arrays: особенно S01 params 5..14; assert четыре bottle Use ведут в callback 7. Это ловит ошибку baseline parser без изменения правильных исходников.
2. LoadRoom/BGM: S00 event6, S02 event1, S04 event10 и шесть S06 room events не меняют overlay id. LoadOverlay копирует arrival из исходящей таблицы до смены overlay.
3. Четыре boundary cases: первый вход -> S00; повторный вход при 295 -> S06; выход S06 -> street point1; key Use на street выставляет только shop-open и удаляет ключ один раз.
4. Bottle path через настоящий Inventory Use: bottle205 -> liquid206/item102; reload/Otherworld/FMVs/Lisa/Dahlia/exit сохраняют liquid; осмотр204 без bottle не дает liquid; повторный Use не дублирует.
5. BasementKey/Generator/elevator: оба door flags, отказ включать generator, включение211, отсутствие четвертого этажа до обоих map marks, появление224 после выбора кнопки; оригинальные floor transitions и возвраты.
6. Plates: cancel возвращает plate, occupied slot отвергается, removal очищает нужный bit, частичная расстановка переживает save/reload, неправильные slots не дают1577, правильные265/270/275/280 дают door46<->71.
7. Bloodsucker: до250 присутствуют NPC/collision, Use BloodPack дает анимацию и250, после перехода/reload они остаются отвлеченными; Hatter pickup и его flag243 независимы.
8. Storeroom/hidden passage: key255 ->256/map mark; cabinet282 с collision update; lighter до alcohol не дает284; alcohol283, lighter284, passage; повторное посещение не возвращает шкаф и лозы.
9. Lisa/FMV: examination key257 ->258, doorway292 ->FMV10/293 ->Lisa294 ->S06; обычный просмотр и skip завершают одинаковые persistent flags и возвращают управление.
10. Dahlia: full/skip обоих вариантов ставят297/295, key pickup296 доступен, повторная загрузка не проигрывает сцену заново и не дублирует key; hospital map207/kit199 сохраняют picked state.
11. Optional VCR253/254 и hammer289: взаимодействуют без влияния на обязательные door flags, корректно возвращают управление и выбранное оружие.

Эти проверки дополняют компиляцию/линковку и последующую проверку на New 3DS. Они не заменяют аппаратную приемку, FMV/звуковую приемку, проверку загрузки assets или реальную публикацию новой игровой сборки.
