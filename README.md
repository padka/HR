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
