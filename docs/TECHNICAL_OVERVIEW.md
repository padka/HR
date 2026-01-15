# Technical Overview

## Scope
This document summarizes the architecture, major components, and operational flow
of the RecruitSmart Admin system. It is a high-level companion to the detailed
procedures in `docs/LOCAL_DEV.md`, `docs/MIGRATIONS.md`, and `README.md`.

## Architecture at a Glance
- Admin UI: FastAPI web app for recruiters and operators.
- Admin API: SQLAdmin + REST endpoints for internal management.
- Telegram Bot: Aiogram worker for candidate interactions.
- Data: PostgreSQL in production, SQLite in dev/test.
- Queues/Cache: Redis (notifications broker + optional cache).

## Key Runtime Flows
1) Candidate lifecycle
   - Candidate data is stored in `users` and related domain tables.
   - Status transitions are managed by the workflow API:
     `GET /candidates/{id}/state` and `POST /candidates/{id}/actions/{action}`.

2) Interview scheduling
   - Slots are stored in the DB and validated against overlap rules.
   - Admin UI exposes manual scheduling, rescheduling, and approval flows.

3) Notifications
   - Bot sends messages via Redis-backed broker (production).
   - Templates are managed through admin UI and cached in the bot.

## Code Structure
- `backend/apps/admin_ui/`: FastAPI admin UI (routers, services, templates, static).
- `backend/apps/admin_api/`: Admin API and SQLAdmin surface.
- `backend/apps/bot/`: Telegram bot handlers, notifications, and templates.
- `backend/core/`: Settings, DB, logging, cache, DI, utilities.
- `backend/domain/`: Domain models, services, workflow, repositories.
- `backend/migrations/`: Alembic migrations and utilities.
- `tests/`: Unit, integration, and e2e coverage.

## Configuration
- `.env.example` is the canonical template (no secrets).
- `.env.local` overrides `.env` for development.
- Production validation is enforced in `backend/core/settings.py`.

Critical production settings:
- `SESSION_SECRET` (>= 32 chars)
- `DATABASE_URL` (PostgreSQL only)
- `REDIS_URL`
- `NOTIFICATION_BROKER=redis`
- `ADMIN_USER` / `ADMIN_PASSWORD`

## Database Migrations
- Apply migrations before starting services.
- Use `python scripts/run_migrations.py` or `make dev-migrate`.
- See `docs/MIGRATIONS.md` for details and safety guidelines.

## Testing
- Core tests: `make test` (requires Postgres test DB).
- Targeted runs: `pytest tests/...`.
- Production config checks: `tests/test_prod_*.py` and
  `tests/test_session_cookie_config.py`.

## Observability
- Health: `/health` (Admin UI), `/` (Admin API).
- Logging: JSON option via `LOG_JSON`.
- Metrics: Prometheus endpoints in `backend/core/metrics.py`.

## Security Notes
- Do not store secrets in git or templates.
- `SESSION_COOKIE_SECURE` and `SESSION_COOKIE_SAMESITE` are enforced in prod.
- Bot tokens must be supplied via environment variables.

## Related Documents
- `README.md`
- `docs/LOCAL_DEV.md`
- `docs/MIGRATIONS.md`
- `docs/DEVEX.md`
- `docs/TECH_STRATEGY.md`
