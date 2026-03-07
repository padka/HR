# GO LIVE RUNBOOK — Recruitsmart Admin

## 1. Preflight (обязательно)
1. Проверить, что P1 из `PRODUCTION_READINESS_REPORT.md` закрыты.
2. Подготовить `.env` в секрет-хранилище (не в git):
   - `ENVIRONMENT=production`
   - `DATABASE_URL=postgresql+asyncpg://<app_user>:<password>@<host>:5432/<db>`
   - `MIGRATIONS_DATABASE_URL=postgresql+asyncpg://<migrator>:<password>@<host>:5432/<db>`
   - `REDIS_URL=redis://<redis-host>:6379/0`
   - `NOTIFICATION_BROKER=redis`
   - `ADMIN_USER`, `ADMIN_PASSWORD`
   - `SESSION_SECRET` (>=32 chars)
   - `BOT_TOKEN`, `BOT_CALLBACK_SECRET` (>=32 chars)
   - `OPENAI_API_KEY` (если `AI_ENABLED=true`)
   - `WEB_CONCURRENCY=2` (минимум для production envelope)
3. Убедиться, что migration user имеет DDL права.

## 2. Backup перед релизом
```bash
# PostgreSQL backup
export PGPASSWORD='<db_password>'
pg_dump -h <db-host> -p 5432 -U <db-user> -d <db-name> -Fc -f backup_pre_release_$(date +%F_%H%M).dump
```

## 3. Сборка релизного образа
```bash
cd /Users/mikhail/Projects/recruitsmart_admin
docker build --target prod -t recruitsmart-admin:release-$(date +%Y%m%d-%H%M) .
# опционально оставить тег latest
docker tag recruitsmart-admin:release-$(date +%Y%m%d-%H%M) recruitsmart-admin:latest
```

## 4. Deploy (compose)
```bash
cd /Users/mikhail/Projects/recruitsmart_admin

# 1) Миграции отдельным шагом
docker compose up -d postgres redis_notifications redis_cache
docker compose up -d migrate

# 2) Запуск сервисов
docker compose up -d admin_ui admin_api bot
```

## 5. Canary и smoke после выкладки
```bash
# health/readiness
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8000/health | jq .
curl -fsS http://127.0.0.1:8000/health/bot | jq .
curl -fsS http://127.0.0.1:8000/health/notifications | jq .
curl -fsS http://127.0.0.1:8100/health | jq .

# быстрый регресс-gate
.venv/bin/python scripts/formal_gate_sprint12.py

# perf gate (mixed 600 rps envelope)
BASE_URL=http://127.0.0.1:8000 ./scripts/perf_gate.sh
```

Canary-порядок:
1. Включить только `admin_ui` + `admin_api`, проверить smoke/login/dashboard/slots/candidates.
2. Включить `bot`, проверить отсутствие `fatal_error_code` в `/health/notifications`.
3. Мониторинг 30-60 минут: 5xx, timeout, outbox queue depth, poll staleness, bot runtime switch.
4. Порог мониторинга: error rate <1%, p95 <250ms, p99 <1000ms.

## 6. Rollback
### 6.1 Быстрый rollback сервисов
```bash
cd /Users/mikhail/Projects/recruitsmart_admin
# откат к предыдущему стабильному образу (пример тега)
docker tag recruitsmart-admin:<previous-stable-tag> recruitsmart-admin:latest
docker compose up -d admin_ui admin_api bot
```

### 6.2 Rollback миграций (только если совместимо и согласовано)
```bash
# пример: откат на одну ревизию
DATABASE_URL='postgresql+asyncpg://<migration_user>:<password>@<host>:5432/<db>' \
ENVIRONMENT=production \
.venv/bin/alembic downgrade -1
```

### 6.3 Проверка после отката
```bash
curl -fsS http://127.0.0.1:8000/health | jq .
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8100/health | jq .
```

## 7. Логи и диагностика
```bash
cd /Users/mikhail/Projects/recruitsmart_admin
docker compose logs --since=30m admin_ui admin_api bot | tail -n 400
```

## 8. Критерий завершения релиза
- Все health endpoints зелёные.
- `formal_gate_sprint12.py` не содержит fail.
- Нет всплеска 5xx/timeout в первые 60 минут.
- Очередь уведомлений не застревает (`outbox_queue_depth` не растёт монотонно, `delivery_state=ok`).
