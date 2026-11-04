# Оставшаяся игра: статический аудит и порядок контентных checkpoint

Аудит от 28.10.2026, выполнен **до подключения новой главы**. Точка отсчёта:
School `65ab73346` / документирование `44997c1f3`, поверх принятой Stage 11A B
`stage11a-cpu-B-src-8c51d74ee1feb7e0`. Активная Stage 11B и Native-FMV не
изменяются. Аппаратное прохождение этим документом не подтверждается.

Машинная версия: `3ds_port/reports/remaining-game-coverage.json`, генератор
`3ds_port/tools/audit_remaining_game.py`. В ней все **33 overlay MAP2–MAP7**,
исходные event records с индексом/строкой, callback, required/disabled flags,
Use, LoadRoom, LoadOverlay, save points, FMV, точки, spawn/AI callbacks,
ресурсы и SHA исходников. `item_interactions` отделяет реальные операции
от общей таблицы `LOADABLE_INVENTORY_ITEMS`: наличие предмета в последней
не означает, что этот предмет добывается в данной комнате.

Авторитетные источники для каждого `mapN_sXX`: каталог `src/maps/mapN_sXX/`,
`include/maps/mapN/mapN_sXX.h`, `configs/USA/maps/sym.mapN_sXX.txt`,
`pc_port/build_gen/extracted_data/mapN_sXX_extracted_data.c`.
Комнаты/триггеры: `map_points.h`, `MAP_ROOM_IDXS`, `vc_road_data.h`,
`header_field_D2C.h`; спавны: `chara_spawns.h` и `charaGroupIds`.
Общие исходные модули находятся в `include/maps/shared` и
`src/maps/characters`; включения `.c` также учтены.

## Состояние нативного покрытия

На входе из оставшихся карт слинкован только **MAP2_S00**: весь Old Silent
Hill, его ранние события, K. Gordon, церковный вход и мост уже существуют
в принятой базе. MAP0_S02 содержит используемые им интерьеры. School добавляет
MAP1_S01–S06, поэтому возврат через школьный выход также разрешён.
MAP2_S01–MAP7_S03 имеют исходники/таблицы, но пока отсутствуют в 3DS target.

Имеющаяся общая инфраструктура: original Status/Inventory → lastUsedItem →
Event_Update, общий pickup/Use, коллизии, боевой damage, анимации, DMS,
event flags, original save record, BGM/XA/SFX и загрузка дисковых ресурсов.
Вероятно контентные дополнения: event/room/door/point tables и исходные
callback. Требуют проверки совместимости: ARM-типы callback, повторные поля
overlay header, прямые PS1 data pointers, нативные callable animation tables,
новые AI, эффекты и ресурсная вместимость. Отсутствие INCLUDE_ASM не доказывает
готовность ARM. INCLUDE_RODATA зачастую обеспечивается extractor/PSX data alias;
это отдельный вопрос от отсутствующего нативного кода.

## Районы, зависимости и естественные границы

| Блок | Overlay и помещения | События, предметы, замки, противники | Выход / checkpoint |
|---|---|---|---|
| 1. После школы: Old Silent Hill | **MAP2_S00**, существующий **MAP0_S02** (в том числе дом K. Gordon), **MAP2_S01** Balkan Church; начало **MAP2_S02** Central Silent Hill. **MAP2_S04** police station — доступная необязательная ветка следующего района | K. Gordon Key из школы → исходный замок/расход; Далия/DMS/озвучка → Flauros и Drawbridge Key; ключ в пульт, отдельное подтверждение выключателя и движение моста. Air Screamer/Groaner; в полном S02 также Romper. Смена мира здесь не нужна, босса нет | Исходный S00 point 55 → **S02 с destination pose из S00 point 56**, обычное управление за мостом. Выбран **первым**: завершена церковь/мост, начинается новый город и путь к больнице |
| 2. Alchemilla | **MAP2_S02/S04** — улицы/полиция; **MAP3_S00** вход, осмотр/встреча Kaufmann; **S01** обычные этажи/подвал/кухня/генератор; **S02** лифт/переход; **S03–S05** Otherworld этажи, сестринская, кладовая, видео, палаты, скрытый проход; **S06** возвращённая больница и Далия | Basement Key/генератор/лифт → Otherworld. Plastic Bottle + жидкость → Unknown Liquid (сохранить для Cybil). Четыре Plate (Turtle/Hatter/Cat/Queen) и исходная расстановка; Blood Pack/Bloodsucker; Basement Storeroom Key, Disinfecting Alcohol + Lighter → скрытый проход; Video Tape, Examination Room Key, Hammer; Lisa и Dahlia; Creeper, Puppet/Dummy Nurse/Doctor, Bloodsucker. Босс-арены нет | Flags 292→293(FMV)→294 → S06; Antique Shop Key → **MAP2_S02**, контроль перед antique shop. Весь hospital group — одна глава, без остановки на лифте |
| 3. Antique shop и Otherworld Central Silent Hill | Возврат **MAP2_S02**, **MAP4_S01** antique shop/алтарь/тоннель, **S02** Otherworld улицы; **S03** mall/Twinfeeler; **S04** hospital vision/Lisa; **S05** Floatstinger arena; повторный **MAP2_S04** для полиции | Antique Shop Key расходуется исходным callback. Cybil/скрытый путь/алтарь, Axe; провал в mall, Hunting Rifle, полный Twinfeeler; Lisa-вставки; полный Floatstinger и возврат города. Night Flutter/Wormhead/Romper. S04 flags 337/338, 339/340 управляют видениями/выходом к боссу | Floatstinger → **MAP2_S02**, затем исходный путь через **MAP2_S00** к водопроводу; стабильное управление у начала следующего sewer. Не разрывать между двумя фазами этой сюжетной линии |
| 4. Первый sewer | Возврат **MAP2_S00** waterworks → **MAP5_S00**, обе части канализации, служебные проходы/ключевая комната/выход | Исходный вход после событий города; Sewer Key, Sewer Exit Key, карта, закрытые ворота; Creeper и Hanged Scratcher, исходная засада у ключа. Без босса/FMV | **MAP5_S01**, управляемый Harry в Resort Area после выхода |
| 5. Resort/Kaufmann и катер | **MAP5_S01** resort улицы; **S02** Annie's Bar и Indian Runner; **S03** Norman's Motel/гараж/номера. Затем **MAP6_S00** Otherworld lakefront и **S01** boat | Kaufmann bar fight, Receipt/Kaufmann Key, исходные коды дверей/сейфа, Safe Key; Magnet → Motorcycle Key → гараж/мотоцикл/Aglaophotis. Это необязательная ветка, влияющая на ending, не исключать её. Air Screamer/Groaner/Romper, scripted Kaufmann. Катер: Cybil/Dahlia, постановка цели lighthouse/amusement park; Night Flutter/Wormhead/Romper на изменённых улицах | После разговора на катере → **MAP6_S00**, контроль и задача маяка. Сохранить условия перехода мира и ending flags из Kaufmann ветки |
| 6. Lighthouse → amusement park | **MAP6_S00**, **S02** lighthouse/Alessa, **S03** второй sewer, **S04** парк/карусель/Cybil/Alessa/Dahlia | Lighthouse seal/story flags → возвращение/канализация; Hanged Scratcher/Mumbler, затем Grey Child/Larval Stalker. **Monster Cybil**: AI, огнестрельный бой, arena/camera/death; альтернативное спасение через сохранённую Unknown Liquid. Flauros расходуется в сцене Alessa/Dahlia. MonsterCybil/Parasite/Flauros callbacks обязательны, хотя не все перечислены в spawn groups | Flag 451 → **MAP7_S00 entry 8**; подключить прибытие/первую Lisa-сцену до нормального управления в Nowhere |
| 7. Nowhere и финал | **MAP7_S00** вступление/Lisa; **S01/S02** полный смешанный hospital/interior maze; **S03** финальная арена и ending scripts | Pliers → ключ, Screwdriver/Stone of Time/часы/Bird Cage Key; Ophiel/Hagith/Phaleg/Bethor/Aratron и их двери; камера/символы, электричество/генератор, Ring of Contract/холодильник, Video Tape; Amulet of Solomon, Crest of Mercury, Ankh, Dagger of Melchior, Disk of Ouroboros → финальная дверь. Lisa/BloodyLisa, GhostDoctor/GhostChildAlessa/Bloodsucker/Stalker. Финальные **Incubator/Incubus** и scripted actors Kaufmann/Dahlia/Cybil/Alessa, все ending варианты | Original ending chain → результаты/credits/next-game save/title; после концовки следующей обычной главы нет. Не считать вход на арену устойчивой остановкой: там начинается автоматическая сцена |

Первый блок включает полный relevant MAP2 group для свободного осмотра; S03
имеет `NO_STAGE!` и не имеет входящего нормального LoadOverlay. Он не нужен
для маршрута. MAP4_S00 аналогично заглушечный; MAP4_S06/MAP6_S05 не имеют
event-driven входов в нормальном графе. Их наличие в инвентаризации не является
требованием добавить отладочные входы. Решение об исключении делать по исходному
графу, не по тому, что такие overlay «легко компилируются».

Это **план будущих задач**, не реализация блоков 2–7. Повторно используемые
карты между блоками остаются едиными: S02 до/после больницы и после Floatstinger,
S04 normal/alternate police exits, S00 школьная и sewer ветки.

## FMV и звуковые границы

Исходный API: `SysState_Fmv_Update` вызывает
`open_main(FILE_XA_ZC_14392 - eventParam, blockCount)` и после возврата ставит
`disabledEventFlag`. Флаги `flags_8_13` определяют повторную инициализацию
InGame. Номера в таблице — eventParam, а не file ID.

| Место | Параметр → оригинальный файл |
|---|---|
| MAP2_S01 церковь | 12 → **M6_02112**, после возврата 181 → исходная сцена Далии |
| MAP3_S00 | 13 → M5_03140 |
| MAP3_S04 | 10 → M8_03039 |
| MAP4_S03 | 11 → M7_01536 |
| MAP6_S03 | 9 → M9_01730 |
| MAP6_S04 | 8 → MA_03590; 7 → MB_04850 |
| MAP7_S00 | 6 → MC_01930 |
| MAP7_S01 и S02 | 5 → MD_03780; сохранить условия обоих вызовов, не склеивать события |
| MAP7_S03 | 4 → ME_03300; ending 3 → Z1_16180, 2 → Z3_02340, 1 → Z4_01590, 0 → ZC_14392 |

Все эти вызовы обслуживает **существующий Native-FMV checkpoint**
`codex/fmv-native` / `e94a90a6b` / `native-fmv-src-59d6e586ef70b529` после
интеграции. Новый decoder или вечный skip не нужен. Школьный M4_02490 — уже
известная входная зависимость, не новая задача. Ending credits/stream и переход
к results тоже сохранить через исходный API, даже когда они не выражены отдельной
строкой MAP_EVENTS. Пропуск/cleanup/возврат в игровое состояние нужно проверить
после объединения, throughput ещё не подтверждён на устройстве.

**Отдельный финальный пробел:** `FILE_VIN_STF_ROLL_BIN`,
`src/bodyprog/credits_init.c`, `src/screens/credits/credits.c` и
`src/bodyprog/ranking.c` ещё не входят в 3DS closure. В game_services.c
`func_8008F94C`, `func_800904F4`, `Results_DisplayInfo` пока останавливают
исполнение как неподключённый results screen. Эти границы надо заменить
исходной реализацией в финальном блоке, согласовать native staff-roll callbacks
`func_801E2E28/2ED8/2FC0`, исходный список титров вместо desktop PcCredits_List,
Next Fear flags/clearGameCount/clearGameEndings и сохранение результатов.
MAP7_S03 вызывает эту цепь; необязательный Channeling Stone ending в MAP6_S02
тоже вызывает staff roll. **FMV checkpoint эту зависимость не закрывает.**
Это статически установленный пробел для будущих задач, он не реализуется здесь.

DMS и обычная озвучка — отдельная от FMV зависимость. Церковь загружает
`CHRC.DMS`, original Dahlia model/ANM и команды XA; hospital/boat/ending actors
используют свои DMS/XA и фоновые банки. Мост включает длительный пространственный
SFX и stereo/volume ramp; сирены/переходы миров и boss ambience сохраняются.
Точные FILE_*/BGM/SFX и строки вызовов по каждой карте находятся в JSON.
Архитектура SPU/NDSP, renderer, GTE и feedback здесь не меняется.

## Сохранения и риски интеграции

У всех блоков persistent authority — исходный **s_Savegame**, inventory,
eventFlags, paper-map marks, enemy overlay state, map/room/player position,
world/boss/ending flags. JSON перечисляет save-menu события каждого overlay и
все прямые обращения к save state. Портовые глобальные переменные не должны
заменять эти поля. Особые точки: состояние моста после reload; размещённые plates;
собранная жидкость до Cybil; пройденный generator/hidden passage; Kaufmann ending
ветка; Cybil alive/dead; пять установленных финальных предметов и boss completion.
Временные DMS/camera/puzzle cursors можно сбрасывать при re-entry, solved state — нельзя.

Главные ещё не проверенные зависимости: новые animation function-pointer tables;
полные character update/collision/damage callbacks (не только charaGroupIds);
PS1 адреса таблиц с callback; ARM layout/type compatibility; вместимость исходных
буферов в более крупных сценах; renderer effects/feedback в поздних мирах.
Последние документировать для Stage 11B, не исправлять отдельной архитектурой.

Условные поля `mapIdx` в **LoadRoom** не считать LoadOverlay: в частности
MAP3_S00→MAP6_S01, MAP3_S02→MAP0_S02, MAP3_S04→MAP5_S02 и поздние ссылки на Cafe
не означают, что нужно загружать эти overlay ради каждого такого события.
Dispatcher и sysState первичны. Аналогично общий LoadOverlay граф содержит
возвратные/поздние ветки: статический список не доказывает их доступность сейчас.

Для каждой будущей задачи: соответствующий полный блок, минимальные compatibility
правки, compile/link + ограниченные ARM component checks; затем отдельный checkpoint.
Одна совмещённая hardware candidate после принятой 11B + School + Native-FMV +
готовый контент, с обычной публикацией только на той последующей стадии.
