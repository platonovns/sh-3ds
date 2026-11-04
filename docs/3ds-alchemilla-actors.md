# Alchemilla: native actors и таблицы анимации

Область: исходные MAP3_S00–MAP3_S06. Функции AI, движение, урон,
смерть, DMS/dialogue и completion logic сохраняют retail-реализацию.
Аппаратная приемка, оценка графики/звука и непрерывный playthrough здесь не
заявляются. См. `3ds_port/reports/alchemilla-actors-arm.json` и общий отчет блока.

## Точное actor coverage

| Overlay | Исходные actors / dispatch | Инициализация данных |
|---|---|---|
| MAP3_S00 | Kaufmann_Update; сценический spawn в func_800D0CF8 | KaufmannAnimInfos_Init; KAUFMANN_ANIM_INFOS[46] |
| MAP3_S01 | Creeper_Update; три исходных spawn rows | CreeperAnimInfos_Init; CREEPER_ANIM_INFOS[36] |
| MAP3_S02 | Creeper_Update; Alessa_Update (сценический spawn в func_800D0608) | CreeperAnimInfos_Init; AlessaAnimInfos_Init; ALESSA_ANIM_INFOS[22] |
| MAP3_S03 | PuppetNurse_Update для Puppet/Dummy Nurse; PuppetDoctor_Update для Puppet/Dummy Doctor; Bloodsucker_Update | PuppetNurseData_Init; BloodsuckerAnimInfos_Init; BLOODSUCKER_ANIM_INFOS[30] |
| MAP3_S04 | Puppet/ Dummy Doctor; Lisa_Update и сценический spawn в func_800D2668 | PuppetNurseData_Init; LisaAnimInfos_Init; LISA_ANIM_INFOS[36] |
| MAP3_S05 | Puppet/ Dummy Nurse; Creeper_Update | PuppetNurseData_Init; CreeperAnimInfos_Init |
| MAP3_S06 | Dahlia_Update; сценический load/spawn в func_800D0C14 | DahliaM3S06AnimInfos_Init; DAHLIA_M3S06_ANIM_INFOS[52] |

Dummy variants используют те же original update routines, что Puppet variants;
нового AI не вводится. `Chara_None` в retail spawn rows означает исходный
вариант/наследование группы: эти записи не заменяются новыми spawns.
Alessa входит в фактический MAP3_S02 header/spawn graph, несмотря на отсутствие
ее имени в минимальном списке задания.

Kaufmann DMS track — `KAU`, Alessa — `ARISA`, Lisa — `LISA`, Dahlia — `DARIA`.
Вызовы Dms_CharacterTransformGet / Dms_CameraTargetGet, XA dialogue и установка
оригинальных event flags остаются в map event routines. Окончание сцены
Kaufmann устанавливает 197/198; Alessa — 237; Lisa использует 298/299 и 294;
Dahlia — 297/295. Это исходные save flags, не новые port globals.

## Native callback tables

Original callable addresses таблиц: Anim_BlendLinear `0x80044CA4`,
Anim_PlaybackOnce `0x800449F0`, Anim_PlaybackLoop `0x80044B38`.
На ARM каждая непустая playbackFunc должна ссылаться на соответствующую
скомпилированную ARM-функцию. Пустые retail entries остаются пустыми.

PuppetNurseData_Init материализует две native arrays по 46 s_AnimInfo,
четыре s_800D5710 instance records и три combat tuning records.
Доктор использует B, три nurse variants — A. Instance animInfo_24 должен быть
native pointer: простой DATA alias на original MAP3 BIN небезопасен.

Исключения из PS1 DATA aliasing в native_overlay.py:

- KAUFMANN_ANIM_INFOS, ALESSA_ANIM_INFOS, LISA_ANIM_INFOS;
- DAHLIA_M3S06_ANIM_INFOS (общая DAHLIA_ANIM_INFOS уже нужна Post-school);
- CREEPER_ANIM_INFOS, BLOODSUCKER_ANIM_INFOS;
- sharedData_800D5710_3_s03, sharedData_800D5A8C_3_s03.

Все Init routines вызываются до использования нового overlay. В частности
Bloodsucker.c необходимо компилировать с MAP3_S03: hospital Control_2/Control_4
содержатся в соответствующих #ifdef и зависят от original EventFlag_250,
stateStep 18/19/20 и Blood Pack event callback. Режим MAP7_S02 сюда не подходит.

## Минимальные compatibility исправления

1. Отдельная hospital Dahlia table. Church MAP2_S01 и hospital MAP3_S06
   имеют различные duration/frame ranges. Например, entry 8 имеет duration
   20480 в church и 12288 в hospital. Использование общей church table
   изменяло бы исходную сцену. В dahlia.h alias включается только для
   SH_3DS_PORT && MAP3_S06; MAP2_S01 сохраняет свою таблицу.
2. PuppetNurseData_Init теперь восстанавливает ранее опущенные unnamed words
   по retail: +0x10={1,1,2,3}, +0x14=0, +0x28={9,6,7,9},
   +0x30={0,1,2,3}. Все прочие scalars и анимации уже совпадали с MAP3 BIN.
3. Kaufmann/Lisa/Alessa rotation casts к SVECTOR следуют существующему Dahlia
   подходу: исходный SVECTOR3 имеет те же первые компоненты.
4. Nurse/Bloodsucker получили исходные объявления Math_MatrixTransform;
   Bloodsucker — sound_system.h, Nurse — stdlib.h для abs.
   Rotation casts исправляют строгую ARM-проверку типов.
5. Desktop nurse SFX debug logging исключен из 3DS. Существующая проверка
   identity field_124 оставлена: stale NPC slot не должен косвенно вызывать
   garbage/PS1 callback. Она не заменяет normal initialization/AI.

## Offline verification

Воспроизводимый runner: `python3 3ds_port/tools/test_alchemilla_actors.py`.
Использует DEVKITARM, подготовленные offline flags/dependencies и Unicorn;
читает `sh1_data/sh1.bin` либо SH_DISC. Никакие BIN/CUE, saves или .3dsx
в отчет/архив не копируются. Actor component ELF имеет только stub playback
entrypoints и служит проверке инициализации таблиц, не игровой сборкой.

Runner компилирует семь actor components и семь native table components;
исполняет native Init routines и сравнивает все scalar bytes и точное
соответствие playback pointer original->ARM. 294 entries обычных actor tables
и 552 проверяемых entries четырех nurse variants в трех overlays, всего 846.
Сравниваются все scalar bytes 12 instance records, три tuning tables;
повторный Init проверяет отсутствие зависимости от прежнего состояния.

Дополнительный `--game-elf 3ds_port/build/alchemilla/alchemilla-content.elf`
проверяет исходные Nurse/Doctor damage/death routines на Easy/Normal/Hard,
четыре variant records, nonlethal/lethal damage, очистку damage packet,
original persisted enemy bits. Hard сохраняет original RNG policy respawn.
Он также сравнивает Harry map animation arrays S00–S06: 11,31,27,33,35,39,11
entries (включая terminators), всего 187 entries, с BIN и native callbacks.
Результат каждого реально выполненного набора записывается в JSON;
наличие описания optional check само по себе не означает его PASS.

## Практические границы и Stage 11B риски

AI attack/movement/collision и сложность сохранены на уровне исходников;
isolated damage inputs не доказывают все combat геометрические взаимодействия.
Аппаратно нужно проверить aiming, hit volumes, захват/атаки Nurse/Doctor,
Creeper attack/death, сохранение enemy states и возвраты между overlays.

MAP3_S03 Bloodsucker использует scratch RAM и bone 14 для collision geometry;
MAP3_S03/S04/S05 Nurse/Doctor строят collision volumes из иерархии костей.
Неправильный pose/GTE или stale bone buffer здесь может нарушить combat даже
при корректных callbacks. Это риск integration в gameplay geometry/pose;
рендерер, GTE pipeline и audio architecture в этой работе не меняются.

MAP3_S02 Alessa использует DMS light/camera tracks; MAP3_S04 Lisa и MAP3_S06
Dahlia — исходные cutscene камеры и модели. Offline table checks не оценивают
визуальную правильность этих сцен, текстуры, GPU timing и performance.
FMV/audio decoder зависимости описывает основной отчет Alchemilla;
actors не реализуют новый декодер и не заменяют movie events пропусками.

Фактический результат 28.10.2026: standalone actor compile/Init/BIN checks PASS;
полный content ELF: 24 Nurse/Doctor damage cases на -1/0/1 difficulty и 187
Harry animation entries PASS. SHA-256 проверенного ELF сохранен в
поле elf_sha256 отчета; это внутренний ELF без .3dsx и публикации.

