# Dependency Inventory

## Python runtime
- **Interpreter**: Project metadata targets Python `>=3.11`, while tooling/docs expect 3.12/3.13 – mismatch noted for DX alignment.【F:pyproject.toml†L1-L49】
- **Core dependencies** (`pyproject.toml`): FastAPI 0.112, Starlette 0.37, Uvicorn `[standard]` 0.30, SQLAlchemy 2.0 (async), `itsdangerous`, `Jinja2`, `python-multipart`, `aiofiles`, `aiosqlite`, `greenlet` – all pinned exact.【F:pyproject.toml†L21-L39】
- **Optional groups**: single `dev` extra bundles bot runtime (`aiogram`, `aiohttp`, `redis`, `httpx`), tooling (pytest, Playwright, linting, Alembic), and SQLAdmin – no separation between prod/dev/bot concerns.【F:pyproject.toml†L41-L60】
- **Legacy pins**: `requirements-dev.txt` duplicates/extends the same packages, increasing drift risk (e.g., `sqladmin`, `APScheduler`, `fakeredis`).【F:requirements-dev.txt†L1-L25】
- **Bootstrap coupling**: `backend/core/db.py` imports migrations on module import, requiring Alembic even for read-only contexts; `backend/apps/admin_ui/services` import `backend.apps.bot.services`, which depends on optional `aiohttp`/`aiogram`.【F:backend/core/db.py†L1-L72】【F:backend/apps/admin_ui/routers/api.py†L15-L18】

## Node/Tailwind toolchain
- `package.json` defines a single script `build:css` invoking Tailwind CLI; devDependencies pinned loosely (`^` ranges) for Tailwind 3.4, PostCSS, Autoprefixer, Tailwind plugins.【F:package.json†L1-L17】
- `package-lock.json` captures a Node 20-compatible lock but is committed, requiring manual sync.

## Observed issues
- Optional bot deps are imported eagerly (e.g., `backend/apps/admin_ui/services/slots.py` references bot services), causing runtime import errors when extras are missing – evidenced by audit tools failing without `aiohttp` installed.【F:backend/apps/admin_ui/services/slots.py†L17-L33】
- Session middleware relies on `itsdangerous`; missing wheel disables sessions but leaves code paths calling `request.session`, leading to 500s.【F:backend/apps/admin_ui/app.py†L44-L78】【F:backend/apps/admin_ui/security.py†L97-L158】
- No dependency health tooling configured (no `deptry`, `pip-audit`, `npm audit` integration) despite instructions; CI workflows only run lint/tests/screenshots.【F:.github/workflows/ci.yml†L1-L94】

## Alignment actions (Phase 1 targets)
1. Split extras (`core`, `dev`, `bot`) and drop `requirements-dev.txt` in favour of `uv`/`pip-tools` lock exports.
2. Enforce Python 3.12+/Node 20 in `dev_doctor` and CI matrix; document fallback for 3.11 as warn-only until migration completes.
3. Add supply-chain checks (`pip-audit`, `npm audit`, `deptry`) and pre-commit with `ruff/black/isort`.
4. Gate optional bot imports behind feature flags/null objects to avoid mandatory installs for admin-only usage.
