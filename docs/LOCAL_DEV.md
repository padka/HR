# Local Development Guide

## Prerequisites
- **Python**: 3.12.x recommended (3.11 works with warnings until DX epic completes). Use `pyenv` or `asdf` to manage versions.【F:pyproject.toml†L21-L39】【F:audit/DEPS.md†L1-L12】
- **Node.js**: 20.x (LTS). Install via `nvm`/`asdf`.
- **Package managers**: `uv` (or `pipx + pip-tools`), `npm` (or `pnpm`).
- **SQLite**: Bundled with Python; no external DB required for local smoke.

## Environment setup
```bash
# Clone repository
$ git clone git@github.com:example/hr-admin.git
$ cd hr-admin

# Create virtual environment
$ uv venv --python=3.12
$ source .venv/bin/activate

# Install core app + extras (temporary until extras split)
$ pip install -e .[dev]

# Install pre-commit hooks (after epic 1 lands)
$ pre-commit install

# Install Node deps
$ npm install
```

### Environment variables
Create `.env` (loaded by `backend/core/env.py`) with safe defaults:
```
ADMIN_USER=demo
ADMIN_PASSWORD=demo
SESSION_SECRET_KEY=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJ
BOT_ENABLED=0
ADMIN_DOCS_ENABLED=1
```
Additional toggles (see `docs/RUNBOOK.md`) cover Redis, Telegram bot, rate limits, and secure headers.

## Day-to-day commands
| Command | Description |
| --- | --- |
| `make setup` | Validate Python/Node toolchain, install deps (to be updated with `uv` + extras). |
| `make ui` | Run Tailwind build (`npm run build:css`). |
| `make run` | Start FastAPI admin UI (`uvicorn backend.apps.admin_ui.app:app`). Requires DB access; on first run seeds defaults. |
| `BOT_ENABLED=0 make run` | Launch admin UI without bot runtime (fails today because of eager imports; fix in Runtime Stability epic). |
| `make screens` | Execute Playwright screenshot suite (requires `playwright install`). |
| `make lint` | Run ruff/black/isort/mypy (after DX epic wires pre-commit). |
| `pytest` | Run Python test suite (unit/integration). |

## Troubleshooting
- **`ModuleNotFoundError: aiohttp`**: Install optional bot deps or set `BOT_ENABLED=0` after lazy-import refactor.【82a108†L1-L18】
- **Session-related 500s**: Ensure `SESSION_SECRET_KEY` provided and `pip install itsdangerous==2.2.0` until DX fixes optional dependency check.【F:backend/apps/admin_ui/app.py†L44-L78】
- **Database locked**: SQLite file located under `data/bot.db`; delete for clean slate (reseed will occur on next run).【F:backend/core/bootstrap.py†L15-L63】

## Future improvements (tracked in roadmap)
- Replace editable install with extras (`core`, `dev`, `bot`) and reproducible lockfiles.
- Add `make doctor` to assert Python/Node versions, env vars, and optional services.
- Provide Docker-based local stack after optional Release Container epic.
