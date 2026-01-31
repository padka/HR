# Deployment Guide

## Scope
This repository contains:
- FastAPI Admin UI (`backend/apps/admin_ui/app.py`)
- Admin API (`backend/apps/admin_api/main.py`)
- Telegram bot (`backend/apps/bot/app.py`, `bot.py`)
- SPA (React/Vite) served under `/app/*` from `frontend/dist/`

## Local/Dev Run (summary)
- Backend + Bot (dev):
  - Use `scripts/dev_admin.sh` (admin UI) and `scripts/dev_bot.sh` (bot)
  - Or `scripts/dev_crm.sh` to run SPA + admin together (see script for details)
- SPA build:
  - `npm --prefix frontend/app install`
  - `npm --prefix frontend/app run build`
- Migrations:
  - `python scripts/run_migrations.py` (dev/test only)

## Dependencies
- PostgreSQL (required in all environments)
- Redis (notifications + cache) — required in production, optional in development

## Production checklist (minimum)
1. Build the Docker image (includes SPA build).
2. Provide secrets via environment variables (do not commit `.env`).
3. Configure `DATA_DIR` as a persistent volume.
4. Run migrations before starting services (use the `migrate` service if deploying with Docker Compose).
5. Ensure SQLAdmin is protected (admin credentials required).

## Example production run (docker compose)
```bash
export ENVIRONMENT=production
export DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/recruitsmart
export REDIS_URL=redis://redis_notifications:6379/0
export NOTIFICATION_BROKER=redis
export DATA_DIR=/var/lib/recruitsmart_admin
export ADMIN_USER=admin
export ADMIN_PASSWORD="strong-password-here"
export SESSION_SECRET="32+ chars"
export BOT_CALLBACK_SECRET="32+ chars"

docker compose up -d migrate
docker compose up -d
```

## References
- `docs/LOCAL_DEV.md`
- `docs/MIGRATIONS.md`
- `README.md`
- `docker-compose.yml`
