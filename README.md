# HR Bot Project

## Admin UI
The admin interface is served by a single FastAPI application located at
`backend.apps.admin_ui.app:app`. Any ASGI server (for example, Uvicorn) can
load it directly:

```bash
python3 -m uvicorn backend.apps.admin_ui.app:app
```

## Telegram bot
The Telegram bot is exposed through a small CLI wrapper (`bot.py`) that calls
the new application factory defined in `backend.apps.bot.app`. To launch the
bot locally, ensure `BOT_TOKEN` is configured (for example via `.env`) and run:

```bash
python bot.py
```

The same behaviour can be reproduced programmatically via
`backend.apps.bot.app.create_application()`.

## Running tests
Project level tests should be executed with the Python module runner to avoid
PATH issues:

```bash
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
