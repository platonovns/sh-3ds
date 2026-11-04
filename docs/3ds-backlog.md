# Бэклог 3DS-порта

## Current status — 2026-10-28

**Stage 10 — Road to School is CLOSED / HARDWARE ACCEPTED** by explicit user
decision. See [final acceptance](3ds-stage10-accepted.md). The natural route to
school and school save were accepted on real New Nintendo 3DS; earlier Cafe-only
coverage and Stage 10 pending statements below are historical.

Retained performance follow-ups: flashlight feedback/texture cost, Cafe command
generation and shared-core SPU workload. The
[three hardware CPU recordings](3ds-stage10-r6-cpu-hardware.md) provide evidence
for future scoped work. They are not blockers to the closed Stage 10 milestone.
Deferred UI/FMV/stereo and other later features remain deferred.

## S8-TRANSITION-01 — визуальный переход между уровнями

Status: **CLOSED with Stage 10 hardware acceptance**. R5 hardware feedback
confirmed rendering/fade correctness without corruption or flicker.
The remaining fade-cadence observation is retained as a polish follow-up.
The following paragraphs describe the earlier Stage 8/R1a history.
См. [изменения framebuffer framing/fade и границы проверок](3ds-stage10-r1a-handoff.md).
Следующий абзац сохраняет историческое состояние принятого Stage 8 R2.
Добавлено: 2026-10-26, после аппаратной проверки R2 на New Nintendo 3DS.

Оставшаяся проблема — некорректное отображение исходного эффекта перехода
между уровнями. Предыдущие симптомы: уменьшение изображения, неверное
расположение и фрагментация во время эффекта. Пользователь подтвердил, что
переход остаётся единственным замечанием, и явно принял R2 с этим исключением.
Точный вид остаточного дефекта после R2 отдельно не уточнялся.

При возвращении к задаче использовать принятую R2 как базу и короткий известный
переход для воспроизведения. Сохранить исходный эффект и корректную 400×240
презентацию gameplay. Существующие исправления clamp framebuffer-спрайтов и
isinter не считать полным решением оставшейся проблемы.

Основание приёмки: [Stage 8 R2](3ds-stage8-r2-accepted.md).

## Deferred after Stage 9 — recorded 2026-10-26

Исторический список при закрытии Stage 9. Новое задание Stage 10 разрешает
расширение gameplay до школы, performance/profiling и отдельный C-stick control
path. Эти пункты теперь в работе по Stage 10; приёмка R1a и полный маршрут ещё
не получены. Остальные отложенные направления ниже не открываются автоматически.

Stage 9 audio is now closed and HARDWARE ACCEPTED by the user on R6.
See [the accepted audio baseline](3ds-stage9-r6-accepted.md).
The following remain deferred; closing Stage 9 does not authorize their implementation:

- Persistent lower-screen UI closely inspired by the original Silent Hill Status aesthetic.
- Original-style item carousel as a major lower-screen element.
- Optional touch-friendly Quick Select and lower-screen touch controls.
- Separate map mode filling the lower 320×240 display.
- Broader gameplay validation beyond Cafe, and later-map/gameplay bugs discovered after Cafe.
- FMV/video playback, any separate FMV audio path, and possible later stereoscopic FMV conversion.
- Stereoscopic gameplay, likely targeting 30 FPS.
- Final optimization toward stable 60 FPS in 2D.
- Modern camera/control enhancements.
- Old Nintendo 3DS optimization/support.

The user's normal hardware gameplay validation reaches Cafe only. Stage 8 R2
remains the frozen HARDWARE ACCEPTED baseline, including S8-TRANSITION-01 above.
Stage 9 R6 is the frozen HARDWARE ACCEPTED audio baseline. SFX/VAB/KDT,
early Cheryl/Harry, Cafe Harry/Cybil and START/Skip with functional subsequent
audio are confirmed by the user. This does not extend gameplay/audio hardware
coverage beyond Cafe. Earlier R2/R3 failures remain historical evidence.

## S9-PERF-01 — медленная Cafe-катсцена и паузы между репликами

Статус: **отложено в отдельную стадию performance/profiling**. В задаче
закрытия Stage 9 не исследовать и не оптимизировать.

Первое аппаратное наблюдение R1: Cafe monster cutscene около **10–12 FPS**
на New Nintendo 3DS. При финальной приёмке R6 пользователь подтвердил,
что Cafe-сцена всё ещё работает примерно при 10–12 FPS. Сами реплики звучат
с правильными скоростью и высотой; затянутые паузы **между** ними относятся
к замедленному продвижению игры/катсцены при низком FPS.

Пользователь явно исключил эти паузы из ошибок XA/audio и принял Stage 9 R6.
Не менять принятую аудиореализацию, частоту, pitch или gain для компенсации
медленной симуляции. Сохранять качество аудио/SPU, графики и корректность игры.
Будущая работа начинается с отдельного профилирования; причины CPU/GPU
в рамках этого закрытия не измеряются и заранее не приписываются аудио.

Сохранить полезную XA-диагностику. Её отключение или удаление допустимо только
после доказательства существенной runtime-стоимости будущим профилированием.
Основание: [финальная аппаратная приёмка Stage 9 R6](3ds-stage9-r6-accepted.md).
