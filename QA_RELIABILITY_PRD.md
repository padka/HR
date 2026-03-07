# PRD: QA, Reliability and Release Safety Program for RecruitSmart

## 1. Document Status
- Status: Draft for implementation
- Owner: Engineering / QA / Platform
- Source of truth inputs:
  - `TESTING_MASTER_PLAN.md`
  - `TEST_COVERAGE_MATRIX.md`
  - `CRITICAL_USER_FLOWS.md`
  - `RISK_REGISTER.md`
  - `PERFORMANCE_TEST_PLAN.md`
  - `SECURITY_AND_ACCESS_TEST_PLAN.md`
  - `AUTOMATION_ROADMAP.md`

## 2. Executive Summary
RecruitSmart already has a working technical base and a meaningful automated test footprint, especially in slot reservation, status transitions, notifications, rate limiting, and auth hardening. The limiting factor is not the total absence of tests. The limiting factor is uneven protection of the system across the most business-critical and most failure-prone areas.

This PRD defines a productized QA and reliability program whose goal is to make releases predictable, measurable, and safe without rewriting the stack or changing business logic. The program will turn the current repo into a release-governed system with explicit PR gates, nightly deep checks, pre-release validation, migration safety, RBAC confidence, communication reliability coverage, and measurable performance thresholds.

## 3. Background and Problem Statement
The repository shows a hybrid maturity profile:
- domain-critical backend areas are covered reasonably well;
- frontend smoke and health checks exist;
- health and metrics endpoints already exist;
- migration, runtime, RBAC, and integration paths remain structurally risky.

The highest-risk gaps are concentrated in a few zones:
- custom migration runner and incomplete downgrade rehearsal;
- WebApp booking flow that uses its own SQL path instead of fully shared domain orchestration;
- recruiter chat and outbound messaging that do not expose a full delivery lifecycle;
- large monolithic router/service files that make regression review difficult;
- incomplete route-level RBAC validation across a very large API surface;
- performance tooling that exists but is not enforced in CI or release flow.

As a result, the current state is operationally usable but not fully release-safe. The system is in `conditional go`, not `go`.

## 4. Problem to Solve
RecruitSmart needs a QA/reliability layer that answers these questions with evidence instead of assumptions:
- Can we safely ship to production after every mainline merge?
- Will a release break candidate booking, recruiter workflow, or outbound communication?
- Will unauthorized access or scope leakage be caught before production?
- Will a migration fail before the app is deployed rather than during startup?
- Will performance regressions be visible before recruiters feel them?
- Can incidents involving Telegram/Max delivery be traced to an exact lifecycle stage?

## 5. Product Goal
Build a repeatable, repository-grounded quality system that:
- blocks unsafe releases early;
- catches the highest-impact regressions on every PR;
- exercises integration-heavy and concurrency-heavy paths nightly;
- validates migrations, performance, RBAC, and delivery reliability before release;
- gives engineering and management a simple go / no-go decision based on explicit criteria.

## 6. Success Criteria

### Primary success metrics
- 100% of P0 release-critical flows covered by automated PR or nightly checks.
- 0 open P0 issues in auth, booking, status, messaging, or migration safety at release cut.
- 0 expected business conflicts surfacing as `500` in critical booking and workflow paths.
- Pre-release gate includes migration, performance, RBAC, and critical-flow validation for every release candidate.
- Candidate communication flows expose a lifecycle that distinguishes queueing, dispatch, provider acceptance, delivery, retry, and terminal failure.

### Secondary success metrics
- Mean time to detect critical regression: same PR or same day, not after deployment.
- Nightly suite failure signal is actionable and grouped by module.
- Performance regressions greater than agreed threshold are caught before release.
- Release checklist becomes evidence-based rather than manual intuition.

## 7. Non-Goals
This PRD does not include:
- redesign of business workflows;
- rewriting the backend or frontend stack;
- product rule changes for roles, statuses, or funnel semantics;
- full AppSec pentest;
- replacing all legacy code in one phase.

## 8. Users and Stakeholders

### Primary users
- QA engineers and SDETs
- backend engineers
- frontend engineers
- platform/DevOps engineers
- release managers

### Business stakeholders
- product owner
- recruiting operations leadership
- support / incident response

### Why they care
- engineering needs deterministic regression feedback;
- release managers need a hard release gate;
- recruiting ops needs communication and scheduling flows to stop failing silently;
- management needs a confident production-readiness signal.

## 9. Repository-Grounded Context

### Backend
- FastAPI apps in `backend/apps/admin_ui`, `backend/apps/admin_api`, `backend/apps/bot`, `backend/apps/max_bot`.
- SQLAlchemy async with PostgreSQL in real deployment profiles.
- Redis for cache and notifications in deployment stack.
- APScheduler and async background loops for reminders and maintenance tasks.
- Custom migration runner in `backend/migrations/runner.py` with entrypoint `scripts/run_migrations.py`.

### Frontend
- React 18 + Vite + TanStack Router + TanStack Query in `frontend/app`.
- 36 app route files.
- 12 Playwright E2E specs and 10 frontend unit test files.

### Scale and complexity markers
- `backend/apps/admin_ui/routers/api.py`: 115 routes, 4490 lines.
- `backend/apps/admin_ui/services/candidates.py`: 3632 lines.
- `backend/apps/bot/services.py`: 7540 lines.
- `frontend/app/src/app/routes/app/candidate-detail.tsx`: 2793 lines.

These numbers matter because regression probability rises sharply in large files with mixed responsibilities and side effects.

## 10. Current Maturity Assessment

| Dimension | Current state | Required target |
|---|---|---|
| Core domain tests | Acceptable to strong | Strong and release-gated |
| UI smoke | Moderate | Moderate-strong with role-based flows |
| RBAC confidence | Moderate-weak | Strong for critical routes |
| Migration safety | Weak-moderate | Strong |
| Communication reliability | Weak-moderate | Strong and observable |
| Perf readiness | Moderate-weak | Strong enough for pre-release gate |
| Release safety | Moderate | Strong and policy-enforced |

## 11. Product Scope

### Included
1. PR gate definition and automation.
2. Nightly deep validation suites.
3. Pre-release gate definition and automation.
4. Critical user flow coverage.
5. RBAC and access testing matrix.
6. Migration and schema safety validation.
7. Communication reliability and observability coverage.
8. Performance gate definition and enforcement.
9. Post-deploy smoke expectations.

### Included modules
- auth / session / access
- candidates
- candidate workflow/status
- slots / interview booking / intro day
- notifications / outbox / reminders
- recruiter chat / messenger
- Telegram WebApp
- dashboard / analytics
- dictionaries and admin settings
- integrations: Telegram, Max, hh, AI
- migrations / bootstrap / config
- frontend critical routes

## 12. Key Product Requirements

### FR-1. PR quality gate must block unsafe changes
The system must run a fast but meaningful suite on every PR.

Required checks:
- backend fast pack for auth, scoping, slot conflicts, notifications basics, migration contract;
- frontend typecheck, lint, vitest;
- Playwright smoke and mobile smoke;
- dependency audit when dependencies change;
- secret scan and merge-marker guard.

Acceptance criteria:
- any regression in auth, booking, scoping, or migration contract fails PR;
- runtime under acceptable CI budget;
- failures are attributable to module or gate type.

### FR-2. Nightly validation must exercise deeper reliability paths
The system must run a broader suite nightly against a more production-like environment.

Required checks:
- full pytest;
- full Playwright suite;
- Postgres + Redis integration pack for notification worker/outbox;
- RBAC matrix over critical routes;
- performance smoke using existing loadtest profiles;
- sandbox/fake-adapter checks for Telegram and Max.

Acceptance criteria:
- nightly failures produce actionable artifact bundles;
- flake rate is low enough for trust;
- reliability regressions are detected before release prep.

### FR-3. Pre-release gate must be explicit and mandatory
Every release candidate must pass a heavier gate before production deploy.

Required checks:
- migration rehearsal against fresh and seeded Postgres;
- selected downgrade/upgrade smoke;
- performance mixed profile gate;
- critical business flows;
- sandbox integrations;
- health and observability checks.

Acceptance criteria:
- release cannot be marked ready while pre-release gate is red;
- gate result is visible as `go`, `conditional go`, or `no-go`.

### FR-4. RBAC and scope enforcement must be testable and measurable
The system must prove that admins and recruiters only access allowed objects.

Required coverage:
- candidate detail, delete, assign recruiter, workflow actions;
- slot list/detail/mutations;
- city list/detail/update/reminder policy;
- staff thread messages, attachments, members;
- metrics and diagnostic endpoints.

Acceptance criteria:
- recruiters receive `404` for foreign objects where policy requires no existence leak;
- admin-only routes reject recruiter access;
- coverage exists for both session and bearer auth modes.

### FR-5. Candidate booking semantics must be consistent across entry points
Admin UI booking, bot booking, and WebApp booking must obey the same conflict and state semantics.

Required coverage:
- reserve, approve, reject, reschedule, cancel;
- duplicate candidate conflict;
- cross-purpose conflict between interview and intro day;
- concurrent reservation attempts.

Acceptance criteria:
- no expected business conflict surfaces as `500`;
- no double booking under concurrency;
- WebApp SQL path behavior is parity-tested against domain path.

### FR-6. Communication reliability must be explicit, not inferred
Outbound communication to candidates must expose delivery lifecycle stages.

Required lifecycle stages:
- `queued`
- `dispatched`
- `provider_accepted`
- `delivered` where supported
- `failed`
- `retry_scheduled`
- `terminal_failed`

Required system behaviors:
- duplicate send prevention using idempotency keys or client request ids;
- retry behavior by failure class;
- visibility into current stage, error code, retry count, and last transition time.

Acceptance criteria:
- recruiter can distinguish queued vs failed vs retrying vs terminally failed;
- Telegram and Max flows share one operational status contract;
- status transitions are logged and testable.

### FR-7. Migration safety must be release-grade
Migration execution must be deterministic and compatible with deployment topology.

Required coverage:
- upgrade from empty DB;
- upgrade from existing seeded DB;
- selected downgrade/upgrade smoke;
- app startup with app-role only after migration;
- failure on production startup when `MIGRATIONS_DATABASE_URL` contract is violated.

Acceptance criteria:
- migration contract is enforced in CI;
- no release proceeds without migration rehearsal;
- SQLite-specific shortcuts do not hide PostgreSQL failures.

### FR-8. Performance gate must be measurable and enforceable
Performance must use the existing load tooling as a release mechanism, not only documentation.

Required scenarios:
- mixed read/write baseline;
- spike;
- queue throughput;
- booking concurrency;
- reporting and search-heavy stress.

Acceptance criteria:
- agreed thresholds are versioned and enforced;
- regression beyond threshold blocks release or triggers `conditional go`;
- evidence is stored as artifacts and trendable over time.

### FR-9. Observability must support release and incident decisions
The system must expose enough signals to diagnose failures in candidate operations and integrations.

Required checks:
- `/healthz`, `/ready`, `/health`, `/health/bot`, `/health/notifications`, `/metrics/notifications`;
- Prometheus counters for queue, retries, failures, request latency;
- audit events for critical mutations;
- structured log fields for communication flows and request correlation.

Acceptance criteria:
- degraded states are visible without reading raw stack traces;
- critical actions are traceable to actor, candidate, channel, and operation.

### FR-10. Frontend critical paths must be covered beyond smoke
The UI layer must cover the highest-value operational flows by role.

Required E2E flows:
- recruiter login and scoped access;
- candidate list/detail;
- slot approve/reject/reschedule;
- candidate schedule slot;
- intro-day schedule path;
- messenger send/retry;
- mobile-safe critical shell behavior.

Acceptance criteria:
- business-critical route regressions are caught before release;
- role-based and mobile regressions are part of automation, not manual-only checks.

## 13. Non-Functional Requirements
- Deterministic test data for critical suites.
- Fast PR gate with bounded runtime.
- Nightly suites must run against Postgres and Redis, not only SQLite and memory broker.
- Failure output must be actionable, not only pass/fail.
- Test environments must be reproducible locally and in CI.

## 14. Milestones

### Milestone 1: PR critical gate
Deliverables:
- recruiter bearer/session parity tests;
- slot/candidate/city RBAC smoke;
- recruiter chat send/retry tests;
- WebApp booking regression pack start.

Exit criteria:
- all critical PR checks green on `main` for one week.

### Milestone 2: Nightly reliability suite
Deliverables:
- Postgres + Redis notification worker suite;
- RBAC matrix over critical routes;
- scheduled full Playwright;
- performance smoke.

Exit criteria:
- nightly reports are stable and low-flake.

### Milestone 3: Pre-release gate
Deliverables:
- migration rehearsal;
- selected downgrade smoke;
- mixed performance gate;
- critical user flow suite;
- sandbox integration smoke.

Exit criteria:
- release process references these checks as mandatory.

### Milestone 4: Communication lifecycle observability
Deliverables:
- unified delivery status contract;
- recruiter-visible delivery diagnostics;
- test suite for lifecycle progression.

Exit criteria:
- communication incidents can be diagnosed by lifecycle state, not support guesswork.

## 15. Dependencies
- Postgres and Redis CI environment.
- Stable seeded test data strategy.
- Fake/sandbox adapters for Telegram, Max, and AI.
- Ownership from backend/frontend/platform to keep gates healthy.
- Agreement on release thresholds for latency, queue backlog, and failure rates.

## 16. Risks to Delivery of This Program
- Flaky integration tests will undermine trust if added without deterministic fixtures.
- Performance gates without consistent seed data will produce noisy signals.
- Communication lifecycle work may require coordinated backend and frontend changes.
- Monolithic service/router structure will slow test seam creation if not sliced incrementally.

## 17. Open Decisions
- Whether to move fully to standard Alembic runtime or continue hardening the custom runner.
- Exact numeric performance thresholds by route class for release go/no-go.
- Whether delivery lifecycle is stored in existing messaging tables or separate delivery-log entities.
- Whether sandbox Max/Telegram tests run nightly or pre-release only.

## 18. Acceptance Criteria for This PRD
This PRD is considered implemented when:
1. PR gate includes the defined critical checks.
2. Nightly suite covers deep reliability paths with Postgres and Redis.
3. Pre-release gate is versioned, enforced, and visible.
4. Migration rehearsal is mandatory before release.
5. RBAC coverage exists for critical route families.
6. Communication reliability is lifecycle-based and observable.
7. Performance gate uses the existing profile tooling with hard thresholds.
8. Release decision can be made from evidence instead of manual intuition.

## 19. Recommended Implementation Order
1. PR auth/RBAC/booking gate.
2. WebApp booking parity tests.
3. Recruiter chat reliability suite.
4. Migration downgrade and startup matrix.
5. Nightly Redis/Postgres worker integration suite.
6. Performance smoke in scheduled CI.
7. Pre-release gate formalization.
8. Delivery lifecycle observability rollout.

## 20. Final Product Decision
This program should be approved and executed. The repository already has enough code-level foundation to benefit from a strong QA/reliability product layer. Without it, further feature work increases delivery risk faster than it increases product value.
