"""Freeze R2 diagnostic evidence without changing Stage 7 or frozen R1."""
import contextlib,hashlib,io,json,runpy,shutil,struct,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
r1=read(p/'reports/stage8-diagnostic-r1.json');s7=read(p/'reports/stage7-accepted.json')
assert sha(p/r1['binary'].removeprefix('3ds_port/'))==r1['sha256']
assert sha(p/'baselines/stage8-diagnostic-r1.zip')==r1['archive_sha256']
assert sha(p/'build/hardware-stage7-native-wide/silenthill_game.3dsx')==s7['sha256']
assert sha(p/'baselines/stage7-native-wide-candidate.zip')==s7['archive_sha256']
pc=read(p/'reports/stage8-final-pc.json');arm=read(p/'reports/stage8-final-arm.json')
assert pc['status']==arm['status']=='PASS' and len(arm['results'])==14
assert pc['elf_sha256']==arm['elf_sha256']==sha(p/'silenthill_game.elf')
pixels=read(p/'reports/stage8-r2-pixel-index.json');assert pixels['status']=='PASS'
assert pixels['renderer_object_sha256']==sha(p/'build-game/render_3ds.o')
assert read(p/'reports/stage8-r2-gpu-arm.json')['status']=='PASS'
assert read(p/'reports/stage8-r2-reload-working.json')['status']=='PASS'
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
for name in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/name).exists(),name
with contextlib.redirect_stdout(io.StringIO()):identity=runpy.run_path(str(p/'tools/build_identity.py'))
build=identity['identity'];assert build in (p/'build/build_identity.h').read_text()
evidence=p/'reports/azahar-stage8-r2-cafe'
def snapshot(name):
    s=dict(line.split('=',1) for line in (evidence/name).read_text().splitlines() if '=' in line)
    assert s['build']==build and s['first_failure']=='0' and s['report_complete']=='1'
    assert s['game_state']=='11' and s['map_idx']=='1'
    return s
a=snapshot('final-cafe-30.txt');b=snapshot('final-cafe-60.txt')
assert a['stage8_fps_limit']=='30' and b['stage8_fps_limit']=='60'
assert all(a[k]==b[k] for k in ('player_x','player_z','player_yaw'))
assert int(a['stage8_status_opens'])>=1
assert sha(root/'sh1_data/memcard.mcr').upper()==read(evidence/'card-before.json')['Hash']
metrics=('recent_fps','recent_frame_ms','recent_worst_ms','recent_work_ms','recent_wait_ms',
    'recent_sim_speed','linear_free','heap_used','cache_active','texture_bytes')
performance={'context':'Azahar, same Cafe save/camera; OBSERVE_FAST 1-second SD snapshots, not hardware',
    '30':{k:float(a[k]) for k in metrics},'60':{k:float(b[k]) for k in metrics},
    'status_opens':int(a['stage8_status_opens']),
    'status_open_ms':float(a['stage8_status_open_ms']),
    'status_open_work_ms':float(a['stage8_status_open_work_ms']),
    'simulation_limit':'Measured windows fall below 1.000 under >66.7ms hitches with retained 273-Q12 cap. Exact hitch source not isolated; these are not a comparable rare-observation performance benchmark to R1.',
    'card_unchanged':True}
(p/'reports/stage8-r2-performance.json').write_text(json.dumps(performance,indent=2)+'\n')
def sections(path):
    data=path.read_bytes();off=struct.unpack_from('<I',data,32)[0];size,count,strings=struct.unpack_from('<HHH',data,46)
    h=[struct.unpack_from('<10I',data,off+i*size) for i in range(count)]
    strings=data[h[strings][4]:h[strings][4]+h[strings][5]]
    return {strings[x[0]:].split(b'\0')[0].decode():x[5] for x in h}
now=sections(p/'silenthill_game.elf');old=sections(p/'build/hardware-stage8-diagnostic-r1/silenthill_game.elf')
memory={'sections':{k:now[k] for k in ('.text','.rodata','.data','.bss')},
    'bss_delta_to_r1':now['.bss']-old['.bss'],'new_linear_allocations':0,'new_VRAM_allocations':0,
    'texture_capacity':25165824,'resource_capacity':11896416,'visibility_rows_max':512,'attack_rows_max':128}
(p/'reports/stage8-r2-memory.json').write_text(json.dumps(memory,indent=2)+'\n')
feedback={'status':'R1 HARDWARE FINDINGS REPORTED; NOT ACCEPTED','reported_date':'2026-10-26',
    'findings':['startup presentation unstable','model horizontal dark bands persist','location transition corrupt',
        'Status close starts top fade','START consumes cutscene skip','Cafe monster invisible'],
    'source':'user hardware report; R1 binary and archive remain immutable'}
(p/'reports/stage8-r1-hardware-feedback.json').write_text(json.dumps(feedback,indent=2)+'\n')
candidate=p/'build/hardware-stage8-diagnostic-r2';archive=p/'baselines/stage8-diagnostic-r2.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
(candidate/'diagnostics').mkdir()
(candidate/'diagnostics/stage8_debug.txt').write_bytes(b'ATTACK\n')
(candidate/'diagnostics/stage6_observe.txt').write_bytes(b'OBSERVE\n')
binary=candidate/'silenthill_game.3dsx'
record={'status':'DIAGNOSTIC R2; HARDWARE PENDING; STAGE 8 INCOMPLETE',
    'build':build,'binary':binary.relative_to(root).as_posix(),'bytes':binary.stat().st_size,
    'sha256':sha(binary),'elf_sha256':sha(candidate/'silenthill_game.elf'),
    'monster_regression_closed':False,'reload_despawn_defect_fixed':True,
    'R1_specific_invisibility_cause':'unconfirmed; same reload defect also exists in accepted Stage 7',
    'ARM_tests':14,'PC_ASan_UBSan':'PASS','PICA':'PASS','performance':performance,'memory':memory}
report=p/'reports/stage8-diagnostic-r2.json'
report.write_text(json.dumps(record,indent=2)+'\n')
handoff=f'''# Stage 8 R2 — диагностическая сборка

**Stage 8 НЕ HARDWARE ACCEPTED. Критическая регрессия видимости R1 ещё не закрыта.**

Бинарник: `C:/Users/sombo/Documents/ChatGPT/sh_3ds/silent-hill-decomp/{record['binary']}`

Размер: **{record['bytes']} байт**. Build: `{build}`.

SHA-256: `{record['sha256']}`

Stage 7 и замороженные R1 binary/archive проверены по SHA-256 и сохранены.

| Замечание | Что сделано / граница доказательства |
|---|---|
| Монстр невидим | В ARM подтверждён reload-путь: ошибочный X=2147483647 → удаление NPC. Применено существующее PC-исправление X=-4096. При 30/60 NPC сохраняется и выпускает геометрию. Ошибка есть и в Stage 7, поэтому причина именно регрессии R1 пока не установлена. Нужен focused hardware test с новым журналом. |
| Запуск/2D | Обе пары верхних framebuffer и render targets явно чёрные. Warning переведён с раннего 320x224 окружения на тот же 320x448 → 320x240 холст, что Title, центрированный на top LCD. 2D не растянута до 400. Проверить flicker/позицию на New 3DS. |
| Status close | Повторный top fade начинался в InGame шаге 0. Для возврата из Inventory теперь reset; обычные игровые fades сохранены. ARM и возврат из реального Cafe Status прошли. Субкадровый результат подтвердить на железе. |
| Тёмные полосы | Маскированный fog producer обрезался на ±112 вместо открытых ±120. Исправлены общие вертикальные пределы, без исключений для персонажей. ARM подтверждает полное покрытие; проверить реальное затенение моделей. |
| Переход | Пропущенный PC-clamp допускал чтение атласа третьим спрайтом; теперь 256+64, с обратным масштабированием в 400. GsInitGraph2 также терял isinter: восстановлены оба поля 2D feedback. Исходная функция проверена детерминированно, эффект сохранён. Аппаратная проверка формы/левого края нужна. |
| START | Новое нажатие в обычном gameplay открывает Pause. В cutscene оригинальный START проходит в Skip; Cafe входит в оригинальный шаг 52. Удержание после Skip не открывает Pause. |

Полный разбор: `docs/3ds-stage8-r2-audit.md`.

## Проверки и 30/60

14 ARM-проверок, PC ASan/UBSan, PICA colour/STP/order/mask/оба LCD — PASS.
Оригинальный Load дошёл до Cafe, одно открытие/закрытие Status; First FAIL=0.
Сохранение memcard.mcr не изменено, Azahar завершён.

| Azahar, одинаковая Cafe/камера | FPS | Работа без pacing, мс | Скорость времени | Худший кадр, мс |
|---|---:|---:|---:|---:|
| 30 | {float(a['recent_fps']):.3f} | {float(a['recent_work_ms']):.3f} | {float(a['recent_sim_speed']):.4f} | {float(a['recent_worst_ms']):.3f} |
| cap 60 | {float(b['recent_fps']):.3f} | {float(b['recent_work_ms']):.3f} | {float(b['recent_sim_speed']):.4f} | {float(b['recent_worst_ms']):.3f} |

Это запуск с частой диагностической записью раз в секунду, не сопоставимый
performance benchmark с R1 (там редкие снимки). В этих окнах hitches превышают
66.7 мс; сохранённый лимит 273 Q12 отбрасывает часть времени. Источник каждого
hitch отдельно не локализован. Минутные детерминированные проверки скорости
времени проходят, но **1.000 для этих реальных окон не заявляется**.
Режим 60 сохранён как измерительный/unlocked с cap 60; оптимизаций ради locked
60 не делалось. Производительность New 3DS должен измерить аппаратный тест.

Новых linear/VRAM-аллокаций: 0. BSS относительно R1: {memory['bss_delta_to_r1']:+d} байт.
Размеры texture/resource cache сохранены. Полных поздних маршрутов не было.

## Короткая проверка на New 3DS

1. Скопировать этот `.3dsx`. Для диагностического запуска положить оба файла из
   соседнего `diagnostics/` в `sdmc:/3ds/silenthill/`. Они одноразовые.
   `ATTACK` включает также новый журнал видимости, `OBSERVE` — снимки раз в 15 с.
2. Через своё обычное Cafe сохранение воспроизвести первоначальное появление
   монстра в 30 FPS. Подтвердить: виден → летает → остаётся в сцене. Повторить
   в 60, выбранном через Pause. Если невидим, атака пока не является следующим
   тестом: прислать `stage8_visibility_trace.txt`, `stage4_status.txt`, режим FPS,
   фото обоих экранов и указание Load/новая игра.
3. Проверить black → warning → Title; START во время разговора Cybil должен
   выполнять оригинальный Skip. В обычной игре START открывает Pause.
4. Закрыть Status: верхний экран должен сразу показывать gameplay. Проверить
   Гарри/монстра около верхнего и нижнего края и один известный переход локации.
5. Если случайно повторится остановка при атаке, сохранить фото First FAIL/detail
   или Luma exception и `stage8_attack_trace.txt`. Исправление атаки не заявлено.

Приоритет следующего шага — аппаратное подтверждение видимости, затем уже атака.
'''
(root/'docs/3ds-stage8-r2-handoff.md').write_text(handoff,encoding='utf-8')
(candidate/'README-RU.md').write_text(handoff,encoding='utf-8')
with zipfile.ZipFile(p/'baselines/stage8-diagnostic-r1.zip') as z:previous=json.loads(z.read('manifest.json'))
paths=[root/n for n in previous if not n.startswith('3ds_port/build/')]
paths+=identity['paths']
for directory in (p/'source',p/'include',p/'tools',p/'tests',candidate,evidence,p/'reports/azahar-stage8-r2-pixels'):
    paths.extend(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths+=list((p/'reports').glob('stage8-*'))+list((root/'docs').glob('3ds-stage8-*'))
paths+=[p/'build-game/flags',p/'build/build_identity.h']
paths=sorted(set(f for f in paths if f.is_file()))
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin','.cue','.mcr') for f in paths)
manifest={f.relative_to(root).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for n,info in manifest.items():
        data=z.read(n);assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],n
record.update(archive_sha256=sha(archive),verified_members=len(manifest))
report.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('performance','memory')},indent=2))
