# HR Bot Project

[![CI](https://github.com/OWNER/HR/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/HR/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-85%25+-brightgreen.svg)](https://github.com/OWNER/HR/actions/workflows/ci.yml)

## Admin UI
The admin interface is served by a single FastAPI application located at
`backend.apps.admin_ui.app:app`. Any ASGI server (for example, Uvicorn) can
load it directly:

```bash
python3 -m uvicorn backend.apps.admin_ui.app:app
```

> **Security prerequisites:** configure `ADMIN_USER`, `ADMIN_PASSWORD` and
> `SESSION_SECRET` before starting the service. Placeholder values such as
> `admin`/`change-me` are rejected during startup. For local development over
> HTTP set `SESSION_COOKIE_SECURE=false` to disable automatic HTTPS redirects.

## Telegram bot
The Telegram bot is exposed through a small CLI wrapper (`bot.py`) that calls
the new application factory defined in `backend.apps.bot.app`. To launch the
bot locally, ensure `BOT_TOKEN` is configured (for example via `.env`) and run:

```bash
python bot.py
```

The same behaviour can be reproduced programmatically via
`backend.apps.bot.app.create_application()`.

## Development workflow

The project now provides dedicated Make targets that orchestrate the Python and
frontend tooling. To bootstrap a workstation, initialise the database and run
the full test suite execute the following commands:

```bash
make bootstrap   # install Python (pip/Poetry) and Node dependencies
make dev-db      # apply migrations and seed the default data locally
make test        # execute the Python test suite
```

The bootstrap target prefers Poetry when it is available on the system and
falls back to `pip install -e ".[dev]"` otherwise. It also provisions Playwright
browsers so that UI screenshot tests can run without manual intervention.

The default configuration runs the admin UI with a "NullBot" when `BOT_TOKEN`
is not provided, which allows the smoke checks in CI to execute without access
to Telegram credentials. Refer to `docs/DEVEX.md` for a complete set of backend
and frontend workflows, Playwright usage guidelines, smoke-test procedures and
Liquid Glass token rotation notes.

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

The `/health/bot` endpoint reports the runtime state of the integration
(`enabled`, `ready`, `status`) which simplifies operational diagnostics.

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
`backend/migrations`. Both the web applications and the bot invoke
`backend.core.bootstrap.ensure_database_ready()` during startup, which applies
pending migrations, creates any missing tables from the ORM metadata and
populates the default seed data.

For brand new environments or CI setups you can run the same logic manually:

```bash
python -c "from backend.migrations import upgrade_to_head; upgrade_to_head()"
```

The seeding step is idempotent and can be executed multiple times without
creating duplicate cities, recruiters or test questions.

> **Note:** The latest migrations require PostgreSQL because they rely on concurrent index operations.
