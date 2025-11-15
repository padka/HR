# HR Bot Project

[![CI](https://github.com/OWNER/HR/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/HR/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-85%25+-brightgreen.svg)](https://github.com/OWNER/HR/actions/workflows/ci.yml)

## Database Migrations

⚠️ **Important:** Database migrations must be run **before** starting any application services.

Migrations are managed using Alembic and should be executed separately to prevent race conditions in multi-instance deployments:

```bash
# Run migrations
python scripts/run_migrations.py
```

For detailed migration documentation, Docker/K8s setup, and troubleshooting, see [docs/MIGRATIONS.md](docs/MIGRATIONS.md).

## Admin UI
The admin interface is served by a single FastAPI application located at
`backend.apps.admin_ui.app:app`. Any ASGI server (for example, Uvicorn) can
load it directly:

```bash
# Run migrations first (required)
python scripts/run_migrations.py

# Then start the admin UI
python3 -m uvicorn backend.apps.admin_ui.app:app
```

For day-to-day development there is also a resilient wrapper that auto-restarts
the server on code changes or unexpected crashes:

```bash
python scripts/dev_server.py
# customize command or watch paths via flags:
python scripts/dev_server.py --cmd "uvicorn backend.apps.admin_ui.app:app --port 8100" --watch backend --watch admin_app
```

### Кандидаты: представления по воронкам

Страница `/candidates` поддерживает два специализированных режима работы, выбираемых через
query‑параметр `pipeline` (и переключатель в UI):

| Pipeline | URL-пример | Описание |
| --- | --- | --- |
| `interview` _(по умолчанию)_ | `/candidates` | Классическая воронка до Test2: поиск, фильтры, канбан и календарь работают с интервальными слотами (`purpose != intro_day`). |
| `intro_day` | `/candidates?pipeline=intro_day` | Отдельная доска кандидатов, прошедших Test2. Показывает стадии «Ждут назначения», «Приглашены», «Подтвердили», «Результат», «Отказались», календарь и список привязаны к слотам `purpose == intro_day`. |

В режиме `intro_day` появляются:

- **Funnel Overview** — карточки с конверсией по стадиям и списком статусов (используется `summary.funnel` из сервиса `list_candidates`).
- **Расширенная таблица** — отдельные колонки для адреса/контакта, ответственного рекрутёра, кнопки «Назначить ОД» и «Переназначить».
- **Фильтры и экспорт** автоматически прокидывают активный `pipeline`, поэтому при переключении режимов сохраняются выбранные города, статусы и пагинация.

API `GET /candidates` и соответствующие сервисы (`list_candidates`, `candidate_filter_options`) принимают параметр `pipeline`, что позволяет UI/автоматизации получать нужное представление без дополнительных маршрутов.

## Notifications Broker (Redis)

Интеграционные тесты для уведомлений и полноценный NotificationService ожидают работающий
Redis. Для локальной разработки достаточно поднять контейнер:

```bash
docker compose up -d redis_notifications
```

Установите `NOTIFICATION_BROKER=redis` и `REDIS_URL=redis://redis_notifications:6379/0`
в `.env`, чтобы сервер и интеграционные тесты использовали Redis вместо InMemory брокера.
Для интеграционных проверок запустите `pytest -m notifications --redis-url redis://localhost:6379/0`
— параметр `--redis-url` также пробрасывается в CI.

Тесты с маркером `notifications` используют InMemory broker, если Redis недоступен, но сценарии
из `tests/integration/test_notification_broker_redis.py` подключаются к указанному `--redis-url` и
автоматически пропускаются, если сервис не запущен.

### Load tests

- Dev sanity: `PYTHONPATH=. python scripts/loadtest_notifications.py --count 200`
- Pre-release baseline: `PYTHONPATH=. python scripts/loadtest_notifications.py --broker redis --count 2000 --rate-limit 50 --metrics-json docs/reliability/<date>-redis.json`

Все артефакты из нагрузочных и эксплуатационных проверок складывайте в `docs/reliability/`
с ISO-датой в имени файла (см. `docs/NOTIFICATIONS_LOADTEST.md`).

### Health endpoints

- `GET /health` — базовый статус БД, state manager и кэша.
- `GET /health/bot` — запускаемость Telegram‑бота и состояние интеграции.
- `GET /health/notifications` — состояние брокера уведомлений, работы воркера/напоминаний и
  факт запуска бота (polling). Для Redis брокера эндпоинт делает лёгкий `PING` и вернёт 503,
  если брокер или воркер недоступны.
- `GET /metrics/notifications` — Prometheus-совместимые метрики (`seconds_since_poll`, `poll_skipped_total`,
  `rate_limit_wait_seconds`, per-type counters и др.) для построения графиков/алертов.

### Sandbox & диагностика

- `PYTHONPATH=. python scripts/e2e_notifications_sandbox.py` — поднимает локальный Telegram sandbox,
  прогоняет кандидат + рекрутер уведомления end-to-end и формирует `NotificationLog` записи.
  Подробности в `docs/NOTIFICATIONS_E2E.md`.

## Telegram bot
The Telegram bot is exposed through a small CLI wrapper (`bot.py`) that calls
the new application factory defined in `backend.apps.bot.app`. To launch the
bot locally, ensure `BOT_TOKEN` is configured (for example via `.env`) and run:

```bash
# Run migrations first (required)
python scripts/run_migrations.py

# Then start the bot
python bot.py
```

The same behaviour can be reproduced programmatically via
`backend.apps.bot.app.create_application()`.

## Development workflow

Install the development dependencies, enable the local Git hooks, and run the
test suite from the project root:

```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pre-commit install
pytest --cov=backend --cov=tests --cov-report=term
```

The default configuration runs the admin UI with a "NullBot" when `BOT_TOKEN`
is not provided, which allows the smoke checks in CI to execute without access
to Telegram credentials.

### Bot integration configuration

The admin UI integrates with the Telegram bot to automatically launch “Test 2”
for candidates whose interview outcome is marked as “passed”. The behaviour can
be tuned through the following environment variables (see `.env.example` for a
quick start template):

| Variable | Default | Description |
| --- | --- | --- |
| `BOT_ENABLED` | `true` | Master switch for the integration. Set to `false` to skip Test 2 dispatches entirely. |
| `BOT_PROVIDER` | `telegram` | Bot provider identifier. Only the Telegram provider is currently supported. |
| `BOT_TOKEN` | _(empty)_ | Telegram bot token. Required when `BOT_ENABLED=true`. |
| `BOT_API_BASE` | _(empty)_ | Optional override for custom Telegram API endpoints. |
| `BOT_USE_WEBHOOK` | `false` | Enable webhook mode for the bot (requires `BOT_WEBHOOK_URL`). |
| `BOT_WEBHOOK_URL` | _(empty)_ | Public webhook endpoint used when `BOT_USE_WEBHOOK=true`. |
| `TEST2_REQUIRED` | `false` | When `true`, a bot failure results in HTTP 503 responses from `/slots/{id}/outcome`. When `false`, the request succeeds and Test 2 is skipped. |
| `BOT_FAILFAST` | `false` | If enabled, the admin UI refuses to start when the bot is misconfigured while `BOT_ENABLED=true`. |
| `BOT_AUTOSTART` | `true` (dev) | When enabled, the Telegram bot long-polling worker starts automatically with the admin server (forced off in production). |
| `LOG_LEVEL` | `INFO` | Global logging verbosity (`DEBUG`, `INFO`, `WARNING`, ...). |
| `LOG_JSON` | `false` | Emit JSON logs to stdout/file when `true`. |
| `LOG_FILE` | _(auto)_ | Override log file path (defaults to `data/logs/app.log`). |

The `/health/bot` endpoint reports the runtime state of the integration
(`enabled`, `ready`, `status`) which simplifies operational diagnostics.

## Security configuration

### Environment variables setup

**IMPORTANT:** Never commit the `.env` file to version control. All sensitive credentials must be configured through environment variables.

Required security settings:

| Variable | Required | Description |
| --- | --- | --- |
| `SESSION_SECRET` | **Yes** | Session signing key. Must be at least 32 characters. Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_PASSWORD` | **Yes** | Admin UI password. Use a strong password (16+ characters, mixed case, numbers, symbols). |
| `ADMIN_USER` | No | Admin UI username (default: `admin`). |
| `BOT_TOKEN` | **Yes** | Telegram bot token from @BotFather. Keep this secret! |

### Deployment checklist

Before deploying to production:

1. Generate a strong `SESSION_SECRET`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. Set a strong `ADMIN_PASSWORD` (do not use the example value).

3. Configure environment variables on your server (do not use `.env` file in production).

4. Verify that `.env` is listed in `.gitignore` (already configured).

5. Remove any `.env` file from your working directory:
   ```bash
   rm .env  # Only if you're using environment variables directly
   ```

### Example: Setting environment variables

**Development (using .env file locally):**
```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

**Production (using system environment):**
```bash
export SESSION_SECRET="your-generated-secret-here"
export ADMIN_PASSWORD="your-strong-password-here"
export BOT_TOKEN="your-telegram-bot-token"
# ... other variables
```

## Runtime data storage

All runtime artefacts (SQLite databases, generated reports, uploaded resumes)
are stored under the directory specified by the `DATA_DIR` environment
variable. If the variable is not provided, the project falls back to the
`data/` folder in the repository root. Within this directory the following
sub-folders are used:

- `reports/` – generated recruiter reports (`report_*.txt`).
- `test1/` – interview questionnaires saved as text files (`test1_*.txt`).
- `uploads/` – user-uploaded files such as resumes.

The directories are created automatically on startup. To keep the repository
clean, point `DATA_DIR` to a location outside the project checkout when
running locally, for example:

```bash
export DATA_DIR="$HOME/hr-bot-data"
mkdir -p "$DATA_DIR"/reports "$DATA_DIR"/test1 "$DATA_DIR"/uploads
```

The bot uses SQLite by default with a database file located inside `DATA_DIR`
(`bot.db`). You can override the connection string via the `DATABASE_URL`
environment variable.

## Running tests
Project level tests should be executed with the Python module runner to avoid
PATH issues. The test suite relies on optional dependencies that are not part
of the standard library, therefore make sure to install the development
requirements before invoking pytest:

```bash
pip install -r requirements-dev.txt
python3 -m pytest
```

If you prefer to call `pytest` directly, ensure that your shell `PATH` includes
`~/.local/bin` (or the equivalent directory where your Python environment
installs console scripts).

## Database migrations and seed data

The database schema is managed through Python migration scripts located under
`backend/migrations`. Both the web applications and the bot call
`backend.core.db.init_models()` during startup, which upgrades the database to
the latest revision and applies the default seed data.

For brand new environments or CI setups you can run the same logic manually:

```bash
python -c "from backend.migrations import upgrade_to_head; upgrade_to_head()"
```

The seeding step is idempotent and can be executed multiple times without
creating duplicate cities, recruiters or test questions.

> **Note:** The latest migrations require PostgreSQL because they rely on concurrent index operations.
