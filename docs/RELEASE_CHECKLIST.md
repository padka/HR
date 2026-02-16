# Release Checklist

## Security

- [ ] Confirm no real secrets/tokens are stored in committed `.env*` example files.
- [ ] Run secret scan gate: `./scripts/secret_scan.sh`.
- [ ] Rotate `BOT_TOKEN` if it was ever committed or shared.
- [ ] Rotate `BOT_CALLBACK_SECRET` if it was ever committed or shared.
- [ ] Rotate `SESSION_SECRET` if it was ever committed or shared.
- [ ] Verify production secrets are loaded from a secure secret manager.

## Migrations and Startup

- [ ] Run migrations before deployment: `python scripts/run_migrations.py`.
- [ ] Validate `/health` and `/ready` responses after rollout.
- [ ] Confirm bot and notification broker health endpoints are green.
- [ ] Verify `/health/bot` returns expected runtime state (`status`, `runtime.switch_source`, `runtime.switch_reason`, `runtime.disabled_by`).
- [ ] Verify `/health/notifications` has no `notifications.fatal_error_code` and `notifications.delivery_state=ok`.

## Quality Gates

- [ ] Backend tests pass (`make test` / CI matrix).
- [ ] Frontend checks pass (`npm run lint`, `npm run typecheck`, `npm run test`, `npm run test:e2e`).
- [ ] Quality snapshot updated: `./scripts/quality_snapshot.sh --full`.
- [ ] Smoke test critical candidate/city flows in staging.

## AI / Simulator Ops

- [ ] Verify AI Coach endpoints are operational (see `docs/AI_COACH_RUNBOOK.md`).
- [ ] Verify local simulator flows are green before rollout prep (see `docs/SIMULATOR_RUNBOOK.md`).

## Incident Runbook: `telegram_unauthorized`

- [ ] Confirm incident: `/health/bot` shows `runtime.switch_reason=telegram_unauthorized` and `/health/notifications` shows `notifications.fatal_error_code=telegram_unauthorized`.
- [ ] Rotate `BOT_TOKEN` in secret manager and revoke old token in @BotFather.
- [ ] Restart `bot` and `admin_ui` services after secret update.
- [ ] Recheck health: `/health/bot` must not be in runtime error; `/health/notifications` must return HTTP `200` with `delivery_state=ok`.
- [ ] Record incident timestamp and rotation result in release notes/on-call log.
