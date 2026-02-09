# HR Bot Project

[![CI](https://github.com/OWNER/HR/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/HR/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-85%25+-brightgreen.svg)](https://github.com/OWNER/HR/actions/workflows/ci.yml)

## Documentation index

- Technical overview: [docs/TECHNICAL_OVERVIEW.md](docs/TECHNICAL_OVERVIEW.md)
- Candidate profile UX/API: [docs/candidate_profile.md](docs/candidate_profile.md)
- Local dev guide: [docs/LOCAL_DEV.md](docs/LOCAL_DEV.md)
- Migrations: [docs/MIGRATIONS.md](docs/MIGRATIONS.md)
- DevEx notes: [docs/DEVEX.md](docs/DEVEX.md)
- UI strategy: [docs/TECH_STRATEGY.md](docs/TECH_STRATEGY.md)

## Локальная разработка (PostgreSQL обязателен)

Для локальной разработки создайте файл `.env.local` для переопределения настроек production:

```bash
# Копируем пример конфигурации для разработки
cp .env.development.example .env.local
```

Файл `.env.local` автоматически загружается после `.env` и может переопределять настройки. Он не коммитится в git.

**Важно:** Файл `.env` содержит настройки production (`ENVIRONMENT=production`), что требует PostgreSQL и Redis. Файл `.env.local` переопределяет это на `ENVIRONMENT=development`, но **PostgreSQL остаётся обязательным**. В development допускается in‑memory брокер уведомлений, но не SQLite как основная БД.

## Быстрый старт (dev/test)

```bash
python3 -m venv .venv
. .venv/bin/activate
make install            # ставит dev-зависимости (pytest и пр.)
docker compose up -d postgres
make test               # тесты используют PostgreSQL (DATABASE_URL=.../rs_test из Makefile)
```

Переменные окружения для `make test` выставляются автоматически (ENVIRONMENT=test, DATABASE_URL=postgresql+asyncpg://rs:pass@localhost:5432/rs_test, NOTIFICATION_BROKER=memory, ADMIN_USER/PASSWORD=admin). Брокер уведомлений и бот отключены.

## Ветки и CI (обязательно)

- Рабочие ветки: `main` (стабильная), `testing` (интеграционная), фичи — `feature/*`.  
- PR только в `testing`; после стабилизации — PR из `testing` в `main`.  
- Протекции: no force-push; `main` — обязательные проверки + 1 review; `testing` — обязательные проверки.  
- CI (см. `.github/workflows/ci.yml`): поднимает Postgres, запускает `scripts/run_migrations.py`, потом smoke‑pytest (`test_prod_config_simple`, `test_session_cookie_config`, `test_admin_state_nullbot`).
- Обязательные файлы: `.env.example` (шаблон окружения), `CHANGELOG_DEV.md` (фиксировать изменения и проверки).
- Фича-флаг для старого эндпоинта статусов: `ENABLE_LEGACY_STATUS_API` (по умолчанию выключен в dev/staging, в prod обязательно выключен; включать только для отладки/тестов).
  - Новый контракт статусов: `GET /candidates/{id}/state` возвращает `status` + `allowed_actions`; действия — `POST /candidates/{id}/actions/{action}` (см. tests/test_workflow_api.py).

## Обновление зависимостей

- Dependabot создаёт PR для Python (pip/pyproject) и Node (npm) по расписанию:
  - Python: по понедельникам в 06:00 (Europe/Moscow), группировка на prod/dev зависимости.
  - Node: по понедельникам в 06:30 (Europe/Moscow), группировка всех npm пакетов.
- PR помечаются лейблом `dependencies`; перед merge прогоняйте CI и проверяйте ключевые сценарии.
- Security-аудиты:
  - GitHub Actions workflow `Dependency audit` запускается по изменениям файлов зависимостей и раз в неделю (понедельник 07:00 MSK).
  - Локально можно запустить:
    - `pip-audit -r requirements.txt -r requirements-dev.txt`
    - `npm audit --audit-level=high`
- Перед релизом используйте чеклист: [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md).

## Локальный запуск (Postgres + Redis в Docker)

Подготовка:
1. Поднимите контейнеры Postgres и Redis (пример: `docker compose up -d postgres redis_notifications` или существующие `rs-postgres`/`rs-redis`).
2. Скопируйте шаблон: `cp .env.local.example .env.local` и заполните `BOT_TOKEN`, при необходимости обновите `SESSION_SECRET`.
3. Установите зависимости: `make install`.

Запуск:
1. `make dev-migrate`
2. `make dev-admin`  (админка на http://localhost:8000)
3. `make dev-bot`    (отдельный процесс, polling)

Примечания:
- Бот — отдельный процесс (`bot.py`). Админка умеет жить с NullBot при пустом токене, но сам бот без валидного `BOT_TOKEN` не стартует.
- Скрипты `scripts/dev_admin.sh` / `scripts/dev_bot.sh` сами подхватывают `.env.local` (или `.env.local.example`) и предупреждают, если в оболочке висит конфликтный `BOT_TOKEN` (dummy).
- Не запускайте несколько экземпляров бота одновременно: параллельный polling (двойной `getUpdates`) приводит к `TelegramConflictError` в логах.
- Проверка токена (без вывода значения):  
  `python -c "from backend.core.env import load_env; load_env('.env.local'); import os; print('BOT_TOKEN has colon:', ':' in os.getenv('BOT_TOKEN',''))"`

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
- Порты ниже 1024 требуют root. Используйте 8000/8100 (по умолчанию) вместо 800, чтобы избежать проблем с CSRF/сессией в dev.

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

### Telegram контакты кандидата

- Как только кандидат пишет боту (команда, сообщение или нажатие кнопки), middleware бота сохраняет `telegram_user_id`, `telegram_username` и время связи в профиле кандидата.
- В карточке кандидата в админке появился блок «Telegram»: кнопки «Открыть чат», «Скопировать username/TG ID» и fallback‑инструкция с `tg://user?id=<id>` если username скрыт.
- В таблицах, календаре и карточках подсказок выводится та же информация, поэтому рекрутёр всегда видит deeplink и может скопировать идентификатор в один клик.
- Админка не отправляет сообщения от лица рекрутера — блок лишь помогает открыть чат или скопировать данные для ручного контакта.

### Чат с кандидатом

- На странице кандидата есть раздел «Чат (Telegram)» с последними сообщениями, индикатором статуса доставки и кнопкой «Загрузить ещё».
- Отправка сообщений выполняется через Telegram Bot API: каждое сообщение сохраняется в `chat_messages` со статусами `queued/sent/failed`, поддерживается повторная отправка.
- Входящие сообщения логируются ботом как `inbound` и отображаются в карточке после обновления (или через кнопку «Обновить»). Реалтайма нет, но добавлен 5‑секундный поллинг.
- Для быстрых ответов есть набор шаблонов (Напоминание, Подтвердите время и т.д.), которые подставляют текст одним кликом.

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

## Deployment / Production run

The repository now ships with a minimal docker-compose stack that can be used for
production-like deployments or staging smoke tests. It creates five services:

| Service            | Port  | Description |
| ------------------ | ----- | ----------- |
| `postgres`         | 5432  | Primary application database (AsyncPG access from apps). |
| `redis_notifications` | 6379 | Notification broker / state store for the bot. |
| `redis_cache`      | 6380  | Optional cache instance used by the admin UI. |
| `admin_ui`         | 8000  | FastAPI admin interface (`backend.apps.admin_ui.app`). |
| `admin_api`        | 8100  | FastAPI admin API/SQLAdmin surface (`backend.apps.admin_api.main`). |
| `bot`              | n/a   | Telegram worker (`bot.py`) that consumes Redis queues. |

### Prepare configuration

1. Copy `docker-compose.env.example` to `.env` (or pass it via `docker compose --env-file`).
2. Replace placeholder values:
   - Generate a real `SESSION_SECRET`.
   - Set `ADMIN_PASSWORD` and `POSTGRES_PASSWORD` to strong values.
   - Provide a valid `BOT_TOKEN` from @BotFather (the bot container refuses to start otherwise).

### Run the stack

```bash
# Build the shared image once
docker compose build

# Run migrations (one-off). The admin_ui/admin_api/bot services
# depend on this step via the migrate service.
docker compose up -d migrate

# Start everything (-d for detached)
docker compose up -d

# Tail logs for specific services
docker compose logs -f admin_ui
docker compose logs -f bot
```

Healthchecks expose `/health` for the UI and `/` for the Admin API, so you can
verify status quickly:

```bash
curl -f http://localhost:8000/health
curl -f http://localhost:8100/
```

The bot container reports readiness once it connects to Redis and Telegram. If
you run without a valid token you can temporarily set `BOT_ENABLED=false` to skip
startup, but for production you must provide credentials.

All containers share the same image defined in `Dockerfile`, so the build result
is cached and used by the Admin UI, Admin API and the bot service.

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

Интерпретация статусов:

- `/health/bot`:
  - `status=disabled` + `runtime.disabled_by=config|operator` — бот выключен намеренно.
  - `status=error` + `runtime.switch_source=runtime` + `runtime.switch_reason=telegram_unauthorized` — токен бота отклонён Telegram, требуется ротация токена и рестарт.
- `/health/notifications`:
  - `notifications.fatal_error_code=telegram_unauthorized` и `notifications.delivery_state=fatal` — доставка остановлена из‑за фатальной ошибки токена.
  - HTTP `503` означает деградацию воркера/брокера или фатальную ошибку доставки.
  - `status=disabled` (HTTP `200`) — интеграция выключена через конфиг/оператора.

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
pip install -e ".[dev]"
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

## Troubleshooting (dev)
- `BOT_TOKEN invalid → NullBot` — админка продолжит работать, но бот не будет принимать обновления. Для реального бота заполните `BOT_TOKEN` в `.env.local` и перезапустите `make dev-bot`.
- В оболочке лежит `BOT_TOKEN=dummy_token` → скрипты `dev_admin.sh/dev_bot.sh` предупреждают и игнорируют его; иначе вручную `unset BOT_TOKEN`.
- `password authentication failed for user ...` → проверьте `DATABASE_URL` пользователя/пароль/БД. Для docker rs-postgres: `postgresql+asyncpg://rs:pass@localhost:5432/rs`.
- Проверка Postgres в контейнере:  
  `docker exec rs-postgres psql -U rs -d rs -c "\dt"`  
  `docker exec rs-postgres psql -U rs -d rs -c "select * from alembic_version;"`
- Быстрый smoke токена (без вывода значения):  
  `python -c "from backend.core.env import load_env; load_env('.env.local'); import os; print('BOT_TOKEN has colon:', ':' in os.getenv('BOT_TOKEN',''))"`
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

### Централизованное управление контентом бота

- В админке (`/app/system`) добавлен блок **Контент бота**:
  - быстрые переходы к управлению вопросами (`/app/questions`) и шаблонами (`/app/message-templates`, `/app/templates`);
  - единая настройка политики напоминаний (вкл/выкл и смещения по часам).
- API для политики напоминаний:
  - `GET /api/bot/reminder-policy`
  - `PUT /api/bot/reminder-policy`
- Политика хранится в БД и применяется ботом при планировании/исполнении напоминаний.

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

All runtime artefacts (generated reports, uploaded resumes, logs) are stored
under the directory specified by the `DATA_DIR` environment variable. If the
variable is not provided, the project falls back to
`~/.recruitsmart_admin/data` (outside the repository tree). Within this
directory the following sub-folders are used:

- `reports/` – generated recruiter reports (`report_*.txt`).
- `test1/` – interview questionnaires saved as text files (`test1_*.txt`).
- `uploads/` – user-uploaded files such as resumes.
- `logs/` – application logs.

The directories are created automatically on startup. In production, mount
`DATA_DIR` as a persistent volume to avoid losing reports and logs on restart.

### Database quick start

**PostgreSQL (local docker / staging):**

```bash
python -m pip install asyncpg
docker compose up -d postgres
DATABASE_URL=postgresql+asyncpg://recruitsmart:recruitsmart@localhost:5432/recruitsmart make dev
```

The Admin UI logs the active dialect (passwords are masked) and fails fast with
a short `RuntimeError` if the required async driver (`asyncpg`) is missing.

## Self-healing dev server

During day-to-day work you no longer need to restart Uvicorn manually every
time a file changes or the process crashes. The `scripts/dev_server.py`
wrapper keeps the admin UI online by supervising the actual Uvicorn command
and watching the project tree for changes:

```bash
# installs the watcher dependencies and launches the resilient server
pip install -e ".[dev]"
make dev
```

`make dev` respects `DATABASE_URL` from your shell or `.env` — for example,
to connect to a local PostgreSQL instance. Use `make dev-postgres` to keep
the same settings but print a reminder about asyncpg requirements.

The helper does three things for you:

1. Starts the FastAPI admin UI with Uvicorn (default host: `127.0.0.1:8000`).
2. Restarts the process automatically when Python/HTML/TS files under
   `backend/`, `scripts/`, `tests/`, or `docs/` change.
3. Brings the server back up if it exits unexpectedly (for example, because of
   an exception during startup).

You can customise the command or watch paths without editing the script:

```bash
# Run on a different port and also watch the frontend bundle directory
DEVSERVER_CMD="uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port 8100" \
DEVSERVER_WATCH="backend frontend scripts" \
make dev
```

If you prefer to run the supervisor directly, call:

```bash
ENVIRONMENT=development REDIS_URL="" \
DEVSERVER_CMD="uvicorn backend.apps.admin_ui.app:app --port 8000" \
python scripts/dev_server.py --watch backend --watch scripts
```

Once running, every change to the watched paths or an unexpected crash triggers
an automatic restart, so you can concentrate on coding rather than retyping
commands.

If the child process crashes three times within 10 seconds, or if the database
driver is missing (`asyncpg`), the supervisor prints actionable hints and exits
instead of looping endlessly.

## Running tests
Project level tests should be executed with the Python module runner to avoid
PATH issues. The test suite relies on optional dependencies that are not part
of the standard library, therefore make sure to install the development
requirements before invoking pytest:

```bash
pip install -e ".[dev]"
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
