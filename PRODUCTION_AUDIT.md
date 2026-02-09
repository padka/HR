# Production Audit: RecruitSmart Admin

Audit date: 2026-02-09  
Code version: `63ba3ae`  
Workspace: `/Users/mikhail/Projects/recruitsmart_admin`

## Executive Summary

Current state: **Release candidate (dev/staging-ready), not yet “prod-hard”**.

What is already green:
- Backend unit/integration suite passes (Postgres and SQLite).
- Frontend build/typecheck/unit/e2e passes.
- Migrations run cleanly against the dev DB.
- Services respond to health endpoints; bot runtime probe works in this environment.

What still blocks “prod confidence”:
- E2E coverage is mostly navigation/a11y. Key business flows (offer/confirm/reschedule/decline/intro-day) are not fully covered at UI level.
- No single “Ops” surface for notification delivery history, retries, reminder jobs, and failure triage (currently visible only via logs/DB).
- Production operational checklist items (backup/monitoring/alerting/secret rotation cadence) are not fully codified end-to-end.

## Verification Runs (This Audit)

Backend:
- `make test` (Postgres): **466 passed, 2 skipped**
- `.venv/bin/python -m pytest -q` (SQLite): **466 passed, 2 skipped**

Frontend (`/Users/mikhail/Projects/recruitsmart_admin/frontend/app`):
- `npm run lint`: **0 errors, warnings only**
- `npm run typecheck`: **OK**
- `npm run test`: **OK** (note: ErrorBoundary test intentionally logs “boom”)
- `npm run test:e2e`: **OK** (27 Playwright tests)

Migrations:
- `make dev-migrate` (using `.env.local`): **OK**

Runtime smoke (local dev):
- Admin UI: `http://localhost:8100/app`
- Health: `http://localhost:8100/health` -> 200
- Bot health: `http://localhost:8100/health/bot` -> 200 with Telegram probe OK in this environment

## Findings (Prioritized)

### P0 (Must Fix Before Real Candidates)
- Add an Ops UI for bot delivery pipeline:
  - outbox queue (`outbox_notifications`) browsing
  - failed items visibility + manual retry
  - reminder jobs (`slot_reminder_jobs`) visibility
  - message logs (`message_logs`) visibility
  Without this, incidents are “blind” and will require DB access/log digging.

- Expand automated scenario coverage for core hiring flows:
  - offer -> confirm
  - offer -> request reschedule -> propose alternative -> confirm (slot replacement)
  - decline flows
  - intro-day invite -> confirm -> reminders -> decline

### P1 (Should Fix In First Production Iteration)
- Reduce frontend lint noise (warnings) to keep signal high in CI.
- Silence/contain expected “boom” logs in `ErrorBoundary` test to avoid masking real errors in CI logs.
- Consolidate/retire legacy slot assignment router (`/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/assignments.py`) if unused, or align it with the canonical slot-assignment service.

### P2 (Nice to Have / Stability)
- Add runtime dashboards/metrics (queue depth, send latency, retry counts) and alert thresholds.
- Add a staging runbook for Telegram bot token rotation + validation steps.

## Release Checklist Additions (Recommended)

- Secrets:
  - ensure `SESSION_SECRET`, `ADMIN_PASSWORD`, `BOT_TOKEN`, `BOT_CALLBACK_SECRET` are set via secret manager, not in repo
  - rotate bot token before production cutover if it was ever shared
- Monitoring:
  - alert on `/health/bot.status in {error,degraded}` and `/health/notifications` 503
  - alert on outbox failed rate and fatal Telegram error codes
- Backups:
  - daily automated Postgres backups with retention policy
  - restore drill documented

## Next Audit Step (To Reach “Prod Confidence”)

Deliver a “scenario suite” that simulates all critical user journeys:
- Bot conversation flows (test1/test2 + scheduling)
- Admin UI flows (offer/reschedule/decline/intro-day)
- Failure modes (Redis down, Telegram unauthorized, DB slow/unavailable)

This should become a single command gate for release (CI + local):  
`make test && (cd frontend/app && npm run lint && npm run typecheck && npm run test && npm run test:e2e)`
