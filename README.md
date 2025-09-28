# HR Bot Project

## Admin UI
The admin interface is served by a single FastAPI application located at
`backend.apps.admin_ui.app:app`. Any ASGI server (for example, Uvicorn) can
load it directly:

```bash
python3 -m uvicorn backend.apps.admin_ui.app:app
```

## Running tests
Project level tests should be executed with the Python module runner to avoid
PATH issues:

```bash
python3 -m pytest
```

If you prefer to call `pytest` directly, ensure that your shell `PATH` includes
`~/.local/bin` (or the equivalent directory where your Python environment
installs console scripts).
