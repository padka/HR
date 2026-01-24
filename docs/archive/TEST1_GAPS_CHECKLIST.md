# TEST 1 — Gap Checklist

| Категория | Статус | Комментарий |
|-----------|--------|-------------|
| Идемпотентность | ⚠️ Частично | Колбэки антидубли через `TelegramCallbackLog`, но `NotificationLog` не очищается → повторное согласование/подтверждение ломает поток (см. P0). |
| Таймзоны | ✅ | Все `DateTime` → `timezone=True`, `_to_aware_utc` нормализует, `slot_local_labels`/`fmt_dt_local` используют `ZoneInfo`. Напоминания строятся в локальной зоне кандидата. |
| Блокировки/гоночные условия | ⚠️ | `reserve_slot` и `confirm_slot_by_candidate` используют `SELECT .. FOR UPDATE`. Однако повторная бронь после `CONFIRMED` не заблокирована (см. P1). |
| Уникальные индексы | ⚠️ | Есть `uq_slots_candidate_recruiter_active`, но без `confirmed_by_candidate`. NotificationLog нет очистки/расширенного ключа. |
| Напоминания / Scheduler | ✅ | `ReminderService.schedule_for_slot` отменяет старые job, пересоздаёт, хранит в `slot_reminder_jobs`. При повторной отправке слота уведомления пропускаются из-за P0. |
| Retry/Rate limits Telegram | ✅ | `_send_with_retry` реализует экспоненциальные повторы (`TelegramRetryAfter`, `ClientError`). |
| Удаление клавиатур | ✅ | `safe_remove_reply_markup` вызывается после любого исхода (approve/reschedule/att_*) |
| Кэш/инвалидация | ✅ | Списки городов/рекрутёров всегда читаются из БД (`get_active_recruiters*`), кеша нет. |
| Мониторинг/логи | ⚠️ | Ошибки Telegram логируются, NotificationLog фиксирует отгрузки, но нет метрик по провалам рассылки (кроме логов). |
| Тестовое покрытие | ⚠️ | Есть unit-тесты на happy-path, но отсутствовали сценарии рескейла и повторной брони (добавлены красные тесты). |
