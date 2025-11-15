# ТЗ: Улучшение подсистем уведомлений и эксплуатационной готовности

Основание: аудит ND21 от 2025-11-13 (`ND21.md`). Цель работ — устранить выявленные риски (InMemory-брокер в тестах, предупреждения Starlette, отсутствие e2e нагрузки) и повысить готовность системы RecruitSmart Admin к промышленной эксплуатации.

## 1. Задачи для разработчика

### 1.1 Поддержка Redis в тестовой и CI-среде
- **Описание**: подготовить repeatable окружение (docker-compose сервис `redis_notifications` или ephemeral Redis в CI) и обновить пайплайн, чтобы интеграционные тесты с маркером `notifications` выполнялись против Redis.  
- **Результат**: `pytest -m notifications` больше не пропускает `tests/integration/test_notification_broker_redis.py`; документация (`docs/NOTIFICATIONS_LOADTEST.md`) дополнена шагами запуска Redis в CI/локально.

### 1.2 Нагрузочное тестирование Redis-брокера
- **Описание**: расширить `scripts/loadtest_notifications.py` флагами `--duration`/`--count`, добавить экспорт метрик в CSV/JSON и интегрировать в CI job `notification-loadtest`.  
- **Порог**: при `--broker redis --count 2000` средняя задержка публикации < 100 мс, нет ошибок подключения, `rate_limit_wait_seconds` не растёт линейно. Порог записать в README/ND21 дополнении.

### 1.3 Устранение DeprecationWarning Starlette
- **Описание**: обновить вызовы `TemplateResponse` и `TestClient` (`allow_redirects` → `follow_redirects`), убедиться, что предупреждения пропадают.  
- **Артефакты**: unit-тесты подтверждают отсутствие warning; добавить регрессионный тест/pytest-маркер, запрещающий DeprecationWarning (например, `filterwarnings = error::DeprecationWarning` для starlette).

### 1.4 Мониторинг и алерты уведомлений
- **Описание**: обогащение `/health/notifications` данными `rate_limit_wait_seconds`, `poll_skipped_total`, `seconds_since_poll`; добавить Prometheus/Grafana экспорты.  
- **Документация**: обновить `docs/NOTIFICATIONS_LOADTEST.md` и README раздел “Notifications Broker” с новыми метриками и рекомендациями по alert thresholds.

### 1.5 E2E тест Telegram-поставки
- **Описание**: реализовать скрипт/fixture, который поднимает Telegram sandbox (mock API) и воспроизводит передачу сообщения кандидату и рекрутеру end-to-end, включая запись в `NotificationLog`.  
- **Критерий**: скрипт возвращает 0, создаётся как минимум один реальный лог с `delivery_status=sent`, прикладывается инструкция запуска.

## 2. Задачи для тестировщика

### 2.1 Регрессия после включения Redis
- **Сценарии**:
  - Запуск `pytest -m notifications` в окружении с Redis; убедиться, что ранее пропущенные тесты проходят.
  - Smoke-тест `/health/notifications` при остановленном Redis — ожидается `503` + корректный reason.

### 2.2 Нагрузочные проверки
- **Сценарий**: выполнить `scripts/loadtest_notifications.py --broker redis --count 2000 --rate-limit 50` и зафиксировать латентность, throughput, отсутствие ошибок.  
- **Отчёт**: приложить графики/metabase-скрины и CSV из расширенного скрипта.

### 2.3 E2E Telegram delivery
- **Сценарий**: использовать новый sandbox для прогонки Test1 → уведомление рекрутёру, напоминание кандидату. Проверить появление записей в `NotificationLog`, корректность PDF, отсутствие дублей.  
- **Наблюдения**: валидировать retry/backoff при симуляции 500/502 ответов.

### 2.4 Мониторинг и алерты
- **Сценарий**: вручную повышать `poll_interval`/`rate_limit_wait_seconds`, проверять, что алерты срабатывают (Grafana/Alertmanager).  
- **Критерий**: alert fire < 60 сек от нарушения, супрессия после нормализации.

## 3. Общие требования и приемка
1. Все изменения сопровождаются обновлёнными инструкциями (README, docs/NOTIFICATIONS_LOADTEST.md, ND21.md addendum).
2. CI-pipeline включает:
   - `python3 -m pytest`
   - `pytest -m notifications --redis-url ...`
   - `scripts/loadtest_notifications.py --broker redis --count 2000`
3. Warning Starlette не фиксируются в pytest output; добавить блокер в CI (fail on warning).
4. Приёмка выполняется командой эксплуатации: проверяют health-эндпоинты, новые метрики, нагрузочный отчёт, e2e скрипт.
5. Все артефакты (графики, отчёты load-test, инструкции sandbox) складываются в `docs/reliability/` с хронологией спринта.

Исполнение задач считается успешным после двусторонней сдачи (разработчик → тестировщик → заказчик) и обновления ND21 с новым разделом “Post-TZ verification”.
