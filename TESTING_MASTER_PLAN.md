# RecruitSmart Testing Master Plan

## 1. System Overview

### Repository-grounded architecture snapshot
- Backend runtime: FastAPI applications in `backend/apps/admin_ui`, `backend/apps/admin_api`, `backend/apps/bot`, `backend/apps/max_bot`.
- Frontend runtime: React 18 + Vite + TanStack Router + TanStack Query in `frontend/app`.
- Database: PostgreSQL in dev/prod, SQLite used in a subset of tests and Playwright startup.
- ORM: SQLAlchemy async.
- Cache and broker: Redis for cache/notifications in production profiles, memory/null fallbacks in dev and tests.
- Scheduling/background processing: APScheduler, long-running async loops in `backend/apps/admin_ui/background_tasks.py`, bot reminder and notification workers in `backend/apps/bot/services.py` and `backend/apps/bot/reminders.py`.
- Integrations actually present in code: Telegram bot, Telegram WebApp, Max messenger, hh.ru webhook/n8n path, OpenAI-backed AI services, Sentry, Prometheus metrics.
- Access model: session-based web auth plus bearer tokens for admin UI, Telegram initData auth for candidate webapp, principals `admin` and `recruiter` only.
- Deployment profile: `docker-compose.yml` runs `postgres`, `redis_notifications`, `redis_cache`, `migrate`, `admin_ui`, `admin_api`, `bot`, `max_bot`.

### Current delivery surface
- `backend/apps/admin_ui/routers/api.py` contains 115 REST routes behind a single `/api` router.
- `backend/apps/admin_api/webapp/routers.py` exposes 6 candidate-facing Telegram WebApp routes.
- Frontend has 36 route files in `frontend/app/src/app/routes/app`.
- Test inventory currently in repo:
  - Python tests: 150 files.
  - Frontend unit tests: 10 files.
  - Playwright E2E specs: 12 files.

### Current quality baseline
- Strongest coverage areas: slot reservation logic, duplicate prevention, notification retry/outbox, timezone handling, auth hardening, scoping helpers, status transitions, webapp auth.
- Weakest coverage areas: full RBAC route matrix across 115 API routes, recruiter-vs-admin UI flows, real external integration delivery confirmation, performance automation in CI, migration downgrade rehearsal, observability assertions, frontend role-based regressions.

## 2. Testing Goals
- Prevent data loss, duplicate bookings, broken status transitions, and unauthorized access.
- Turn release quality from best-effort to gated and measurable.
- Make critical recruiting flows deterministic under concurrency and partial external failures.
- Detect regressions in routing, permissions, migrations, queues, and candidate communications before production.
- Raise confidence in scaling behavior for API, background workers, and dashboard/data-heavy screens.

## 3. Scope

### In scope
- Backend domain logic, API contracts, RBAC, candidate status transitions, slots, intro-day workflows, notifications, background jobs, migrations, deployment config, CI gates, integrations, frontend critical routes, responsive-critical UI behavior, observability, and release safety.

### Out of scope
- Product redesign.
- Business rule changes.
- Vendor SLA verification for Telegram/Max/hh/OpenAI beyond system-side handling.
- Full pentest.
- Browser compatibility matrix beyond Chromium-based automation unless release requires it.

## 4. Quality Assessment

| Dimension | Assessment | Notes |
|---|---|---|
| Overall quality | Acceptable | Strong domain test density, but systemic reliability gaps remain. |
| Production readiness | Conditional go | Core flows are viable, but migration/runtime/reliability gaps need release gates. |
| Scaling readiness | Moderate risk | Locking/idempotency exists, but background/runtime wiring and chat limits are not fully multi-worker-safe. |
| Testability | Moderate | Good unit/integration seams in domain layer, weaker seams at startup/runtime integration boundaries. |
| Observability | Moderate-weak | Health and Prometheus exist, structured lifecycle telemetry is inconsistent. |
| Release safety | Moderate | CI is materially improved, but migration rehearsal, perf gating, and RBAC smoke are incomplete. |

## 5. Module Map

| Module | What it does | Business criticality | Current confidence | Primary risk |
|---|---|---:|---|---|
| Auth/session/access | Web login, bearer/session auth, principal resolution, brute-force protection | Critical | Moderate | Auth mode parity and RBAC drift across routes |
| Candidate directory | Candidate list/detail/create/update/assignment | Critical | Moderate | Monolithic service, scope leakage, status-side effects |
| Candidate workflow/status | Funnel transitions and workflow actions | Critical | Moderate-strong | Invalid transitions, idempotency edge cases, side-effect coupling |
| Slots/interviews | Slot creation, booking, approval, reject, reschedule | Critical | Strong at domain, moderate at API | Conflict mapping, double-booking race, timezone edge cases |
| Intro day | Scheduling, slot isolation, confirmation/decline | Critical | Moderate | Cross-purpose conflicts, duplicate scheduling, handoff side effects |
| Notifications/outbox | Delivery queue, retries, templates, DLQ behavior | Critical | Strong | Partial failure observability and lifecycle transparency |
| Recruiter chat/messenger | Manual recruiter-to-candidate messaging | High | Weak-moderate | In-memory rate limit, ambiguous delivery state, partial retries |
| Staff chat/calendar | Internal communication and calendar tasking | High | Weak-moderate | Sparse RBAC/attachment coverage |
| Telegram WebApp | Candidate slot booking/reschedule/cancel | Critical | Moderate | SQL-path divergence from domain logic, concurrency bugs |
| Dictionaries/admin settings | Recruiters, cities, templates, questions | High | Moderate | Scope and optimistic locking drift |
| Dashboards/analytics | KPI, incoming queue, recruiter metrics | High | Moderate | Performance degradation and scope/caching errors |
| AI/Copilot | Interview scripts, AI assists | Medium-high | Moderate | Feature-flag variance, provider errors, weak acceptance coverage |
| Integrations | Telegram, Max, hh.ru, OpenAI | Critical | Moderate | External unavailability, retries, insufficient delivery diagnostics |
| Migrations/config/bootstrap | Schema, startup, environment validation | Critical | Weak-moderate | Custom migration runner, startup side effects, SQLite divergence |
| Frontend SPA | Role-based views, filters, lists, candidate detail, messenger | High | Moderate for smoke, weak for deep regression | Business-flow UI regressions not covered deeply |

## 5A. Module Audit Details

| Module | What it does | Why it matters | Critical scenarios | Likely failures | Mandatory tests | Automate first | Visible bottlenecks | Highest-value improvement |
|---|---|---|---|---|---|---|---|---|
| Auth/session/access | Authenticates admins and recruiters and resolves principals | Every protected action depends on it | login, logout, bearer use, brute-force, prod-safe flags | bearer/session drift, bypass flags, 401/403/404 mismatches | auth mode parity, brute-force, CSRF, proxy trust | bearer+session parity and protected-route smoke | mixed auth modes and env variance | consolidate auth contract tests and prod-safe config assertions |
| Candidates | Stores candidate directory, ownership, detail payloads, updates | Central object for all recruiting operations | create, detail, assign recruiter, delete, filter, HH profile enrichment | scope leak, broken filters, side-effect regressions | CRUD + scope + audit + detail payload | list/detail/create/update/delete API matrix | 3632-line service with coupled side effects | split service and add route matrix coverage |
| Workflow/status | Controls funnel state and permitted actions | Wrong state corrupts pipeline reporting and operations | transition, reject, hire, intro-day progression, idempotent repeats | invalid transition, stale UI actions, double side effects | transition matrix, idempotency, retreat no-op | workflow API + service transition matrix | domain/UI/action drift | enforce one status-orchestration seam |
| Slots/interviews | Creates and allocates interview slots | Core supply side of recruiting pipeline | reserve, approve, reject, reschedule, duplicate prevention, timezone handling | double booking, wrong 500 mapping, timezone drift | concurrency, conflict, owner scope, timezone, idempotency | API/domain parity and concurrent reservation tests | high-write concurrency | unify all booking entry points on shared domain path |
| Intro day | Schedules onboarding/intro-day visits | Directly affects candidate conversion and sales handoff | schedule, cancel active interview, confirm/decline, route to Max | duplicate intro day, stale interview assignment, silent Max failure | cross-purpose, cleanup, handoff enabled/disabled/failure | API integration for schedule + handoff | orchestration spans multiple modules | explicit intro-day orchestration and telemetry |
| Notifications/outbox | Sends candidate notifications with retries | Candidate communications and reminders depend on it | enqueue, claim, send, retry, DLQ, stale lock recovery | retry storms, duplicate send, hidden backlog | retry, dedup, broker outage, stale lock, metrics | Redis/Postgres worker integration suite | runtime coupling and missing release gate | make queue/retry gate part of nightly and release |
| Recruiter chat/messenger | Lets recruiter send direct messages to candidate | High business impact and user trust sensitive | send, duplicate request id, retry, rate limit, status display | in-memory limiter, fake sent state, duplicate sends | send/retry/duplicate/multi-worker rate-limit | recruiter chat API/service tests | no shared limiter and limited lifecycle states | Redis limiter + delivery lifecycle model |
| WebApp booking | Lets candidate book/reschedule/cancel from Telegram | Business-critical self-service path | me, list slots, booking, reschedule, cancel | SQL/domain divergence, ownership bypass, race bugs | auth, ownership, concurrency, conflict mapping | Postgres integration suite | raw SQL flow separate from domain path | route through shared booking semantics |
| Dashboard/analytics | Gives operational visibility to recruiters and admins | Wrong numbers distort staffing decisions | summary, incoming, funnel, KPI history, recruiter performance | scope leak, stale cache, slow queries | scoped aggregates, cache invalidation, perf tests | dashboard API + perf smoke | expensive joins/aggregates | perf gate + query-plan review |
| Dictionaries/admin settings | Maintains recruiters, cities, templates, questions | Config errors propagate widely | city CRUD, recruiter CRUD, template preview/history, question reorder | scope drift, optimistic lock misses, bad template content | CRUD negative, scope, optimistic locking | admin CRUD and template validation tests | broad surface, moderate coverage | add CRUD route matrix and concurrency checks |
| Integrations | Connects Telegram, Max, hh, OpenAI | External failures affect core outcomes | webhook handling, adapter bootstrap, fallback, provider outage | silent drop, retry mismatch, contract drift | contract, retry, outage, malformed payload | sandbox/fake-adapter acceptance suite | partial mocks only | unified operational contract and sandbox smoke |
| Migrations/config/bootstrap | Evolves DB and boots runtime services | Release safety depends on it | migrate clean DB, migrate seeded DB, start with app-role, degraded boot | custom runner drift, dialect mismatch, startup side effects | upgrade, downgrade smoke, health after boot | migration contract + startup matrix | custom runner and boot side effects | standardize migration flow and startup matrix tests |
| Frontend critical UI | Delivers recruiter daily workflow | Broken UI blocks operations even if API is healthy | login, candidates, slots, candidate detail, messenger, mobile | role-flow regressions, overflow, stale state UX | smoke, role flow, responsive, a11y | Playwright critical role paths | 2793-line candidate detail and limited deep E2E | expand role-critical E2E and component seams |

## 6. Known Strengths From Existing Tests
- Slot reservation race/idempotency is already explicitly tested in `tests/test_slot_reservations.py`, `tests/test_double_booking.py`, `tests/test_outbox_deduplication.py`, and `tests/test_intro_day_slot_isolation.py`.
- Status transition rules are guarded by `tests/test_status_service_transitions.py`, `tests/test_workflow_api.py`, `tests/test_candidate_actions.py`, and `tests/test_slot_status_transitions.py`.
- Auth hardening and rate limiting are covered in `tests/test_security_auth_hardening.py`, `tests/test_rate_limiting.py`, and `tests/test_admin_surface_hardening.py`.
- Notification retry semantics and DLQ behavior are covered in `tests/test_notification_retry.py`, `tests/test_notification_logs.py`, `tests/test_notification_log_idempotency.py`, and `tests/test_reminder_service.py`.
- WebApp auth and route existence are covered in `tests/test_webapp_auth.py` and `tests/test_webapp_smoke.py`.
- Frontend baseline health exists through Playwright smoke/mobile smoke plus route-focused specs.

## 7. Primary Gaps
- No systematic authorization matrix across all admin API routes and all relevant role/path combinations.
- No production-like end-to-end delivery confirmation tests for Telegram and Max.
- No automated performance gate in CI despite existing loadtest tooling in `docs/performance` and `scripts/loadtest_profiles`.
- Migration contract is partially checked, but downgrade rehearsal and SQLite/Postgres behavior parity are not reliable.
- Chat delivery UX is not backed by a reliable lifecycle model; recruiter sees at best sent/failed, not provider acceptance or delivery progression.
- Startup/bootstrap is side-effect-heavy (`backend/apps/admin_ui/app.py`, `backend/apps/admin_ui/state.py`) and only partially exercised in tests.
- Frontend E2E covers smoke and a few focused paths, but not role-sensitive business flows end to end.

## 8. Test Strategy By Layer

### Unit/domain
- Keep domain rules deterministic and exhaustive around slot state, candidate status, duplicate prevention, timezone normalization, reminder schedule calculations, and template rendering.
- Mandatory for every new rule: transition validation, idempotency, boundary dates, null identifiers, and negative variants.

### Integration/service
- Focus on service seams with DB + mocked adapters.
- High-priority targets: candidate scheduling, intro-day scheduling, recruiter chat send/retry, bot dispatch, Max handoff, staff chat, dashboard cache invalidation.

### API/contract
- Every critical mutation needs happy path, business conflict, unauthorized, forbidden/out-of-scope, invalid payload, idempotent retry, and degraded dependency tests.
- Candidate-facing WebApp routes require separate auth/ownership/concurrency suites.

### UI/E2E
- Keep smoke on every PR.
- Expand to role-based flows: recruiter vs admin candidate access, slot approval/rejection, messenger send/retry, candidate detail actions, filter persistence, mobile-safe flow.

### Performance
- Use existing loadtest profiles to define baseline, mixed, spike, soak, queue throughput, and reporting stress.
- Perf gate must become a release input, not only a manual document.

### Security and access
- Cover auth modes, RBAC, 404 scoping policy, CSRF, brute force, forwarded IP trust, metrics exposure, attachment access, and PII leakage in logs/exports.

### Resilience
- Simulate Redis unavailable, bot unavailable, Max unavailable, OpenAI timeout, DB timeout, broken migration role, duplicate event delivery, and stale outbox lock recovery.

### Observability
- Assert `/healthz`, `/ready`, `/health`, `/health/bot`, `/health/notifications`, `/metrics/notifications`, Prometheus counters, and audit logging on critical actions.

### Migration safety
- Validate upgrade from empty DB, upgrade from pre-populated DB, at least selected downgrade/upgrade smoke, and runtime startup after migration with app-role only.

## 9. Release Criteria

### Required on every PR
- `pytest` targeted fast suites for auth, scoping, slots, notifications, migrations contract.
- `npm --prefix frontend/app run typecheck`
- `npm --prefix frontend/app run lint`
- `npm --prefix frontend/app run test`
- Playwright smoke desktop + mobile.
- Secret scan and dependency audit where lockfiles change.

### Required nightly
- Full pytest.
- Full Playwright suite.
- Postgres + Redis integration pack for notifications/outbox.
- Migration rehearsal against fresh Postgres.
- RBAC smoke matrix.

### Required before release
- Migration contract + selected downgrade smoke.
- Performance mixed-profile gate on prod-like runtime.
- Telegram/Max integration sandbox smoke.
- Candidate critical flow smoke.
- Post-deploy health and metrics probe.

## 10. Production Readiness Criteria
- No P0 open in auth, booking, status, or delivery areas.
- Migration job succeeds with dedicated migration role; app runtime starts with app role only.
- All critical user flows pass in staging against Postgres and Redis.
- Performance gate meets agreed thresholds on mixed load.
- Health endpoints show green dependencies; notification worker and bot integration states are visible.
- Rollback path is documented and rehearsed for last schema change.

## 11. Priority Roadmap

### Wave 1: next 7 days
- Add RBAC smoke for all critical `/api` mutations and detail routes.
- Add recruiter chat delivery tests around duplicate request IDs, retry, external failure, and status exposure.
- Add WebApp booking concurrency tests that align SQL path with domain reservation semantics.
- Add migration downgrade smoke and SQLite guardrail test.

### Wave 2: next 2 weeks
- Introduce nightly Postgres+Redis integration suite for notification/outbox worker.
- Add Max and hh integration contract tests with deterministic fake adapters.
- Add performance smoke to scheduled pipeline using existing `scripts/loadtest_profiles`.
- Expand Playwright to role-based critical flows.

### Wave 3: next 3-4 weeks
- Add resilience scenarios for Redis outage, DB timeout, worker restart, duplicate broker delivery, and external API timeouts.
- Add observability assertions for structured logs/metrics on candidate communication flows.
- Add visual and accessibility checks for the most business-critical screens.

### Wave 4: next 4-6 weeks
- Convert release gate into policy: PR fast checks, nightly deep checks, pre-release perf + migration + sandbox integrations, post-deploy smoke.
- Use seeded staging datasets and replayable fixtures for deterministic QA signoff.

## 12. Recommended Verdict
- Overall quality: **acceptable**.
- Release verdict today: **conditional go**.
- Condition set: close P0/P1 items from `RISK_REGISTER.md`, especially migration safety, recruiter communication reliability, RBAC route coverage, and WebApp/domain booking parity.
