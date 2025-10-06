# TEST 1 — Contract Matrix

## Bot callbacks & messages
| Trigger | Handler | Input | Response / Template | Notes |
|---------|---------|-------|---------------------|-------|
| `t1opt:<q_idx>:<opt_idx>` | `handle_test1_option` | Callback data, state payload | След. вопрос или `finalize_test1` → шаблон `t1_done` | Валидирует через `Test1Payload`, антидубли по `t1_current_idx`. |
| `pick_rec:<id>` | `handle_pick_recruiter` | Recruiter id | Сообщение с клавиатурой слотов (`_recruiter_header`, `kb_slots_for_recruiter`) | Проверка активного рекрутёра и соответствия городу. |
| `refresh_slots:<id>` | `handle_refresh_slots` | Recruiter id | Перерисовка клавиатуры, шаблон `no_slots` при пустом списке | Отвечает `"Обновлено"`. |
| `pick_slot:<rec_id>:<slot_id>` | `handle_pick_slot` | Slot id, recruiter id | Шаблон `slot_sent` кандидату; уведомление рекрутёру (`kb_approve`) | `reserve_slot()` возвращает статусы `reserved/duplicate_candidate/slot_taken`. |
| `approve:<slot_id>` | `handle_approve_slot` | Slot id | Сообщение рекрутёру о результате + отправка кандидату (`approved_msg`/`stage3_intro_invite`) | Пишет NotificationLog `candidate_interview_confirmed`, планирует напоминания. |
| `sendmsg:<slot_id>` | `handle_send_slot_message` | Slot id | Ручная отправка сообщения кандидату | Доступно после согласования. |
| `reschedule:<slot_id>` | `handle_reschedule_slot` | Slot id | Уведомление рекрутёру + `notify_reschedule` кандидату (`slot_reschedule`) | Освобождает слот (`reject_slot`), отменяет напоминания. |
| `reject:<slot_id>` | `handle_reject_slot` | Slot id | Уведомление рекрутёру + `notify_rejection` (`result_fail`) | Слот → FREE, state → `flow="rejected"`. |
| `att_yes:<slot_id>` | `handle_attendance_yes` | Slot id, callback id | Линк (`att_confirmed_link`), ACK (`att_confirmed_ack`) | Dedup через `register_callback` + NotificationLog `candidate_confirm`. |
| `att_no:<slot_id>` | `handle_attendance_no` | Slot id | Сообщение кандидату (`att_declined`), слот → FREE | Рекрутёр получает уведомление, кандидат возвращён к выбору. |

## Templates (по ключам)
| Ключ | Использование | Контекст |
|------|---------------|----------|
| `choose_recruiter` | После Test 1 — меню выбора | `city_id` из state |
| `no_slots` | Нет свободных слотов у рекрутёра | — |
| `slot_sent` | Подтверждение кандидату после брони | — |
| `approved_msg` / `stage3_intro_invite` | Автоуведомление кандидату при согласовании | `candidate_fio`, `city_name`, `dt`, `slot_local_labels` |
| `slot_reschedule` | Рекрутёр инициирует перенос | `recruiter_name`, `dt` |
| `result_fail` | Отказ кандидату | `candidate_fio`, `city_name`, `recruiter_name` |
| `att_confirmed_link`, `att_confirmed_ack` | Кандидат подтверждает | `link`, `dt`, `slot_local_labels` |
| `att_declined` | Кандидат отказался | — |
| `manual_schedule_prompt` | Нет доступных слотов | Для ответственного рекрутёра добавляется кнопка tg://user?id |

## Admin UI / API endpoints
| Endpoint | Method | Payload / Params | Response / Codes | Логика |
|----------|--------|------------------|------------------|--------|
| `/slots` | GET | `recruiter_id`, `status`, pagination | HTML | Вывод списка слотов + counters (см. P2). |
| `/slots/create` | POST | Form (`recruiter_id`, `city_id`, `date`, `time`) | Redirect + flash | Создаёт единичный слот. |
| `/slots/bulk_create` | POST | Form (диапазон дат/времени, шаг, перерывы) | Redirect + flash | Массовое создание слотов. |
| `/slots/{slot_id}` | DELETE | `force` (optional) | JSON `{ok, message, code?}` | Удаление слота, `code="requires_force"` при занятом слоте. |
| `/slots/delete_all` | POST | `{force?: bool}` | `{ok, deleted, remaining}` | Массовое удаление. |
| `/slots/{slot_id}/outcome` | POST | `OutcomePayload {outcome: str}` | `{ok, message, outcome}` + header `X-Bot` | Фиксирует исход интервью, опционально триггерит Test 2. |
| `/slots/{slot_id}/reschedule` | POST | — | `{ok, message, bot_notified}` (200/400/404) | Вызывает `reschedule_slot_booking` → `reject_slot` + `notify_reschedule`. |
| `/slots/{slot_id}/reject_booking` | POST | — | `{ok, message, bot_notified}` | `reject_slot_booking` → `notify_rejection`. |

## Domain / Scheduler
| Функция | Контракт |
|---------|----------|
| `reserve_slot(slot_id, candidate_tg_id, ...) -> ReservationResult` | Возвращает `status` (`reserved`, `slot_taken`, `duplicate_candidate`, `already_reserved`) и `slot` (при наличии). Использует `SlotReservationLock` + уникальные индексы. |
| `approve_slot(slot_id) -> Slot?` | Переводит `pending` → `booked`. При `confirmed_by_candidate` возвращает слот без изменений. |
| `reject_slot(slot_id) -> Slot?` | Освобождает слот, очищает кандидата, удаляет `SlotReservationLock`. **Не** очищает `NotificationLog` (см. P0). |
| `confirm_slot_by_candidate(slot_id) -> CandidateConfirmationResult` | Статусы: `confirmed`, `already_confirmed`, `invalid_status`, `not_found`. Использует NotificationLog для идемпотентности. |
| `ReminderService.schedule_for_slot(slot_id, skip_confirmation_prompts=False)` | Строит расписание `[confirm_2h, remind_1h]`, сохраняет в `slot_reminder_jobs`, отменяет прошедшие задания. |
| `ReminderService.cancel_for_slot(slot_id)` | Удаляет задания из БД и APScheduler. |

## Ошибочные статусы/коды
| Слой | Код/Статус | Когда возникает |
|------|------------|-----------------|
| Bot | `slot_taken` | Слот занят или рекрутёр/город не совпадают (шаблон `slot_taken`). |
| Bot | `duplicate_candidate` | У кандидата есть активная бронь у того же рекрутёра (см. P1). |
| Bot | `already_reserved` | Повторное нажатие на тот же слот (state candidate_tg_id совпадает). |
| Admin API | HTTP 404 + `{"ok":false,"message":"Слот не найден"}` | Слот отсутствует при переносе/отказе/удалении. |
| Admin API | HTTP 400 + `code="requires_force"` | Попытка удалить занятый слот без `force`. |
| Bot callbacks | alert "Сценарий неактивен" / "Слот уже освобождён" | Несогласованные стейты или гонка. |
