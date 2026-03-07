# System Effectiveness Review

## Executive Summary

RecruitSmart is already beyond the "prototype" stage. The system has a workable
service split, a modern SPA frontend, a broad automated test surface, and
explicit operational hooks for health, metrics, and migrations. Assembled as a
whole, it is effective for shipping features quickly.

The main constraint is no longer missing functionality. The constraint is
structural drag:

- oversized modules in both backend and frontend;
- tooling and documentation drift between old and new frontend stacks;
- a custom migration path that works, but is harder to scale safely;
- growing operational complexity around messenger, bot, and multi-channel flows.

Current maturity assessment: **7/10 for delivery**, **5/10 for maintainability at
next scale step**.

## Repository-Grounded Snapshot

### Runtime structure

- Backend surfaces:
  - `backend/apps/admin_ui`
  - `backend/apps/admin_api`
  - `backend/apps/bot`
  - `backend/apps/max_bot`
- Shared layers:
  - `backend/core`
  - `backend/domain`
  - `backend/migrations`
- Frontend SPA:
  - `frontend/app/src/app/routes`
  - `frontend/app/src/theme`

### Technology stack

- Backend:
  - FastAPI
  - SQLAlchemy async
  - PostgreSQL
  - Redis
  - Aiogram
  - APScheduler
  - Prometheus client
- Frontend:
  - React 18
  - Vite
  - TypeScript
  - TanStack Router
  - TanStack Query
  - React Hook Form
  - Zod
  - Zustand
  - FullCalendar
  - Playwright
  - Vitest
- Infra:
  - Docker Compose
  - GitHub Actions

### Current scale signals

- Code/test/theme footprint sampled from repository: `148,916` lines across
  Python, TS/TSX, and CSS.
- Backend test files: `325`
- Frontend e2e/unit test files: `13`
- GitHub Actions workflows: `5`

### Largest maintainability hotspots

- `backend/apps/bot/services.py` — `7540` lines
- `backend/apps/admin_ui/routers/api.py` — `4490` lines
- `backend/apps/admin_ui/services/candidates.py` — `3632` lines
- `frontend/app/src/theme/global.css` — `8717` lines
- `frontend/app/src/app/routes/app/candidate-detail.tsx` — `2824` lines
- `backend/apps/admin_ui/services/dashboard.py` — `2251` lines
- `backend/apps/admin_ui/services/slots.py` — `1921` lines
- `backend/domain/repositories.py` — `1582` lines

## What Works Well

### 1. Service boundaries are understandable

The split between admin UI, admin API, bot, and Max bot is conceptually sound.
The repository still has monolith pressure inside files, but the top-level
runtime boundaries are already reasonable.

### 2. Stack choices are pragmatic

FastAPI + SQLAlchemy + PostgreSQL + Redis is a solid operational core for this
kind of internal product. On the frontend, React + Vite + TanStack Router/Query
is a strong choice for a data-heavy admin system.

### 3. Testing maturity is above average

The system has real backend coverage, frontend unit coverage, and Playwright
coverage. CI runs across multiple Python versions and includes Playwright, which
is a good sign of engineering seriousness.

### 4. Production guardrails exist

`backend/core/settings.py` has meaningful production validation, and
`docker-compose.yml` defines healthchecks and separate service roles. This lowers
the probability of "it boots locally but fails in prod" class incidents.

### 5. Observability is present, not absent

Health endpoints, Prometheus metrics, request logging toggles, and explicit bot
health checks already exist. Many systems at this stage are missing this.

## Structural Issues Reducing Efficiency

### P0. Monolithic file concentration

The architecture looks modular at directory level, but too much operational and
business behavior accumulates in a small number of huge files. This slows:

- onboarding;
- safe refactoring;
- targeted testing;
- incident debugging;
- ownership clarity.

This is most acute in:

- `backend/apps/bot/services.py`
- `backend/apps/admin_ui/routers/api.py`
- `backend/apps/admin_ui/services/candidates.py`
- `frontend/app/src/app/routes/app/candidate-detail.tsx`
- `frontend/app/src/theme/global.css`

### P0. Tooling drift between old and current frontend approaches

The active frontend is Vite-based, but the repo still carries old Tailwind/Jinja
strategy traces in docs and CI artifacts. Examples:

- `frontend/app/vite.config.ts` is the real SPA build entry.
- `.github/workflows/ci.yaml` still contains wording like "Build Tailwind
  bundle".
- `docs/TECH_STRATEGY.md` references `tokens.ts` + `global.css` as source of
  truth, while the current theme system is now split across multiple CSS layers.

This does not break runtime directly, but it increases confusion and slows
correct changes.

### P0. Migration strategy is operationally riskier than it should be

`backend/migrations/runner.py` is a custom migration runner using an
Alembic-style version table, but not full Alembic flow. It is simple and
workable, but it becomes fragile when:

- multiple authors add migrations concurrently;
- non-linear migration histories appear;
- rollback and diff tooling are needed;
- schema reviews become more formal.

### P1. Environment parity is incomplete

The repo is explicit that PostgreSQL is mandatory for dev/test, but Playwright
e2e still boots against SQLite by default in `frontend/app/playwright.config.ts`.
That is useful for speed, but it also means some query behavior and locking
semantics are not exercised in the same shape as production.

### P1. Frontend maintainability is behind frontend capability

The stack is modern, but route files are still too large and the API layer is
only partially typed in practice. `frontend/app/src/api/schema.ts` is generated,
but `frontend/app/src/api/client.ts` still exposes a mostly generic `apiFetch<T>`
pattern rather than a typed endpoint SDK with narrower per-domain adapters.

### P1. Config surface is getting overcrowded

`backend/core/settings.py` is almost a subsystem by itself. That is often a
signal that configuration domains should be split into smaller concerns:

- app runtime;
- DB/cache;
- AI;
- notifications;
- external integrations;
- auth/security.

## Technology Assessment

### Keep

- FastAPI
- SQLAlchemy async
- PostgreSQL
- Redis
- React + Vite
- TanStack Router + Query
- Playwright + Vitest
- Docker Compose for local/staging-like workflows

These are not the problem. Replacing them would create churn without solving the
current bottlenecks.

### Strengthen

- typed API layer on frontend;
- domain/service modularity on backend;
- metrics/logging around messenger and delivery flows;
- CI ergonomics and workflow cleanup;
- migration discipline and schema review workflow.

### Reconsider

- custom migration runner as the long-term default;
- continued growth of file-level monoliths;
- duplicate/stale CI and strategy documents;
- overreliance on giant page components for data-heavy screens.

## Recommended Improvement Plan

### Wave 1. Architecture Hygiene

Goal: reduce structural drag without changing behavior.

1. Split oversized backend modules by capability.
2. Split oversized frontend route files into page shell + feature sections.
3. Make `frontend/app/src/theme/tokens.css` and the current layered CSS model the
   documented source of truth.
4. Remove stale frontend-build references from CI/docs.

Expected impact:

- faster safe edits;
- lower regression probability;
- clearer ownership boundaries.

### Wave 2. Typed Contracts and Boundary Cleanup

Goal: make data flow easier to reason about.

1. Generate and use a typed frontend API SDK from OpenAPI instead of relying
   mainly on generic `apiFetch<T>`.
2. Introduce per-domain API modules:
   - candidates
   - slots
   - messenger
   - recruiters
   - system
3. Split `backend/core/settings.py` into focused config modules while keeping the
   same env contract.

Expected impact:

- fewer request/response shape bugs;
- better editor support;
- safer refactors.

### Wave 3. Migration and Data Safety Track

Goal: reduce schema-change risk.

1. Decide one direction explicitly:
   - formalize the custom runner with stronger branch-chain checks, dry-run
     output, and rollback conventions; or
   - migrate to standard Alembic env/scripts fully.
2. Add migration review gates in CI:
   - forward apply
   - idempotency check
   - downgrade contract for selected revisions
3. Document migration authoring rules in one place.

Expected impact:

- safer concurrent development;
- clearer release discipline;
- fewer deployment surprises.

### Wave 4. Operational Observability

Goal: make failures easy to diagnose in production.

1. Standardize structured logs with correlation IDs across admin, bot, and Max
   integrations.
2. Add delivery lifecycle metrics for outbound messaging:
   - queued
   - dispatched
   - provider accepted
   - provider failed
   - retried
   - terminal failure
3. Expose dashboards for:
   - message latency
   - retry rate
   - dead-letter/failure counts
   - queue backlog
4. Add explicit admin-facing diagnostics for candidate communications.

Expected impact:

- faster incident response;
- better recruiter trust in messaging flows;
- measurable reliability improvements.

### Wave 5. Frontend Productivity and Performance

Goal: keep delivery speed high as the SPA grows.

1. Introduce route-level lazy loading for the heaviest pages.
2. Break `candidate-detail`, `dashboard`, `slots`, and `calendar` into smaller
   feature modules.
3. Add bundle budgets and CI warnings for oversized chunks.
4. Expand visual regression and mobile smoke coverage for core workflows.

Expected impact:

- smaller review scope per change;
- better SPA startup and route performance;
- less UI regression risk.

## 90-Day Priority Order

### Priority A

- split `bot/services.py`
- split `admin_ui/routers/api.py`
- split `admin_ui/services/candidates.py`
- clean stale CI/docs/frontend strategy references

### Priority B

- typed frontend API adapters
- config modularization
- route decomposition for the largest frontend pages

### Priority C

- migration strategy normalization
- delivery observability and communication audit dashboards
- performance budgets and visual regression gates

## Suggested Ownership Model

- Platform/architecture:
  - migrations
  - settings
  - CI
  - deployment and observability
- Product/backend:
  - domain services
  - messaging orchestration
  - candidate workflow slices
- Frontend:
  - route decomposition
  - typed API adoption
  - design system maintenance
  - visual regression coverage

## Final Assessment

The system is effective enough to keep delivering product work. It is not in a
rewrite zone. The right move is targeted structural refinement, not technology
replacement.

The strongest path forward is:

1. preserve the current stack;
2. reduce file-level monoliths;
3. normalize tooling and migration discipline;
4. improve observability around integrations and messaging;
5. tighten typed contracts between backend and frontend.
