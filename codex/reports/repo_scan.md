# Repo scan — HR Admin/Bot

## Languages, frameworks, versions
- **Python** ≥3.11 (`pyproject.toml`): FastAPI 0.112.0, Starlette 0.37.2, Uvicorn 0.30.6, Jinja2 3.1.4, SQLAlchemy[asyncio] 2.0.32, aiofiles 23.2.1, aiosqlite 0.20.0, python-multipart 0.0.9.
- **Bot stack** (dev extras): Aiogram 3.10.0, Redis 5.0.7, APScheduler 3.10.4, sqladmin 0.21.0, Playwright 1.55.0, pytest 8.3.3, httpx 0.27.2.
- **Tooling**: Ruff 0.6.3, Black 24.4.2, isort 5.13.2, mypy 1.11.1, pre-commit 3.8.0 (dev extras).
- **Frontend** (`package.json`): TailwindCSS ^3.4.13 with `@tailwindcss/forms` ^0.5.7, `@tailwindcss/typography` ^0.5.12, PostCSS ^8.4.41, Autoprefixer ^10.4.20. Build target outputs `backend/apps/admin_ui/static/build/main.css`.

## Entry points & runtime commands
- **Admin UI FastAPI** (`backend/apps/admin_ui/app.py`): exported as `app`/`create_app`. Launch via `python3 -m uvicorn backend.apps.admin_ui.app:app` or `make run` (binds 127.0.0.1:8000, loads `.env` before starting).
- **Compatibility shim** (`admin_server/app.py`): re-exports the same FastAPI app for legacy deployments.
- **Telegram bot** (`bot.py` → `backend/apps/bot/app.main`): run with `python bot.py`. The factory `create_application()` wires Aiogram dispatcher, reminder scheduler and database bootstrap.
- **Demo renderer** (`app_demo.py`): lightweight FastAPI app for UI previews; `make demo` runs it under Uvicorn.
- **Database bootstrap**: `make dev-db` wraps `backend.core.bootstrap.ensure_database_ready()` to run migrations/seed data. `tools/recompute_weekly_kpis.py` recalculates KPI snapshots; `make kpi-weekly` automates an 8-week backfill.
- **Diagnostic scripts**: `scripts/dev_doctor.py` validates required env/secrets; `scripts/collect_ux.py` & `tools/render_previews.py` render static previews/screens.

## Templates, static assets & ports
- **Jinja templates** live in `backend/apps/admin_ui/templates/` (e.g. `base.html`, `index.html`, CRUD lists for slots/candidates/recruiters/templates/questions).
- **Static assets** at `backend/apps/admin_ui/static/`: Tailwind source CSS (`css/`), design tokens (`css/tokens.css`), vanilla JS modules (`js/`), build output (`build/main.css`) and UI README. Static files are mounted at `/static` in `create_app()`.
- **Tailwind build**: `npm run build`/`make ui` call `tailwindcss -i backend/apps/admin_ui/static/css/main.css -o backend/apps/admin_ui/static/build/main.css --minify`.
- **Default ports**: Admin UI binds to 8000 via `make run`; Playwright screenshot tests spin up the demo app on 8055 (`tests/test_ui_screenshots.py`).

## Environment variables & config loading
- `.env` loader (`backend/core/env.load_env`) reads key/value pairs into `os.environ` before settings initialisation.
- **Core paths / DB** (`backend/core/settings.py`): `DATA_DIR`, `DATABASE_URL`, `SQL_ECHO`.
- **Admin auth & cookies** (`backend/core/settings.py`, `backend/apps/admin_ui/security.py`): `ADMIN_USER`, `ADMIN_PASSWORD`, `ADMIN_DOCS_ENABLED`, `ADMIN_TRUSTED_HOSTS`, `ADMIN_RATE_LIMIT_ATTEMPTS`, `ADMIN_RATE_LIMIT_WINDOW_SECONDS`, `SESSION_SECRET`, `SESSION_SECRET_KEY`, `SECRET_KEY`, `SESSION_COOKIE_NAME`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, `FORCE_SSL` (FastAPI middleware toggle).
- **Bot integration** (`backend/core/settings.py`, `backend/apps/admin_ui/state.py`): `BOT_ENABLED`, legacy `ENABLE_TEST2_BOT`, `BOT_INTEGRATION_ENABLED`, `BOT_FAILFAST`, `TEST2_REQUIRED`, `BOT_PROVIDER`, `BOT_TOKEN`, `BOT_API_BASE`, `BOT_USE_WEBHOOK`, `BOT_WEBHOOK_URL`, `ADMIN_CHAT_ID`, `REDIS_URL`, `STATE_TTL_SECONDS`.
- **Business defaults & timezone** (`backend/core/settings.py`, `backend/apps/admin_ui/services/kpis.py`): `DEFAULT_COMPANY_NAME`, `REJECTION_TEMPLATE_KEY`, `TZ`, optional `COMPANY_TZ`, `KPI_NOW` (ISO8601 override for metrics).
- `backend/core/settings.validate_settings()` ensures admin creds/session secret placeholders are rejected at startup; failure raises `RuntimeError`.
- Updated `.env.example` lists all variables above with safe defaults/comments.

## Tooling, build & tests
- **Makefile targets**: `install` (pip + npm), `setup`/`bootstrap` (editable install + Playwright browsers), `test` (`python -m pytest`), `ui` (`npm run build`), `codex` (docs tooling), `previews`, `screens` (Playwright UI suite), `doctor`, `demo`, `dev-db`, `kpi-weekly`.
- **Python tests**: Pytest suite under `tests/` (async mode strict). UI regression tests use Playwright against `app_demo` (`tests/test_ui_screenshots.py`).
- **Static analysis**: Ruff, Black, isort, mypy configured via `pyproject.toml`.
- **Docker**: no Dockerfile/Compose shipped; local setup relies on Make targets & virtualenv.

## Critical admin routes (FastAPI)
- `system` router (`backend/apps/admin_ui/routers/system.py`): `/favicon.ico`, health probes `/health`, `/health/bot`, runtime toggles for bot integration.
- `dashboard` (`routers/dashboard.py`): `GET /` renders dashboard counters, bot status, weekly KPIs.
- `slots` (`routers/slots.py`, prefix `/slots`): list (`GET /slots`), creation (`POST /slots/create`, `POST /slots/bulk_create`, `POST /slots` JSON API), updates (`PUT /slots/{id}`), destructive actions (`POST /slots/{id}/delete`, `DELETE /slots/{id}`, `POST /slots/delete_all`, `POST /slots/bulk`), interview outcomes (`POST /slots/{id}/outcome`), reschedule/reject flows.
- `candidates` (`routers/candidates.py`, prefix `/candidates`): listing & filters (`GET /candidates`), CRUD (`POST /candidates/create`, `POST /candidates/{id}/update`, `POST /candidates/{id}/delete`), interview feedback, intro-day messaging, triggering bot Test 2 (`POST /candidates/{id}/slots/{slot_id}/outcome`).
- `recruiters`, `cities`, `templates`, `questions` routers expose analogous CRUD endpoints for their domains; `regions` exposes `/regions/{id}/timezone` lookup.
- `api` router (`routers/api.py`, prefix `/api`): JSON health counters, calendar snapshots, recruiter/city/slot data feeds, template lookup, weekly KPI current/history, city owners, bot integration toggle (`POST /api/bot/integration`).

## Critical bot handlers (Aiogram)
- `common` handlers: `/start` begins interview flow, `/intro` & `/test2` shortcuts, `cb_home_start`, manual contact callbacks, noop hints, fallback text routing.
- `test1`/`test2` handlers: callback data `t1opt:*` for Test 1 options; `answer_*` for Test 2 question responses.
- `slots` handlers: `pick_rec:*`, `refresh_slots:*`, `pick_slot:*` wire candidate scheduling.
- `recruiter` handlers: callbacks `approve:*`, `sendmsg:*`, `reschedule:*`, `reject:*`, plus `/iam` recruiter identification command.
- `attendance` handlers: `att_yes:*`, `att_no:*` manage intro-day confirmation prompts.

## Risks & technical debt
- **No asset manifest/versioning**: Tailwind CLI writes to a fixed `static/build/main.css` and templates reference it directly, so cache-busting relies on manual deploy discipline; missing hashed filenames or manifest helper makes CDN caching brittle.
- **Inline bootstrap script**: `base.html` embeds a sizeable `<script>` in the `<head>` to sync theme/localStorage before CSS loads, forcing `unsafe-inline` in CSP policies or additional nonce plumbing.
- **HTTP Basic only**: Admin protection depends entirely on env-provided `ADMIN_USER`/`ADMIN_PASSWORD` via FastAPI `HTTPBasic`; ensure TLS termination and credential rotation, as there is no first-party UI login or multi-user support.
