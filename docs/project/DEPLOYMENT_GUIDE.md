# Deployment Guide (Draft)

Status: **Draft placeholder created to unblock work**. This file should be expanded before production use.

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
- PostgreSQL (production) / SQLite (dev/test)
- Redis (cache + notifications) in dev via `docker-compose.yml`

## References
- `docs/LOCAL_DEV.md`
- `docs/MIGRATIONS.md`
- `README.md`
- `docker-compose.yml`

