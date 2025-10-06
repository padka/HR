# TEST 1 — Fix & Migration Plan

## Batch 1 (30–45 мин)
- Подготовить регрессионные тесты:
  - Перенос + повторное согласование (ожидать новое уведомление и reminders).
  - Подтверждённый кандидат пытается забронировать новый слот → получить `duplicate_candidate`.
- Зафиксировать current state для NotificationLog (SQL snapshot), чтобы после миграции очистить «старые» записи.

## Batch 2 (45–60 мин)
- Миграция `notification_logs`:
  - Добавить колонку `candidate_tg_id BIGINT NULL`.
  - Обновить уникальный индекс на `(type, booking_id, candidate_tg_id)`.
  - Одноразово проставить `candidate_tg_id` для актуальных брони (JOIN c `slots`).
- Кодовые правки:
  - `add_notification_log` / `notification_log_exists` / `confirm_slot_by_candidate` / `handle_approve_slot` — передавать текущего кандидата.
  - В `reject_slot` + `handle_reschedule_slot`/`handle_reject_slot` очищать NotificationLog.
  - Перегенерировать напоминания после повторного согласования.
- Прогнать обновлённые тесты.

## Batch 3 (30–45 мин)
- Обновить `reserve_slot` проверку `existing_active` на статусы `{pending, booked, confirmed_by_candidate}`.
- Миграция для индекса `uq_slots_candidate_recruiter_active` (добавить `confirmed_by_candidate`).
- Дополнить тесты кейсом повторной брони после подтверждения.

## Batch 4 (30 мин)
- UI: расширить `status_counts` и шаблон для отображения `CONFIRMED_BY_CANDIDATE`.
- Добавить быстрый тест/проверку `list_slots` на корректный аггрегат.

## Rollout
1. Деплой миграций + кода на staging, прогнать тесты и smoke (перенос/отказ/повторная бронь).
2. Очистить наследованные NotificationLog (если остались записи без `candidate_tg_id`).
3. Мониторинг: временно включить логирование успешных уведомлений/напоминаний для проверки.
4. Прокатить в прод с наблюдением за scheduler и ботом.

## Rollback
- Для Batch 2/3: откат Alembic + возврат к старым функциям (Git revert). NotificationLog можно восстановить из снапшота.
- Для UI (Batch 4): откатить шаблон/контроллер.
