# RecruitSmart Admin

RecruitSmart Admin is a production CRM/ATS repository for recruiting pipeline operations, candidate scheduling, recruiter coordination, messaging, and related admin workflows.

The product is currently a FastAPI backend plus a React 18 SPA:
- backend admin server: [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- frontend SPA: [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- compiled frontend bundle served by backend: [frontend/dist](/Users/mikhail/Projects/recruitsmart_admin/frontend/dist)

## Architecture

- Backend: FastAPI, SQLAlchemy, Alembic-style migration runner, Redis-backed optional services, Telegram bot workers, HH/Max integrations.
- Frontend: React 18, TanStack Router, React Query, TypeScript, Vite, pure CSS with custom properties and route-driven layouts.
- Storage/services: PostgreSQL is the primary app database; Redis is used for notifications and optional broker/cache scenarios.
- Testing: Python `pytest`, frontend `vitest`, Playwright smoke/e2e.

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

Detailed command guidance, caveats, and validation scope live in [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md).

## Canonical Docs

Start here in this order:

1. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
2. [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
3. [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
4. [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
5. [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)

Canonical redesign planning package:
- [DESIGN_REDESIGN_PRD.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_REDESIGN_PRD.md)
- [DESIGN_AUDIT_REPORT.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_AUDIT_REPORT.md)
- [UI_PRINCIPLES_AND_LAYOUT_PATTERNS.md](/Users/mikhail/Projects/recruitsmart_admin/UI_PRINCIPLES_AND_LAYOUT_PATTERNS.md)
- [RESPONSIVE_AND_MOBILE_AUDIT.md](/Users/mikhail/Projects/recruitsmart_admin/RESPONSIVE_AND_MOBILE_AUDIT.md)
- [SCREEN_ARCHITECTURE_MAP.md](/Users/mikhail/Projects/recruitsmart_admin/SCREEN_ARCHITECTURE_MAP.md)
- [DESIGN_SYSTEM_PLAN.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_SYSTEM_PLAN.md)
- [MOTION_AND_INTERACTION_GUIDELINES.md](/Users/mikhail/Projects/recruitsmart_admin/MOTION_AND_INTERACTION_GUIDELINES.md)
- [IMPLEMENTATION_ROADMAP_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/IMPLEMENTATION_ROADMAP_FOR_CODEX.md)
- [ACCEPTANCE_CRITERIA.md](/Users/mikhail/Projects/recruitsmart_admin/ACCEPTANCE_CRITERIA.md)
- [DESIGN_QA_CHECKLIST.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_QA_CHECKLIST.md)
- [EXECUTIVE_SUMMARY.md](/Users/mikhail/Projects/recruitsmart_admin/EXECUTIVE_SUMMARY.md)

Canonical Codex execution handoff package:
- [DESIGN_DECISIONS_LOG.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_DECISIONS_LOG.md)
- [CODEX_EXECUTION_PLAN.md](/Users/mikhail/Projects/recruitsmart_admin/CODEX_EXECUTION_PLAN.md)
- [EPIC_BREAKDOWN_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/EPIC_BREAKDOWN_FOR_CODEX.md)
- [TASK_GRAPH_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/TASK_GRAPH_FOR_CODEX.md)
- [COMPONENT_IMPLEMENTATION_SPECS.md](/Users/mikhail/Projects/recruitsmart_admin/COMPONENT_IMPLEMENTATION_SPECS.md)
- [SCREEN_IMPLEMENTATION_SPECS.md](/Users/mikhail/Projects/recruitsmart_admin/SCREEN_IMPLEMENTATION_SPECS.md)
- [CODEX_FIRST_WAVE_RECOMMENDATION.md](/Users/mikhail/Projects/recruitsmart_admin/CODEX_FIRST_WAVE_RECOMMENDATION.md)
- [ROLLOUT_AND_REGRESSION_STRATEGY.md](/Users/mikhail/Projects/recruitsmart_admin/ROLLOUT_AND_REGRESSION_STRATEGY.md)

If these files disagree with older material under [codex](/Users/mikhail/Projects/recruitsmart_admin/codex), [docs/project](/Users/mikhail/Projects/recruitsmart_admin/docs/project), or [docs/archive](/Users/mikhail/Projects/recruitsmart_admin/docs/archive), prefer the root canonical files above.

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
- Do not delete planning artifacts; use indexes and precedence notes instead.
- After changing code or canonical workflow docs, update the relevant root context files.

Project-specific working rules live in [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md).
