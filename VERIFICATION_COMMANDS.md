# Verification Commands

## Purpose

This file is the copy-paste source of truth for install, run, and verification commands in this repository.

## Toolchain

- Python: project supports `3.11` to `3.13`; CI runs frontend gates on Python `3.12`
- Node.js: CI uses Node `20`
- Database for main local dev/test workflows: PostgreSQL
- Redis: optional for some dev flows, required for Redis-backed notifications scenarios

## Initial Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
make install
npm --prefix frontend/app install
cp .env.local.example .env.local
docker compose up -d postgres redis_notifications
```

## Local Run Commands

### Backend-served SPA

```bash
make dev-migrate
make dev-admin
```

Validates:
- env loading from `.env.local` or `.env.local.example`
- migrations run before startup
- FastAPI app serves the SPA on port `8000`

### Bot

```bash
make dev-bot
```

Validates:
- local bot startup with env file loading
- bot token/config presence for polling mode

### MAX bot webhook service

```bash
make dev-max-bot
```

Validates:
- local MAX webhook app startup
- env loading for `MAX_BOT_TOKEN` / `MAX_WEBHOOK_URL`
- webhook endpoint availability on port `8010` by default

### Live-local MAX bootstrap

```bash
make dev-max-live
```

Validates:
- `cloudflared` quick tunnels for admin UI and MAX webhook
- process-local public `CRM_PUBLIC_URL` / `CANDIDATE_PORTAL_PUBLIC_URL`
- process-local public `MAX_WEBHOOK_URL`
- auto-resolution of `MAX_BOT_LINK_BASE` from provider when env value is absent
- local admin UI on `8000` and MAX webhook service on `8010`
- optional `DEV_MAX_LIVE_ADMIN_PORT` / `DEV_MAX_LIVE_MAX_PORT` overrides when the default ports are already occupied

### Frontend-only dev server

```bash
npm --prefix frontend/app run dev
```

Validates:
- Vite dev server startup on `5173`
- proxying to backend endpoints on `8000`

## Backend Verification

### Main backend test suite

```bash
make test
```

Validates:
- Python test suite
- backend service and API behavior
- local PostgreSQL-backed test workflow

Caveat:
- expects PostgreSQL test DB on `localhost:5432/rs_test` as configured in `Makefile`

### Coverage run

```bash
make test-cov
```

Validates:
- same as `make test`
- backend coverage output

## Frontend Verification

### Lint

```bash
npm --prefix frontend/app run lint
```

Validates:
- ESLint on `src/**/*.ts(x)`

### Typecheck

```bash
npm --prefix frontend/app run typecheck
```

Validates:
- TypeScript compile-time checks without emitting files

### Unit / component tests

```bash
npm --prefix frontend/app run test
```

Validates:
- Vitest suites for SPA logic and components

### Production build

```bash
npm --prefix frontend/app run build
```

Validates:
- Vite production build to `frontend/dist`

### Build + bundle budgets

```bash
npm --prefix frontend/app run build:verify
```

Validates:
- production build
- bundle budget check via `scripts/check-bundle-budgets.mjs`

This is the default final gate for frontend work.

## E2E / Smoke Verification

### Frontend smoke suite

```bash
npm --prefix frontend/app run test:e2e:smoke
```

Validates:
- Playwright smoke tests for desktop/mobile critical flows
- self-hosted test server startup from Playwright config

Caveats:
- the Playwright config runs migrations and starts `uvicorn` automatically
- default E2E DB is temporary SQLite, not PostgreSQL

### Full Playwright suite

```bash
npm --prefix frontend/app run test:e2e
```

Validates:
- full Playwright suite after a fresh build

Use when:
- changing shell, routing, overlays, mobile nav, auth flows, or critical UI workflows

## Health / Manual Checks

### Backend health

```bash
curl -f http://localhost:8000/health
```

### Open the app

- [http://localhost:8000/app](http://localhost:8000/app)
- [http://localhost:8000/app/login](http://localhost:8000/app/login)
- [http://localhost:5173](http://localhost:5173) when using Vite dev server

## Recommended Verification By Change Type

### Docs-only repo workflow changes

Run:

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
```

Why:
- confirms the repository entrypoints and standard gates still pass in the current worktree

### Frontend code changes

Run:

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
```

Add when relevant:

```bash
npm --prefix frontend/app run test:e2e:smoke
```

### Backend code changes

Run:

```bash
make test
```

Add targeted commands when changing migrations, broker flows, or integration modules.

## Known Caveats

- `make install` installs Python dependencies only; it does not install frontend npm packages
- `.env.local` is the recommended local override file
- `.env.local.example` is the practical local starting point; `.env.example` is the baseline environment template
- some older docs still mention obsolete commands; prefer this file and the root README
- a dirty worktree is common in this repository; always inspect `git status --short` first
