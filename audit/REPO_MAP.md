# Repository Map

## Top-level layout
- `admin_server/` – thin compatibility package exposing the FastAPI admin UI application for legacy imports (`app`, `create_app`, `lifespan`).
- `backend/` – primary application source tree (domain models, FastAPI apps, services, migrations).
- `bot.py`, `app_demo.py` – ad-hoc entrypoints wiring the Telegram bot runtime and demo scripts.
- `docs/`, `audit/` – documentation, assessments, and tooling for audits/metrics.
- `Makefile`, `tools/`, `scripts/` – developer experience helpers and automation scripts.
- Frontend assets: `tailwind.config.js`, `postcss.config.cjs`, `backend/apps/admin_ui/static/` (raw CSS/JS, Tailwind build output), `previews/`, `ui_screenshots/`.

## `backend/` internals
- `apps/`
  - `admin_ui/`
    - `app.py` – FastAPI factory, session middleware wiring, bot integration setup, static mount, router registration.【F:backend/apps/admin_ui/app.py†L1-L108】
    - `routers/` – UI routes split by domain (`dashboard.py`, `slots.py`, `candidates.py`, `recruiters.py`, `cities.py`, `regions.py`, `templates.py`, `questions.py`, `system.py`, `api.py`).
    - `services/` – data access and orchestration helpers for UI flows (slots CRUD, recruiters, candidates, dashboard KPIs, bot bridge, etc.).
    - `templates/` – Jinja2 templates for pages, fragments, and emails; includes duplicated style tokens.
    - `static/` – Tailwind source files, duplicated CSS/JS bundles (e.g., `liquid-dashboard 2.css`, `dashboard-calendar 2.js`).
    - `config.py`, `state.py`, `security.py` – UI configuration, session/bot state management, HTTP Basic auth & rate limiting (currently assumes `request.session`).
  - `admin_api/`
    - `main.py` – separate FastAPI app wrapping SQLAdmin views; reuses `ensure_database_ready` at startup.【F:backend/apps/admin_api/main.py†L1-L25】
    - `admin.py` – SQLAdmin model view definitions for Recruiters, Cities, Templates, Slots (requires optional `sqladmin`).【F:backend/apps/admin_api/admin.py†L1-L53】
  - `bot/` – Telegram bot integrations, Redis/Aiogram/HTTP clients referenced directly from admin services (optional deps).
- `core/`
  - `settings.py` – settings loader with implicit defaults, environment validation, session secret handling (generates placeholder secret when env missing).【F:backend/core/settings.py†L1-L214】
  - `db.py` – async/sync SQLAlchemy engine factories, migration bootstrap (missing imports guard, always initialises migrations on import).【F:backend/core/db.py†L1-L72】
  - `bootstrap.py` – ensures schema exists and seeds defaults at startup, regardless of runtime mode.【F:backend/core/bootstrap.py†L1-L114】
  - `env.py` – `.env` loading helper.
- `domain/`
  - `models.py` – declarative SQLAlchemy models, currently contains duplicated `UTCDateTime` definition and logger at both top and bottom of file.【F:backend/domain/models.py†L1-L211】【F:backend/domain/models.py†L212-L313】
  - `repositories.py`, `candidates/`, `template_stages.py` – domain-specific data access helpers.
  - `default_data.py`, `default_questions.py` – bootstrap seed data.
- `migrations/` – Alembic env and version scripts (SQLite-focused seed migrations).

## Supporting assets
- `tests/` – pytest suites for services, API responses, and template rendering (limited coverage).
- `.github/workflows/` – CI jobs (`ci.yml`, `ui-preview.yml`) running lint/tests/build screenshots; lacks audits/commitlint.
- `requirements-dev.txt` – legacy dependency pin list duplicating `pyproject.toml` entries (includes optional bot deps).
- `package.json` / `package-lock.json` – Tailwind build tooling (Node 18/20-compatible).
