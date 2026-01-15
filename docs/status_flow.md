# Карта статусов кандидата (as-is)

Источник правды: `backend/domain/candidates/status.py` + `status_service.py`.

## Статусы
| Слаг | Значение |
| --- | --- |
| test1_completed | Прошел тестирование (Тест 1) |
| waiting_slot | Ждет назначения слота |
| stalled_waiting_slot | Долго ждет слота (>24ч) |
| interview_scheduled | Назначено собеседование |
| interview_confirmed | Подтвердился (собес) |
| interview_declined | Отказ на этапе собеседования |
| test2_sent | Прошел собес (Тест 2 отправлен) |
| test2_completed | Прошел Тест 2 (ожидает ОД) |
| test2_failed | Не прошел Тест 2 |
| intro_day_scheduled | Назначен ознакомительный день |
| intro_day_confirmed_preliminary | Предварительно подтвердился (ОД) |
| intro_day_declined_invitation | Отказ на этапе ОД (приглашение) |
| intro_day_confirmed_day_of | Подтвердился (ОД в день) |
| intro_day_declined_day_of | Отказ (ОД в день) |
| hired | Закреплен на обучение |
| not_hired | Не закреплен |

## Допустимые переходы (STATUS_TRANSITIONS)
Каждый переход валиден только из указанных состояний (без `force`). Назад по прогрессии — no-op.

| FROM | TO | Кто триггерит | Основные эффекты |
| --- | --- | --- | --- |
| test1_completed | waiting_slot / interview_scheduled | Bot (`services.set_status_waiting_slot`), слот-логика | Нет |
| waiting_slot | stalled_waiting_slot / interview_scheduled | Cron/бот (нет явного триггера в коде для stalled), рекрутер подтверждает слот | Нет |
| stalled_waiting_slot | interview_scheduled | Рекрутер | Нет |
| interview_scheduled | interview_confirmed / interview_declined / test2_sent | Кандидат подтверждает / отклоняет; рекрутер может пропустить подтверждение | Сообщения в боте, отметка слота |
| interview_confirmed | test2_sent / interview_declined / intro_day_scheduled | Бот после интервью (handlers/interview.py) | Отправка Тест 2 или прямая запись на ОД |
| interview_declined | — | Терминальный | — |
| test2_sent | test2_completed / test2_failed | Бот (`services.finalize_test2`) | Сохранение результата теста, запись отчета, уведомления |
| test2_completed | intro_day_scheduled | Бот/админ назначает ОД (`services.set_status_intro_day_scheduled`) | Создание слота ОД, уведомление |
| test2_failed | — | Терминальный | — |
| intro_day_scheduled | intro_day_confirmed_preliminary / intro_day_declined_invitation | Бот-напоминания ОД | Уведомления кандидату |
| intro_day_confirmed_preliminary | intro_day_confirmed_day_of / intro_day_declined_day_of / hired / not_hired | Бот за 2ч, рекрутер в UI | Завершение процесса |
| intro_day_declined_invitation | — | Терминальный | — |
| intro_day_confirmed_day_of | hired / not_hired | Рекрутер | Финал |
| intro_day_declined_day_of | — | Терминальный | — |
| hired / not_hired | — | Терминальные | — |

## Точки изменения статуса (в коде)
- Bot: `backend/apps/bot/services.py` (тесты, напоминания ОД, прямые апдейты), `handlers/interview.py` (start_test2).
- Admin UI: `backend/apps/admin_ui/routers/candidates.py` (ручное HIRED/NOT_HIRED, назначение ОД), `services/slots.py` (тест2 отправка), `services/candidates.py` (legacy update).
- Domain: `backend/domain/repositories.py` (слоты: approve/decline/confirm; ОД decline), `status_service.py` (валидация и записи).

## Побочные эффекты по переходам
- Отправка Тест 2 (`test2_sent`): бот создаёт план рассылки вопросов, записывает `Slot.test2_sent_at`, отправляет сообщения.
- Завершение Тест 2 (`test2_completed`/`failed`): запись TestResult, отчёт `reports/<id>/test2.txt`, уведомления кандидату, смена статуса.
- Назначение/перенос ОД (`intro_day_scheduled`): создание слота `purpose=intro_day`, сообщения кандидату, напоминания (бот-планировщик).
- Подтверждение/отказ ОД: бот сообщения + обновление статуса, возможные шаблоны напоминаний.
- Финальные статусы (`hired`/`not_hired`): чисто статус, без дополнительных сайд-эффектов.

## Наблюдения/расхождения
- `is_status_retreat` превращает откат статуса в no-op (мягкая защита от гонок/повторов).
- Нет транзакционных блокировок при смене статуса + создании слотов (риск двойного ОД при гонке).
- Проверка stalled_waiting_slot отсутствует как фонова задача — переход не используется.

## Гипотезы для тестов
- Все переходы вне `STATUS_TRANSITIONS` без `force` должны падать `StatusTransitionError`.
- Повторный вызов одного и того же перехода должен быть идемпотентным.
- Откат статуса должен быть no-op (как реализовано).
- При отсутствии Redis бот/напоминания должны либо фейлиться предсказуемо, либо логировать — нужно зафиксировать в тестах ожидаемое поведение.
