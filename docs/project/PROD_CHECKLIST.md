# Production Checklist (Draft)

Status: **Draft placeholder created to unblock work**. Expand/verify before real production deploys.

## Pre-Deploy
- [ ] Environment variables configured (no secrets in repo)
- [ ] Database reachable and backed up
- [ ] Redis reachable
- [ ] Migrations reviewed and ready (run in prod only with explicit approval)
- [ ] Bot credentials verified (no duplicate running bot instances)

## Build & Assets
- [ ] SPA build generated (`frontend/app` → `frontend/dist/`)
- [ ] Static assets served correctly under `/app/*`
- [ ] CSP headers validated for SPA assets

## Smoke & Health
- [ ] `/api/health` (or equivalent) returns OK
- [ ] Login works for admin and recruiter
- [ ] Dashboard loads without errors

## Post-Deploy
- [ ] Error logs checked (backend + bot)
- [ ] Background jobs running
- [ ] Monitoring/alerts enabled

