# RecruitSmart Maxpilot

RecruitSmart Maxpilot is a production CRM/ATS repository for recruiting pipeline operations, candidate scheduling, recruiter coordination, messaging, verification providers, and related admin workflows.

The product is currently a FastAPI backend plus a React 18 SPA:
- backend admin server: [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- public/candidate API host: [backend/apps/admin_api/main.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/main.py)
- Telegram bot runtime: [backend/apps/bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/app.py)
- frontend SPA: [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- compiled frontend bundle served by backend: [frontend/dist](/Users/mikhail/Projects/recruitsmart_admin/frontend/dist)

## Product Scope

RecruitSmart Maxpilot supports:
- candidate verification and candidate-access flows;
- recruiter/admin CRM workflows;
- Telegram messaging and bounded MAX pilot surfaces;
- HH integration and sync jobs;
- interview slots, slot reservations, manual scheduling, and manual availability fallback.

The application-code hardening baseline is `rc/hardening-candidate-scale-20260425-19` on branch `release/hardening-artifact-freeze`. The docs-inclusive handoff candidate is `rc/hardening-candidate-scale-20260425-20` after this documentation package is committed and CI passes. Production remains NO-GO until staging smoke, production preflight, secret rotation, nginx/log verification, DB checks, and production smoke are completed.

## Architecture

- Backend: FastAPI, SQLAlchemy, Alembic-style migration runner, Redis-backed optional services, Telegram bot workers, HH integrations.
- Frontend: React 18, TanStack Router, React Query, TypeScript, Vite, pure CSS with custom properties and route-driven layouts.
- Storage/services: PostgreSQL is the primary app database; Redis is used for notifications and optional broker/cache scenarios.
- Testing: Python `pytest`, frontend `vitest`, Playwright smoke/e2e.

Current supported runtime matrix lives in [docs/architecture/supported_channels.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/supported_channels.md).
The short version:
- supported: Admin SPA, Telegram bot/webapp, HH integration, n8n HH sync callbacks
- supported bounded pilot: MAX launch/webhook/mini-app shell over shared candidate-access backend contracts
- unsupported historical implementations: legacy candidate portal implementation, historical full MAX runtime
- target state, not current runtime: full standalone browser candidate rollout and SMS / voice fallback integration

## Repository Layout

```text
backend/            FastAPI apps, domain services, migrations, integrations
frontend/app/       React SPA source, tests, Vite config
frontend/dist/      Built SPA bundle served by backend
docs/               Product, architecture, migration, release, and runbooks
codex/              Older Codex-era notes, tasks, reports, and context files
scripts/            Dev helpers, migration runner, smoke/perf utilities
tests/              Python tests
artifacts/          Generated reports, screenshots, logs
```

## Quick Start

### Backend + SPA served by FastAPI

```bash
python3 -m venv .venv
. .venv/bin/activate
make install
npm --prefix frontend/app install
cp .env.local.example .env.local
docker compose up -d postgres redis_notifications
make dev-migrate
make dev-admin
```

Open:
- backend-served SPA: [http://localhost:8000/app](http://localhost:8000/app)
- login: [http://localhost:8000/app/login](http://localhost:8000/app/login)
- health: [http://localhost:8000/health](http://localhost:8000/health)

### Frontend-only dev server

In another terminal:

```bash
npm --prefix frontend/app run dev
```

The Vite server runs on `http://localhost:5173` and proxies `/api`, `/slots`, `/auth`, and `/candidates` to the backend on port `8000`.

### Optional bot worker

```bash
make dev-bot
```

## Common Commands

### Backend

```bash
make dev-migrate
make dev-admin
make dev-bot
make test
make test-cov
make openapi-export
make openapi-check
```

### Frontend

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

OpenAPI truth is generated from the live FastAPI apps:

```bash
make openapi-export
make openapi-check
```

`make openapi-export` refreshes:
- [frontend/app/openapi.json](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/openapi.json)
- [backend/apps/admin_api/openapi.json](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/openapi.json)
- [frontend/app/src/api/schema.ts](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/schema.ts)

`make openapi-check` is a required repo-local gate whenever a change touches routes, schemas, API contracts, or OpenAPI tooling. It must fail the change if tracked schemas drift from the live `admin_ui` or `admin_api` app factories.

## Canonical Docs

Start here in this order:

1. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
2. [docs/README.md](/Users/mikhail/Projects/recruitsmart_admin/docs/README.md)
3. [docs/PROJECT_OVERVIEW.md](/Users/mikhail/Projects/recruitsmart_admin/docs/PROJECT_OVERVIEW.md)
4. [docs/ARCHITECTURE.md](/Users/mikhail/Projects/recruitsmart_admin/docs/ARCHITECTURE.md)
5. [docs/API_SPEC.md](/Users/mikhail/Projects/recruitsmart_admin/docs/API_SPEC.md)
6. [docs/DATA_MODEL.md](/Users/mikhail/Projects/recruitsmart_admin/docs/DATA_MODEL.md)
7. [docs/DEPLOYMENT.md](/Users/mikhail/Projects/recruitsmart_admin/docs/DEPLOYMENT.md)
8. [docs/OPERATIONS_RUNBOOK.md](/Users/mikhail/Projects/recruitsmart_admin/docs/OPERATIONS_RUNBOOK.md)
9. [docs/STAGING_TARGET_REQUIREMENTS.md](/Users/mikhail/Projects/recruitsmart_admin/docs/STAGING_TARGET_REQUIREMENTS.md)
10. [docs/STAGING_HANDOFF.md](/Users/mikhail/Projects/recruitsmart_admin/docs/STAGING_HANDOFF.md)

Root policy changed on 2026-03-08:
- closed task-specific markdown packages were removed from repo root
- temporary task/spec/checklist docs must now be deleted after completion
- if you need old closed-task material, use git history or historical docs in [docs/archive](/Users/mikhail/Projects/recruitsmart_admin/docs/archive)

## Current Active Scope

- Mounted SPA scope: `31` routes defined in [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- Dormant route files excluded from first redesign wave: `vacancies.tsx`, `reminder-ops.tsx`
- Current redesign execution priority: foundation -> shell -> recruiter-first flows -> mobile hardening -> admin cleanup
- Do not restart the redesign planning process unless the route map or product scope materially changes

## Environment Files

- [.env.example](/Users/mikhail/Projects/recruitsmart_admin/.env.example): baseline environment template
- [.env.local.example](/Users/mikhail/Projects/recruitsmart_admin/.env.local.example): recommended local development starting point
- [.env.development.example](/Users/mikhail/Projects/recruitsmart_admin/.env.development.example): minimal override example

Local dev helpers load `.env.local` if present, otherwise they fall back to `.env.local.example`.

## Contributor / Agent Rules

- Inspect before editing. Do not assume older docs are current.
- Work in small verified batches.
- Keep business logic changes out of repo-setup tasks.
- Temporary markdown files for prompts/TODO/specs must be deleted after the task is closed.
- After changing code or canonical workflow docs, update the relevant canonical docs in [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md), [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md), and [docs](/Users/mikhail/Projects/recruitsmart_admin/docs).

Project-specific working rules live in [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md).
