#!/usr/bin/env python3
"""Write the Russian hardware handoff only after emulator gates pass."""
import hashlib,json
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
v=read(p/'reports/stage7-validation.json');assert v['status']=='AZAHAR VERIFIED; HARDWARE PENDING'
binary=p/'silenthill_game.3dsx';assert hashlib.sha256(binary.read_bytes()).hexdigest()==v['sha256']
sections=read(p/'reports/stage7-sections.json');m=v['memory'];c=v['comparison']
baseline=read(p/'reports/stage6-candidate.json')['analysis']['memory_last_120_seconds']
num=lambda x:f'{int(x):,}'.replace(',',' ')
body=f'''# Stage 7 — кандидат для New Nintendo 3DS

**HARDWARE PENDING. Аппаратная приёмка Stage 7 ещё не выполнена.**
Stage 6 остаётся HARDWARE ACCEPTED; его бинарник и архив не изменены.

Кандидат: `3ds_port/build/hardware-stage7-native-wide/silenthill_game.3dsx`.
Размер: **{num(binary.stat().st_size)} байта**.
SHA-256: `{v['sha256']}`.
Сборка: `{v['build']}`. Обычный запуск, без DEV_START_MAP.
Исходники и доказательства: `3ds_port/baselines/stage7-native-wide-candidate.zip`;
поэлементный манифест SHA-256 находится внутри архива.

## Что проверено

В Azahar пройден обычный путь New Game → пролог → кошмар → удар/падение →
Cafe → полный разговор с Сибил → свободное управление. Проверены оригинальные
модели и подбор Health Drink/Flashlight, нижний Status, навигация, экипировка
пистолета и применение Health Drink. Взята бумажная карта с исходным полноэкранным
2D-изображением. Создано сохранение, приложение полностью закрыто и запущено
снова; оригинальный Load восстановил Cafe, предметы, количества и экипировку.
После Load проверены видимая геометрия Cafe, перемещение и повторное открытие
нижнего Status. Итоговые снимки сделаны после завершения перехода загрузки.
После меню записан непрерывный свободный участок длительностью
{v['continuous_free_cafe_seconds']:.1f} с без роста памяти и ошибок.

Сохранены одинаковые ракурсы 320×240 и 400×240:
`3ds_port/reports/azahar-stage7-systems/final-cafe-classic.png` и
`final-cafe-wide.png`. Масштаб GTE не меняется; добавляется геометрия по краям.
Время кадра Azahar: {float(c['classic']['recent_frame_ms']):.2f} мс classic и
{float(c['wide']['recent_frame_ms']):.2f} мс wide
({c['wide_frame_time_change_percent']:+.2f}%). Это замер эмулятора.
Цель реального New 3DS остаётся около 30 FPS; Stage 7 на устройстве ещё не измерен.

Пройдены PC/ASan/UBSan, ARM GS/TMD (296 моделей), оригинальные save/card state
machines, управление, анимации, частицы и кэш. Синтетические PICA-пробы проверяют
прозрачность/STP, режимы смешивания и порядок на верхней native-поверхности;
RGB, маску, нижнюю область страницы и продолжение кадра — на обоих экранных
назначениях. Подробности: `3ds_port/reports/stage7-validation.json`.

## Память

| Область | Байты |
|---|---:|
| Обычная heap, поздний стабильный диапазон | {num(m['heap_used']['min'])}–{num(m['heap_used']['max'])} |
| Свободная обычная heap, минимум | {num(90271744-m['heap_used']['max'])} |
| Свободная linear heap | {num(m['linear_free']['min'])} |
| Использованная linear heap | {num(33554432-m['linear_free']['min'])} |
| Texture cache, фиксированная ёмкость | {num(m['texture_bytes']['max'])} |
| Resource cache | {num(m['resource_cache_bytes']['max'])} |
| Карта: постоянная обычная heap | 131 072 |
| Карта: дополнительный временный пик записи | 131 072 |
| BSS всего / прирост к Stage 6 | {num(sections['stage7']['bss'])} / +{num(sections['delta']['bss'])} |
| Новый нижний color target, VRAM | 307 200 |
| Существующая native color / stencil поверхность, VRAM | 1 048 576 / 1 048 576 |
| Верхний color / depth-stencil target, VRAM | 384 000 / 384 000 |
| Существующие renderer vertices, linear | 663 552 |

Новых больших linear-буферов и копий моделей нет. Новый draw-clip массив
ограничен 49 152 байтами BSS. PSX RAM: 3 145 728 байт; canonical VRAM с метаданными:
1 048 580 байт. Существующие presentation vertices занимают 256 байт linear.

| Стабильный показатель Azahar | Stage 6 | Stage 7 |
|---|---:|---:|
| Обычная heap, использовано | {num(baseline['heap_used']['max'])} | {num(m['heap_used']['max'])} |
| Linear, свободно | {num(baseline['linear_free']['min'])} | {num(m['linear_free']['min'])} |
| Texture cache | {num(baseline['texture_bytes']['max'])} | {num(m['texture_bytes']['max'])} |
| Resource cache | {num(baseline['resource_cache_bytes']['max'])} | {num(m['resource_cache_bytes']['max'])} |

## Виртуальная карта

Путь: `sdmc:/3ds/silenthill/memcard.mcr`.
Формат: стандартный raw PS1 образ **131 072 байта**, без контейнерного заголовка.
Вставлен виртуальный SLOT1; SLOT2 отображается отсутствующим. Используются
оригинальные файлы/метаданные/контрольные суммы и одиннадцать записей на файл.
Запись идёт через полный `.tmp` с flush/fsync и сохранением предыдущего `.bak`.
Повреждённый существующий main-файл не переформатируется автоматически.

Тестовая карта в рабочем каталоге: `sh1_data/memcard.mcr`.
Новая запись — **Data 2 внутри SLOT1**: Cafe, пистолет/15, фонарик/1,
Health Drink израсходован, карта взята. Её можно использовать как обычный
нативный путь разработки через Load. Карта не включена в архив исходников.

## Проверка на реальном New 3DS

1. Скопировать кандидат в используемый каталог homebrew; оставить прежние
   BIN/CUE и структуру `sdmc:/3ds/silenthill/`. Существующую карту сохранить
   отдельно перед заменой тестовой картой.
2. Проверить обычный New Game до Cafe либо Load нужной записи. Верхний экран
   должен использовать 400×240 с дополнительной геометрией и правильными
   пропорциями; проверить улицу, гараж, кошмар, Cafe и разговор с Сибил.
3. Подобрать обычный предмет. X (Triangle) открывает оригинальный Status
   на нижних 320×240; проверить навигацию, экипировку и применение. Для выхода
   выбрать Exit и подтвердить B (Cross). Верхний кадр в меню остаётся сохранённым.
4. Записать игру у блокнота в Cafe в SLOT1. Полностью завершить приложение
   (START+SELECT останавливает игру, затем START закрывает приложение),
   запустить снова и через **Load** выбрать созданную запись. Проверить позицию,
   предметы, количества, экипировку и отсутствие уже подобранных предметов.
5. Проверить около десяти минут свободной игры: ошибки, постепенное замедление,
   целостность краёв экрана, fog/lighting и стабильность. Сообщить результат/FPS
   и любой первый FAIL. Только после этого возможна аппаратная приёмка Stage 7.

## Ограничения

Звук/SPU/NDSP/XA/голоса не реализованы; FMV пропускаются. Options, отдельный
экран бумажной карты, Pause и Results остаются вне этого среза и имеют явные
ограничители. Подбор бумажной карты проверен отдельно от её меню. Сохранения
поздних карт не входят в приёмочный сценарий. Touch, постоянная нижняя карта,
стерео, C-stick camera и 60 FPS не добавлялись.

Снижение Cybil примерно до 24 FPS на принятом Stage 6 остаётся backlog;
это не повторное открытие аппаратной приёмки Stage 6.
'''
(root/'docs/3ds-stage7-handoff.md').write_text(body,encoding='utf-8')
print('Wrote docs/3ds-stage7-handoff.md; HARDWARE PENDING')
