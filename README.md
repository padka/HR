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
PATH issues:

```bash
python3 -m pytest
```

If you prefer to call `pytest` directly, ensure that your shell `PATH` includes
`~/.local/bin` (or the equivalent directory where your Python environment
installs console scripts).
