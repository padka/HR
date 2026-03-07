# Automation Roadmap

## Goal
Build a layered automation program that catches business-critical regressions early, reserves heavier suites for nightly and pre-release, and makes release quality measurable.

## Phase 0. Immediate baseline (Days 1-7)

### Add to every PR
- Backend fast pack:
  - auth/session/bearer parity
  - scoping guards
  - slot reservation/conflict/idempotency
  - notification retry basics
  - migration contract
- Frontend fast pack:
  - typecheck
  - lint
  - vitest
  - Playwright `smoke.spec.ts` and `mobile-smoke.spec.ts`
- Security smoke:
  - brute-force lock
  - metrics exposure
  - protected route denial

### New tests to write first
1. Recruiter bearer token to `/api/profile` and top protected routes.
2. WebApp booking/reschedule/cancel Postgres integration suite.
3. Recruiter chat send/duplicate/retry tests.
4. Admin-vs-recruiter access matrix for candidate and slot critical mutations.
5. Migration downgrade smoke for latest revision chain.

## Phase 1. Nightly reliability pack (Week 2)
- Full pytest suite.
- Full Playwright suite.
- Postgres + Redis notification/outbox integration run.
- RBAC matrix over top 30 critical routes.
- Performance smoke using existing mixed profile.
- Sandbox adapter tests for Telegram/Max with deterministic fakes.

## Phase 2. Pre-release gate (Weeks 3-4)
- Migration rehearsal on fresh and pre-seeded Postgres.
- Performance gate on prod-like runtime profile.
- Critical user flow smoke:
  - recruiter login and scoped access
  - candidate create/schedule
  - slot approve/reject/reschedule
  - intro-day scheduling
  - recruiter message send/retry
- Observability gate:
  - health endpoints green
  - notification metrics exposed
  - audit log entries created for critical actions

## Phase 3. Weekly deep checks (Month 2)
- Soak test for queue and dashboard workloads.
- Failure injection for Redis outage, DB timeout, Telegram retry-after, Max unavailable.
- Full security matrix for attachments/staff chat/thread membership.
- Visual and responsive regression baseline for top five screens.

## CI Cadence

### On each PR
- Required:
  - `pytest` fast critical pack
  - frontend typecheck/lint/unit
  - Playwright smoke + mobile smoke
  - migration contract if migrations/config touched
  - dependency audit when lockfiles change
- Keep runtime under 15 minutes.

### Nightly
- Full backend suite.
- Full frontend E2E.
- Redis/Postgres integration suites.
- Performance smoke.
- RBAC matrix.
- Report to artifact bundle with failures grouped by module.

### Pre-release
- Migration rehearsal.
- Performance mixed + spike.
- Sandbox integration smoke.
- Critical flow suite.
- Manual signoff only for scenarios that cannot be meaningfully automated.

## What stays manual for now
- Real Telegram/Max end-user delivery confirmation until sandbox observability is complete.
- AI answer quality review beyond schema/timeout/caching correctness.
- Exploratory UX around dense candidate lists and bulk operations.
- Browser-specific manual checks outside Chromium.

## Owners and Deliverables
- QA/SDET: route matrix, integration suites, perf harness, pre-release gate.
- Backend: seams for deterministic adapters, migration hardening, structured delivery status.
- Frontend: Playwright expansion, UI observability surfaces, role-based flows.
- DevOps/Platform: nightly env with Postgres + Redis, metrics retention, release smoke after deploy.

## Success Metrics
- PR gate catches all P0 regressions in auth, booking, status, and delivery paths.
- Nightly run produces stable pass/fail signal with low flake rate.
- Pre-release gate becomes mandatory for mainline release candidate.
- Mean time to detect release-blocking regression drops to same day.
