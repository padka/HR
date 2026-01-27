# Project Audit (Draft)

Status: **Draft placeholder created to unblock work**. Expand with a full audit before production changes.

## System Map (high level)
- **Admin UI**: `backend/apps/admin_ui/` (FastAPI + Jinja legacy + SPA mounting)
- **Admin API**: `backend/apps/admin_api/`
- **Bot**: `backend/apps/bot/`
- **SPA**: `frontend/app/` (React + TypeScript + Vite)
- **DB**: PostgreSQL (prod), SQLite (dev/test)
- **Cache/Jobs**: Redis (cache, notifications, jobstore)

## Key Docs
- `docs/TECHNICAL_OVERVIEW.md`
- `docs/access-control.md`
- `docs/migration-map.md`
- `docs/TECH_STRATEGY.md`

## Known Gaps (to verify)
- Deployment runbook is minimal.
- Full production checklist not yet formalized.
- Some legacy Jinja pages still exist alongside SPA.

