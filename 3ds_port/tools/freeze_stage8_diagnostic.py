"""Freeze a reviewable diagnostic iteration, explicitly not Stage 8 completion."""
import contextlib,hashlib,io,json,re,runpy,shutil,struct,zipfile
from pathlib import Path
p=Path(__file__).resolve().parents[1];root=p.parent
read=lambda f:json.loads(f.read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
accepted=read(p/'reports/stage7-accepted.json')
assert accepted['status']=='HARDWARE ACCEPTED'
assert sha(p/'build/hardware-stage7-native-wide/silenthill_game.3dsx')==accepted['sha256']
assert sha(p/'baselines/stage7-native-wide-candidate.zip')==accepted['archive_sha256']
with zipfile.ZipFile(p/'baselines/stage7-native-wide-candidate.zip') as z:
    baseline=read(p/'reports/stage7-accepted.json')
    previous=json.loads(z.read('manifest.json'))
    for name,info in previous.items():
        data=z.read(name);assert len(data)==info['bytes'] and hashlib.sha256(data).hexdigest()==info['sha256'],name
    # These four working reports were overwritten by initial Stage 8 test runs.
    # Restore them byte-for-byte; new verification uses Stage 8 report names.
    for name in ('stage7-card-tests.json','stage7-save-arm.json','stage7-tmd-arm.json','stage7-gpu-extensions-arm.json'):
        relative='3ds_port/reports/'+name
        if relative in previous:(p/'reports'/name).write_bytes(z.read(relative))
pc=read(p/'reports/stage8-final-pc.json');arm=read(p/'reports/stage8-final-arm.json')
assert pc['status']==arm['status']=='PASS'
assert arm['elf_sha256']==sha(p/'silenthill_game.elf')
assert len(arm['results'])==12 and all(r['exit_code']==0 for r in arm['results'])
pixels=read(p/'reports/stage8-pixel-index.json');assert pixels['status']=='PASS'
assert pixels['renderer_object_sha256']==sha(p/'build-game/render_3ds.o')
assert 'result=PASS' in (p/'reports/stage8-final-surface.txt').read_text()
assert 'SH_3DS_DEV_START_MAP' not in (p/'build-game/flags').read_text()
for name in ('stage4_autoinput.txt','stage6_route.txt','stage6_observe.txt','stage7_input.txt','stage7_pad.txt','stage8_debug.txt'):
    assert not (root/'sh1_data'/name).exists(),name
with contextlib.redirect_stdout(io.StringIO()):identity=runpy.run_path(str(p/'tools/build_identity.py'))
build=identity['identity'];assert build in (p/'build/build_identity.h').read_text()
evidence=p/'reports/azahar-stage8-cafe'
def status(name):
    s=dict(line.split('=',1) for line in (evidence/name).read_text().splitlines() if '=' in line)
    assert s['build']==build and s['first_failure']=='0' and s['report_complete']=='1'
    return s
s30=status('final-cafe-30.txt');s60=status('final-cafe-60.txt');inventory=status('final-status-cycles.txt')
assert s30['stage8_fps_limit']=='30' and s60['stage8_fps_limit']=='60'
assert all(s['game_state']=='11' and s['map_idx']=='1' for s in (s30,s60,inventory))
assert all(s30[k]==s60[k] for k in ('player_x','player_z','player_yaw'))
assert int(inventory['stage8_status_opens'])>=2
metrics=('recent_fps','recent_frame_ms','recent_work_ms','recent_wait_ms','recent_sim_speed',
    'heap_used','heap_free','linear_free','texture_bytes','cache_active','resource_cache_bytes')
performance={'context':'Azahar, same loaded Cafe save and camera, rare SD observation; not New 3DS measurements',
    '30':{k:float(s30[k]) for k in metrics},'60':{k:float(s60[k]) for k in metrics},
    'status_opens':int(inventory['stage8_status_opens']),
    'status_open_ms':float(inventory['stage8_status_open_ms']),
    'status_open_work_ms':float(inventory['stage8_status_open_work_ms']),
    'unmeasured':['normal street','Cybil','natural first-monster attack','representative heavy scene']}
(p/'reports/stage8-performance.json').write_text(json.dumps(performance,indent=2)+'\n')
def sections(path):
    b=path.read_bytes();off=struct.unpack_from('<I',b,32)[0];size,count,strings=struct.unpack_from('<HHH',b,46)
    headers=[struct.unpack_from('<10I',b,off+i*size) for i in range(count)];h=headers[strings];names=b[h[4]:h[4]+h[5]]
    return {names[h[0]:].split(b'\0')[0].decode():h[5] for h in headers}
now=sections(p/'silenthill_game.elf');before=sections(p/'build/hardware-stage7-native-wide/silenthill_game.elf')
memory={'sections':{k:now.get(k,0) for k in ('.text','.rodata','.data','.bss')},
    'bss_delta_to_stage7':now['.bss']-before['.bss'],'new_linear_allocations':0,
    'linear_capacity':33554432,'texture_cache_capacity':25165824,'resource_cache_capacity':11896416,
    'bottom_color_vram':307200,'native_color_vram':1048576,'native_depth_stencil_vram':1048576,
    'top_color_vram':384000,'top_depth_stencil_vram':384000,
    'vertex_linear':663552,'presentation_vertices_linear':256,
    'card_persistent_ordinary_heap':131072,'card_transaction_extra_peak':131072,
    'measurement_scope':'Cafe, Status and components; not a full later-map peak/stability certification'}
(p/'reports/stage8-memory.json').write_text(json.dumps(memory,indent=2)+'\n')
candidate=p/'build/hardware-stage8-diagnostic-r1';archive=p/'baselines/stage8-diagnostic-r1.zip'
assert not candidate.exists() and not archive.exists()
candidate.mkdir()
for ext in ('.3dsx','.elf','.map','.smdh'):shutil.copy2(p/('silenthill_game'+ext),candidate/('silenthill_game'+ext))
(candidate/'diagnostics').mkdir()
(candidate/'diagnostics/stage8_debug.txt').write_bytes(b'ATTACK\n')
(candidate/'diagnostics/stage6_observe.txt').write_bytes(b'OBSERVE\n')
record={'status':'DIAGNOSTIC R1; HARDWARE PENDING; STAGE 8 INCOMPLETE','build':build,
    'binary':(candidate/'silenthill_game.3dsx').relative_to(root).as_posix(),
    'bytes':(candidate/'silenthill_game.3dsx').stat().st_size,'sha256':sha(candidate/'silenthill_game.3dsx'),
    'elf_sha256':sha(candidate/'silenthill_game.elf'),'stage7_accepted_unchanged':True,
    'attack_crash_reproduced':False,'attack_crash_fix_confirmed':False,'once_per_swing_fix_component_verified':True,
    'photo1_strip_root_cause_confirmed':False,'hardware_visual_validation':False,
    'checks':{'pc_sanitizers':True,'ARM':True,'PICA_pixels':True,'Cafe_original_load':True,'repeated_Status':True},
    'performance':performance,'memory':memory,'archive':archive.relative_to(root).as_posix()}
report=p/'reports/stage8-diagnostic-r1.json';report.write_text(json.dumps(record,indent=2)+'\n')
handoff=f'''# Stage 8 — диагностическая R1 для New Nintendo 3DS

**Stage 8 НЕ завершён и НЕ HARDWARE ACCEPTED.** Это замороженная диагностическая
итерация. Остановка при естественной атаке монстра пока не воспроизведена;
полноэкранная левая полоса из фото 1 также не получила отдельного точного
воспроизведения. Компонентные исправления не заменяют проверку на устройстве.
Stage 7 принят пользователем; его бинарник и архив не изменены.

Бинарник: `{record['binary']}`. Размер: **{record['bytes']} байт**.
SHA-256: `{record['sha256']}`.
Build: `{build}`. Обычный запуск, без DEV_START_MAP и без автозапуска New Game.
Исходники/доказательства: `3ds_port/baselines/stage8-diagnostic-r1.zip`, SHA-256
каждого включённого файла находится в `manifest.json` внутри архива.

## Изменения и проверка

Внесены общая очистка всей native-поверхности, привязка экрана к владельцу кадра,
скрытие промежуточного LoadStatus, исправления размера/положения 3D-превью из
PC-порта, преобразование полного native-кадра для framebuffer effects и обработка
нужной PSX-страницы. Игровой 3D viewport остаётся 400×240 с прежним GTE-масштабом;
Status — оригинальное 2D на нижних 320×240. Итоговая внешняя визуальная проверка
по каждому из пяти симптомов ещё нужна. Подробности и границы доказательств:
`docs/3ds-stage8-audit.md`.

START открывает паузу: Resume, Exit to Title, 30/60 FPS, Quit application.
В меню B подтверждает, A/START возобновляют. Движок во время паузы не вызывается,
время паузы вычитается из игровых часов. Проверены SDK-граница паузы и настоящий
ARM `Game_WarmBoot` из инициализированной игры к Title. Быстрый boot сохраняет
Title/Load; неподдерживаемые attract-demo/intro не забирают управление из меню.

Перенесены PC pacing <=60, накопительный Q12-таймер, коррекции камеры/текста/
попаданий. Принятая граница шага Stage 7 сохранена, чтобы просадки ниже 30 FPS
не замедляли время. Тесты покрывают 15/24/30/45/60 Гц. Сравнение накопленного
урона двух попаданий одного удара: Stage 7 — 65088 → 131580, Stage 8 —
65088 → 65088. Связь этого дефекта с вашим зависанием ещё не установлена.

Пройдены PC/ASan/UBSan, 12 ARM-проверок, 296 TMD, исходные save/load state
machines, камера/поза, частицы, boot/New Game, idle-Title и возврат к Title.
PICA: blend/STP/order/mask, оба экрана, continuation, readback и resampling.
Старая геометрия clear оставляет 16 строк/6400 пикселей суммарно; исправленная
заливка покрывает все 96000 пикселей. Это подтверждает горизонтальные пробелы,
но само по себе не воспроизводит полную вертикальную полосу фото 1.

## Замеры Azahar

Одинаковое Cafe save/положение/камера, редкая запись телеметрии:

| Режим | Реальный FPS | Кадр, мс | Работа без pacing, мс | Pacing wait, мс | Скорость времени |
|---|---:|---:|---:|---:|---:|
| 30 | {performance['30']['recent_fps']:.3f} | {performance['30']['recent_frame_ms']:.3f} | {performance['30']['recent_work_ms']:.3f} | {performance['30']['recent_wait_ms']:.3f} | {performance['30']['recent_sim_speed']:.4f} |
| 60 | {performance['60']['recent_fps']:.3f} | {performance['60']['recent_frame_ms']:.3f} | {performance['60']['recent_work_ms']:.3f} | {performance['60']['recent_wait_ms']:.3f} | {performance['60']['recent_sim_speed']:.4f} |

Повторных открытий Status: {performance['status_opens']}; последнее открытие
{performance['status_open_ms']:.3f} мс, без pacing {performance['status_open_work_ms']:.3f} мс.
Сопоставимого замера задержки Stage 7 нет: численное ускорение не заявляется.
Улица, Cybil, естественная атака и тяжёлая сцена в 30/60 здесь НЕ измерены.
Это не показатели производительности реального New 3DS.

Новых linear-аллокаций: **0**. Изменение BSS: {memory['bss_delta_to_stage7']:+d} байт
(всего {memory['sections']['.bss']}). Texture capacity: 25165824, resource capacity:
11896416 байт. Измеренная свободная linear в Cafe: {int(performance['30']['linear_free'])}
байт при 30 и {int(performance['60']['linear_free'])} при 60; после Status:
{inventory['linear_free']}. Кэш ленивый, поэтому это не проверка глобального
пика; принятые ~5 MiB при полном texture cache остаются той же расчётной границей.
Полная разбивка — `3ds_port/reports/stage8-memory.json`.

## Нужен тест первого удара на New 3DS

1. Скопировать этот `.3dsx` вместо запускаемого homebrew. BIN/CUE и существующую
   карту `sdmc:/3ds/silenthill/memcard.mcr` оставить на месте.
2. Для диагностического запуска скопировать файлы из соседней папки `diagnostics/`
   в `sdmc:/3ds/silenthill/`. Они одноразовые и потребляются при boot.
   `stage8_debug.txt` включает максимум 128 строк журнала атаки;
   `stage6_observe.txt` — редкие снимки состояния раз в 15 секунд.
3. Через обычный Load открыть своё Cafe save (известная разработческая запись —
   Data 2 в SLOT1). Дойти до уже известного первого монстра привычным способом.
   Дать ему нанести первый удар, сначала не стрелять; проверить урон, реакцию
   Гарри и продолжение управления. Если остановка повторится — сфотографировать
   оба экрана, весь First FAIL/detail либо Luma exception и последний видимый момент.
4. После выхода/перезапуска прислать `stage4_status.txt` и
   `stage8_attack_trace.txt` из этого SD-каталога, если последний создан. Указать,
   произошла ли остановка до контакта, при контакте, реакции или после смерти.
   Известный старый guard GameOver — FAIL 451/detail 13; его важно отличить
   от сбоя обработки укуса. Отсутствие журнала тоже сообщить.
5. Попутно проверить START → Resume, 30/60 и Exit to Title → Load; несколько
   открытий/закрытий Status, положение пистолета в рамке, левый край, верх/низ
   моделей и переходы. Затем Save → полный выход → запуск → Load.

Звук/FMV/stereo/touch/modern controls/поздние карты не добавлялись. Ранние
ограничители Options/Results/бумажной карты и GameOver из Stage 7 не объявляются
реализованными. Если укус работает, а дальнейшая смерть попадает в старый guard,
это отдельный точный результат для следующей итерации. Stage 8 остаётся открытым
до устранения аппаратного blocker и завершения остальных проверок.
'''
(root/'docs/3ds-stage8-handoff.md').write_text(handoff,encoding='utf-8')
(candidate/'README-RU.md').write_text(handoff,encoding='utf-8')
paths=[root/n for n in previous if not n.startswith('3ds_port/build/')]
paths+=identity['paths']
for directory in (p/'source',p/'include',p/'tools',p/'tests',candidate):
    paths.extend(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
paths+=list((p/'reports').glob('stage8-*'))+list(evidence.rglob('*'))+list((p/'reports/azahar-stage8-pixels').rglob('*'))
paths+=list((root/'docs').glob('3ds-stage8-*'))+[root/'docs/3ds-stage7-accepted.md',p/'reports/stage7-accepted.json',p/'build-game/flags',p/'build/build_identity.h']
paths=sorted(set(f for f in paths if f.is_file()))
assert all('sh1_data' not in f.relative_to(root).parts and f.suffix.lower() not in ('.bin','.cue','.mcr') for f in paths)
manifest={f.relative_to(root).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f)} for f in paths}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for f in paths:z.write(f,f.relative_to(root).as_posix())
    z.writestr('manifest.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
    for name,expected in manifest.items():
        data=z.read(name);assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256'],name
record['archive_sha256']=sha(archive);record['verified_members']=len(manifest)
report.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ('performance','memory')},indent=2))
