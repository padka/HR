# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RecruitSmart Admin is an HR recruitment management system with:
- **Admin UI** (`backend/apps/admin_ui/`): FastAPI backend for the SPA, manages candidates, recruiters, slots, and interview scheduling
- **Telegram Bot** (`backend/apps/bot/`): Aiogram-based bot for candidate interactions (Test1/Test2 flows, scheduling)
- **Admin API** (`backend/apps/admin_api/`): SQLAdmin-based API surface

## Development Commands

```bash
# Setup
make install              # Install dev dependencies in .venv

# Database (PostgreSQL required)
make dev-migrate          # Run Alembic migrations using .env.local
python scripts/run_migrations.py  # Direct migration script

# Local development
make dev                  # Start admin UI with dev_server.py (auto-restart on changes)
make dev-admin            # Start admin UI via scripts/dev_admin.sh
make dev-bot              # Start bot via scripts/dev_bot.sh (separate terminal)

# SPA (React/Vite)
npm --prefix frontend/app run dev      # Start SPA dev server
npm --prefix frontend/app run build    # Build SPA bundle (frontend/dist)

# Testing (requires PostgreSQL test DB)
make test                 # Run tests with PostgreSQL (rs:pass@localhost:5432/rs_test)
make test-cov             # Run tests with coverage

# Run a single test
pytest tests/test_workflow_api.py -v
pytest tests/test_slots_generation.py::test_specific_case -v
pytest -k "test_name_pattern" -v
```

## Architecture

### Directory Structure

```
backend/
├── apps/
│   ├── admin_ui/          # FastAPI admin interface
│   │   ├── routers/       # Route handlers (candidates, slots, cities, etc.)
│   │   └── services/      # Business logic services
│   ├── admin_api/         # SQLAdmin API
│   └── bot/               # Telegram bot
│       ├── handlers/      # Bot command/message handlers
│       ├── notifications/ # Notification system
│       └── templates_jinja/ # Message templates
├── core/                  # Shared infrastructure
│   ├── db.py              # Database engine, async_session factory
│   ├── settings.py        # Settings dataclass with env validation
│   ├── cache.py           # Redis cache abstraction
│   └── dependencies.py    # FastAPI DI (get_async_session, get_uow)
├── domain/                # Domain models and business logic
│   ├── models.py          # SQLAlchemy ORM models
│   ├── repositories.py    # Repository pattern implementations
│   └── candidates/        # Candidate-specific domain logic
└── migrations/            # Alembic migrations
```

### Key Patterns

**Database Sessions**: Always use context managers or FastAPI DI:
```python
# In routers - use dependency injection
async def handler(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Model))

# In services - use context manager
async with async_session() as session:
    result = await session.execute(select(Model))
    if obj:
        session.expunge(obj)  # Detach before returning
```

**Settings Access**: Use `get_settings()` from `backend.core.settings` (cached singleton).

**Workflow API**: Candidate state machine at `GET /candidates/{id}/state` and `POST /candidates/{id}/actions/{action}`.

## Environment Configuration

Required environment variables for development:
- `DATABASE_URL`: PostgreSQL connection (e.g., `postgresql+asyncpg://rs:pass@localhost:5432/rs`)
- `SESSION_SECRET`: 32+ character secret for session signing
- `ADMIN_USER` / `ADMIN_PASSWORD`: Admin credentials

Development uses `.env.local` (not committed) which overrides `.env`. Copy from `.env.local.example`.

Key flags:
- `ENVIRONMENT`: `development` / `production` / `test`
- `BOT_ENABLED`: Enable/disable Telegram bot integration
- `NOTIFICATION_BROKER`: `memory` (dev/test) or `redis` (production)
- `ENABLE_LEGACY_STATUS_API`: Feature flag for old status endpoints (off in prod)

## Testing

Tests require a PostgreSQL test database. The Makefile sets up the test environment automatically:
- `ENVIRONMENT=test`
- `DATABASE_URL=postgresql+asyncpg://rs:pass@localhost:5432/rs_test`
- `NOTIFICATION_BROKER=memory`
- Bot disabled

Test markers:
- `@pytest.mark.notifications`: Notification flow tests
- `@pytest.mark.integration`: Slow tests requiring external services
- `@pytest.mark.no_db_cleanup`: Skip database cleanup

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on push to `main`, `testing`, `feature/**`:
1. Spins up PostgreSQL 15
2. Runs migrations
3. Executes smoke tests: `test_prod_config_simple`, `test_session_cookie_config`, `test_admin_state_nullbot`, `test_workflow_contract`, `test_workflow_api`

Branch strategy: Feature branches → `testing` → `main`

## Code Style

- Python 3.11+
- Black (line-length 88), isort, ruff for linting
- Run `pre-commit install` to enable hooks
- Type hints expected; mypy for static analysis

## Important Conventions

1. **Migrations**: Run before starting services. Never auto-migrate on startup.
2. **ORM Objects**: Call `session.expunge(obj)` before returning from functions that create their own session.
3. **Background Tasks**: Never pass session or ORM objects; pass IDs and create new sessions inside tasks.
4. **Production Validation**: `get_settings()` validates production config (PostgreSQL, Redis, strong secrets).
5. **Timezones**: All slots stored in UTC; use `backend.core.timezone_service.TimezoneService` for conversions.
