# Release Checklist

## Security

- [ ] Confirm no real secrets/tokens are stored in committed `.env*` example files.
- [ ] Rotate `BOT_TOKEN` if it was ever committed or shared.
- [ ] Rotate `BOT_CALLBACK_SECRET` if it was ever committed or shared.
- [ ] Rotate `SESSION_SECRET` if it was ever committed or shared.
- [ ] Verify production secrets are loaded from a secure secret manager.

## Migrations and Startup

- [ ] Run migrations before deployment: `python scripts/run_migrations.py`.
- [ ] Validate `/health` and `/ready` responses after rollout.
- [ ] Confirm bot and notification broker health endpoints are green.

## Quality Gates

- [ ] Backend tests pass (`make test` / CI matrix).
- [ ] Frontend checks pass (`npm run lint`, `npm run typecheck`, `npm run test`, `npm run test:e2e`).
- [ ] Smoke test critical candidate/city flows in staging.
