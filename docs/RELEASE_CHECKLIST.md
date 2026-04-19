# Release Checklist

## Security

- [ ] Confirm no real secrets/tokens are stored in committed `.env*` example files.
- [ ] Run secret scan gate: `./scripts/secret_scan.sh`.
- [ ] Run Python dependency resolver check: `pip install --dry-run -r requirements.txt -r requirements-dev.txt`.
- [ ] Run Python vuln audit: `pip-audit -r requirements.txt -r requirements-dev.txt` (must have no high/critical).
- [ ] Run frontend vuln audit: `cd frontend/app && npm audit --audit-level=high` (must have no high/critical).
- [ ] Rotate `BOT_TOKEN` if it was ever committed or shared.
- [ ] Rotate `BOT_CALLBACK_SECRET` if it was ever committed or shared.
- [ ] Rotate `SESSION_SECRET` if it was ever committed or shared.
- [ ] Verify production secrets are loaded from a secure secret manager.

## Migrations and Startup

- [ ] Set `MIGRATIONS_DATABASE_URL` (dedicated DDL role) for production migration job.
- [ ] Run migrations before deployment: `python scripts/run_migrations.py`.
- [ ] Confirm migration DDL preflight passed (no schema privilege errors).
- [ ] Validate `/health` and `/ready` responses after rollout.
- [ ] Confirm app worker fan-out: `WEB_CONCURRENCY>=2` for `admin_ui` and `admin_api`.
- [ ] Confirm operator bot and notification diagnostics are green after authenticated admin login.
- [ ] Verify `/health/bot` is not publicly accessible and returns expected runtime state for an authenticated admin.
- [ ] Verify `/health/notifications` is not publicly accessible and returns expected delivery state for an authenticated admin.

## Quality Gates

- [ ] Run formal Sprint 1/2 gate: `python3 scripts/formal_gate_sprint12.py` (or `make gate-sprint12`).
- [ ] Backend tests pass (`make test` / CI matrix).
- [ ] Frontend checks pass (`npm run lint`, `npm run typecheck`, `npm run test`, `npm run test:e2e`).
- [ ] Perf gate passed: `./scripts/perf_gate.sh` (error rate <1%, p95 <250ms, p99 <1000ms at 600 rps).
- [ ] Quality snapshot updated: `./scripts/quality_snapshot.sh --full`.
- [ ] Smoke test critical candidate/city flows in staging.

## AI / Simulator Ops

- [ ] Verify AI Coach endpoints are operational (see `docs/AI_COACH_RUNBOOK.md`).
- [ ] Verify local simulator flows are green before rollout prep (see `docs/SIMULATOR_RUNBOOK.md`).

## Incident Runbook: `telegram_unauthorized`

- [ ] Confirm incident under authenticated admin session: `/health/bot` shows `runtime.switch_reason=telegram_unauthorized` and `/health/notifications` shows `notifications.fatal_error_code=telegram_unauthorized`.
- [ ] Rotate `BOT_TOKEN` in secret manager and revoke old token in @BotFather.
- [ ] Restart `bot` and `admin_ui` services after secret update.
- [ ] Recheck authenticated operator diagnostics: `/health/bot` must not be in runtime error; `/health/notifications` must return HTTP `200` with `delivery_state=ok`.
- [ ] Record incident timestamp and rotation result in release notes/on-call log.
