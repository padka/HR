# Operations Runbook

## Overview
The admin platform consists of a FastAPI UI (`backend.apps.admin_ui`), optional SQLAdmin API (`backend.apps.admin_api`), and Telegram bot integrations (aiogram/redis/APScheduler). Database defaults to SQLite but production should run PostgreSQL.

## Startup Procedure
1. Ensure environment variables are configured (see `docs/LOCAL_DEV.md`).
2. Apply migrations via `python -m backend.migrations upgrade head` or rely on `ensure_database_ready()` (auto on startup).【F:backend/core/bootstrap.py†L15-L63】
3. Launch application:
   ```bash
   BOT_ENABLED=0 uvicorn backend.apps.admin_ui.app:app --host 0.0.0.0 --port 8000
   ```
4. If bot integration required, enable redis/aiogram extras and set:
   ```env
   BOT_ENABLED=1
   BOT_INTEGRATION_ENABLED=1
   REDIS_URL=redis://...
   BOT_TOKEN=...
   ```
   After isolation epic, optional services load lazily; until then, install `aiohttp`, `aiogram`, `redis` before startup.

## Health & Monitoring
- **Liveness**: `/health` (temporary). Returns JSON with `database`, `state_manager`, `bot_client`, `bot_integration` statuses; returns 503 if state manager missing.【F:backend/apps/admin_ui/routers/system.py†L23-L65】
- **Bot health**: `/health/bot` probes Telegram API via aiogram when enabled; may block if bot creds invalid.【F:backend/apps/admin_ui/routers/system.py†L67-L145】
- **Planned**: `/healthz` & `/readyz` split with DB latency, bot mode, queue sizes (see roadmap epic 5).
- **Logs**: Standard logging via `uvicorn`. After observability epic, structured logs will include `request_id` and JSON payloads.

## Feature Toggles
| Toggle | Default | Description |
| --- | --- | --- |
| `BOT_ENABLED` | `1` | Enables bot runtime integration. Set `0` for admin-only deployments (requires lazy import fix). |
| `BOT_INTEGRATION_ENABLED` | `1` | Controls runtime switch; also accessible via `/api/bot/integration` POST (protected).【F:backend/apps/admin_ui/routers/api.py†L115-L166】 |
| `FORCE_SSL` | unset | Adds HTTPS redirect middleware when truthy.【F:backend/apps/admin_ui/app.py†L52-L58】 |
| `ADMIN_DOCS_ENABLED` | `0` | Enables `/docs`/`/redoc` for admin UI when set. |
| `SESSION_SECRET_KEY` | auto-generated | Provide strong secret to enable SessionMiddleware; mandatory in prod.【F:backend/apps/admin_ui/app.py†L59-L82】 |
| `ADMIN_TRUSTED_HOSTS` | `localhost,127.0.0.1,testserver` | Restricts Host headers via Starlette middleware.【F:backend/apps/admin_ui/app.py†L44-L53】 |

## Common Failure Modes
| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| `ModuleNotFoundError: aiohttp` on startup | Optional bot deps missing but imported | Install extras or disable bot once isolation epic complete.【82a108†L1-L18】 |
| 500 error on login when sessions disabled | `SESSION_SECRET_KEY` missing; SessionMiddleware skipped but `require_admin` still touches `request.session` | Provide secret and reinstall `itsdangerous`; upcoming fix will guard fallback.【F:backend/apps/admin_ui/security.py†L97-L158】 |
| `/health` returns 503 with `state_manager: missing` | Bot integration disabled or null state manager | Acceptable in admin-only mode post-epic; before fix, treat as warning. |
| Database locked errors | SQLite concurrency | Switch to Postgres in prod or enable WAL, ensure single writer. |

## Deployments
1. Run CI pipeline (lint, tests, UI build, screenshots, audits).
2. Apply migrations (additive only) before deploy.
3. Deploy application (container or process manager).
4. Execute smoke tests:
   ```bash
   curl -f http://host/health
   curl -f http://host/api/health
   curl -f http://host/api/slots?limit=10
   ```
5. If Playwright matrix part of CI, review screenshots for regressions.

## Rollback Procedure
- Rollback code via Git tag or release artifact.
- Restore database from snapshot if destructive migration (not expected; migrations additive only).
- Toggle `BOT_ENABLED=0` or disable new middleware (CSP/report-only) via env for rapid mitigation.
- Document incident in runbook notes and update `docs/ROADMAP.md` tasks.

## Incident Response
1. Capture logs (`uvicorn`, structured log once available).
2. Check `/health` and `/health/bot` for immediate indicators.
3. For auth issues, verify secrets and Trusted Host settings.
4. Escalate to bot team if Telegram API issues persist (include recent `/health/bot` payload).

## Maintenance Tasks
- Rotate `SESSION_SECRET_KEY` quarterly; schedule downtime or session flush.
- Review `pip-audit`/`npm audit` reports each sprint (post-epic instrumentation).
- Refresh Playwright baselines after intentional UI changes.
