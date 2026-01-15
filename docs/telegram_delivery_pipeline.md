# Надёжная доставка исходящих сообщений в Telegram

Документ описывает устройство и эксплуатацию механизма гарантированной доставки, который теперь применяем для всех исходящих уведомлений Telegram.

## Архитектура
- **Фиксация намерения** — любой сервис вызывает `add_outbox_notification`, запись попадает в таблицу `outbox_notifications` со статусом `pending`, счётчиком попыток и `next_retry_at`. Это единственный источник истины.
- **Брокер** — `NotificationService` при наличии `REDIS_URL` использует Redis Streams (`NotificationBroker`). При запуске воркер автоматически выгружает задолженность из outbox в брокер, учитывая `next_retry_at`, и гарантированно переочередит просроченные записи.
- **Потребитель** — `NotificationService` читает из брокера, учитывает заголовок `X-Telegram-Bot-API-Request-ID`, токен-бакет (`rate_limit_per_sec`) и ретраи (экспоненциальный backoff + jitter, `retry_after`). При временных ошибках сообщение переносится вперёд, при постоянных — отправляется в DLQ и помечается в журнале.
- **Failover** — если брокер недоступен или очередь пуста, воркер автоматически переключается на прямую обработку `outbox_notifications` (режим «outbox_fallback»), поэтому сообщения не теряются даже при деградации Redis.
- **Идемпотентность** — комбинированный ключ `(type, booking_id, candidate_tg_id)` и журнал `notification_logs` предотвращают повторную фактическую отправку.

## Конфигурация
- `BOT_ENABLED` — включает/отключает бота целиком.
- `BOT_TOKEN`, `BOT_API_BASE` — доступ к Telegram Bot API.
- `REDIS_URL` — при наличии включает брокер Redis Streams (ключи `bot:notifications`, `bot:notifications:dlq`). При отсутствии используется in-memory broker (подходит только для разработки).
- `BOT_FAILFAST` — при `true` падение инициализации бота/брокера останавливает приложение.
- `STATE_TTL_SECONDS`, `ADMIN_*` — окружение админки, влияют косвенно.
- Параметры воркера настраиваются через переменные окружения:
  - `NOTIFICATION_POLL_INTERVAL` — период опроса APScheduler.
  - `NOTIFICATION_BATCH_SIZE` — размер батча из outbox/брокера.
  - `NOTIFICATION_RATE_LIMIT_PER_SEC` — токен-бакет по Telegram.
  - `NOTIFICATION_RETRY_BASE_SECONDS` / `NOTIFICATION_RETRY_MAX_SECONDS` — backoff.
  - `NOTIFICATION_MAX_ATTEMPTS` — предел попыток до статуса `failed`.
- Тексты уведомлений управляются в админке на странице «Шаблоны уведомлений» (`/message-templates`). Для каждого ключевого события должна существовать активная запись (`channel=tg`, `locale=ru`).

### Как включить/отключить
1. Убедиться, что миграции применены (`alembic upgrade head` или `poetry run backend-manage migrate`).
2. Задать переменные окружения (`BOT_ENABLED=1`, `BOT_TOKEN=...`, `REDIS_URL=redis://...`).
3. Перезапустить `admin_server`/бот (`bot.py`). Повторный запуск безопасен — воркер догонит накопленный outbox.
4. Для выключения: `BOT_ENABLED=0` (воркер остановится, outbox сохранит намерения до повторного включения).

## Наблюдаемость и диагностика
- **Метрики** (экспортируются через `/admin/system` и в Prometheus-адаптере):
  - `notifications_sent_total` / `notifications_failed_total{type}`.
  - `send_retry_total`, `circuit_open_total`.
  - `outbox_queue_depth` — текущий объём работы воркера.
  - `poll_cycle_duration_ms`, `poll_cycle_source_last` помогает понять источник (broker/outbox_fallback).
- **Логи**:
  - `notification.worker.poll_cycle` — завершение цикла (source, processed, skipped_total).
  - `notification.worker.sent` — успешная доставка; содержит `outbox_id`, `booking_id`, `candidate_tg_id`, `attempt`.
  - `notification.worker.retry_scheduled` — планируем повтор (delay, next_retry_at, attempt).
  - `notification.worker.failed` — окончательный отказ; фиксируется ошибка и попадание в DLQ.
  - `notification.worker.poll_error` / `notification.worker.process_item_error` — неожиданные исключения (воркер продолжает работу).
  - `notification.worker.enqueue_failed` — проблемы публикации в брокер.
  - `notification.worker.dlq_error` — ошибки при переносе в DLQ.
  - При отсутствии кастомного шаблона используется резервный текст, но лог уровня WARNING (`Template lookup failed ...; using fallback`) подскажет, что нужно настроить шаблон.
- **SQL**:
  - Очередь: `select id,type,status,next_retry_at,attempts,last_error from outbox_notifications where status='pending' order by id limit 50;`
  - DLQ (Redis): `XRANGE bot:notifications:dlq - + COUNT 20`.
- **Runtime**:
  - REST `/admin/system/state` — блок `queues`/`telegram`.
  - В тестах/локально можно вызвать `await NotificationService._poll_once()` из REPL.

## Алертинг
1. `notifications_failed_total{type}` растёт быстрее `notifications_sent_total{type}` за 5 мин — критический инцидент.
2. `outbox_queue_depth > 100` или не убывает 10+ минут — сбой брокера или лимитов Telegram.
3. `circuit_open_total > 0` — Telegram недоступен; требуется предупредить команду.
4. Наличие записей в Redis DLQ (`XLEN bot:notifications:dlq > 0`) — предупредительный сигнал, нужно расследовать и решить, переотправлять ли вручную.
5. Ошибка конфигурации (`bot_probe` == `bot_not_configured`) — алерт уровня P2.

## Acceptance-сценарии
1. **Массовая отправка** → все сообщения доходят, `outbox_queue_depth` возвращается к 0, rate limit не превышается.
2. **HTTP 429 + retry_after** → сообщение переходит в отложенное состояние, после таймаута отправляется, попыток > 1, дублей нет.
3. **Временные сетевые ошибки** → несколько попыток, success после восстановления сети, журнал фиксирует промежуточные ошибки.
4. **Постоянная ошибка (chat not found)** → сообщение попадает в DLQ, статус `failed`, повторных попыток нет.
5. **Перезапуск воркера** → накопленные записи из `outbox_notifications` автоматически попадают в Redis и доставляются без дублей.
6. **Повторная постановка с тем же ключом** → `add_outbox_notification` сбрасывает статус в `pending`, но фактическая отправка не повторяется (журнал `delivery_status=sent`).

## Масштабирование
1. Убедиться, что используется Redis-брокер (иначе масштабирование не даст эффекта).
2. Запустить дополнительные экземпляры сервиса бота/админки — все они подключатся к той же consumer group (`bot_notification_workers`), сообщения будут распределены.
3. Следить за `outbox_queue_depth` и задержками; при стойком росте увеличивать число воркеров горизонтально.
4. Для повышения throughput можно поднять `rate_limit_per_sec` и `batch_size` воркера, но обязательно мониторить ответы Telegram и ошибки 429.
5. Восстановление после аварий: повторный старт каждого экземпляра безопасен — при инициализации он догружает outbox в брокер и продолжает с того места, где остановился.

## Примечания по безопасности
- Токены хранятся только в переменных окружения; убедитесь, что они не попадают в логи.
- В журналах (`notification_logs`) содержится текст уведомлений; ограничьте доступ к базе.
- Для трассировки используйте `correlation_id` (`outbox:{booking_id}:{uuid}`) — он прокидывается в заголовок Telegram и логи.
