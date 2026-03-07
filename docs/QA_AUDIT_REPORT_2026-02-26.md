# QA Audit Report — RecruitSmart CRM

Date: 2026-02-26  
QA Lead: Codex (virtual team mode)  
Environment: local (`main`, commit `c478383`)  
App URL: `http://127.0.0.1:8000`

## 1) Executive Summary
- Core CRM flows are generally stable: smoke/regression and e2e suites passed.
- Critical defects found in auth/booking:
  - Recruiter OAuth bearer tokens are issued but unusable (`401` on protected API).
  - Duplicate candidate booking path returns `500` instead of business error (`400/409`).
- Performance bottleneck is concentrated on `GET /api/candidates` under spike (tail latency degrades sharply).
- AI interview-script scope is blocked in this environment (`501 ai_disabled`), so end-to-end AI acceptance cannot be fully validated locally.

Release risk now: **High** (P0/P1 issues present).

## 2) Virtual Team and Work Split
- QA Lead: plan, orchestration, unified report, risk decision.
- Manual QA: exploratory API/UI checks (auth, roles, slot flow, statuses, errors).
- QA Automation Engineer: unit/integration/e2e execution and regression evidence.
- Performance/Load Engineer: steady/spike/soak load via curl harness with p50/p95/p99/RPS/error.
- Security/Privacy QA: auth headers, role boundaries, brute-force/rate-limit/CSRF behavior.
- Data/DB QA: migrations, status transitions, idempotency, duplicate booking path.
- Product Analyst QA: status semantics, incoming flow markers, dashboard metrics consistency.

## 3) Repo Facts Collected (from code/config)
- Backend: FastAPI (`backend/apps/admin_ui`, `backend/apps/admin_api`).
- Frontend: React + Vite (`frontend/app`).
- DB: PostgreSQL for dev/prod; SQLite used in e2e/test profiles.
- Cache/queue: Redis present; in tests often memory/null mode.
- Integrations: Telegram bot, OpenAI provider, KB/RAG modules, HH resume support in AI module.
- Roles: `admin`, `recruiter`.
- Health/metrics: `/health`, `/ready`, `/metrics`, `/health/bot`.
- Candidate status lifecycle: `backend/domain/candidates/status.py`.

## 4) Test Plan and Execution

### Smoke suite (critical path)
- Auth token issue/consume, profile access, dashboard summary, candidates list, slots list.
- Result: passed with admin token; recruiter token defect found.

### Regression suite
- Candidate/slot/status/scoping/security/AI-related tests.
- Result: passed in targeted packs.

### Exploratory charters
- Role/scope boundary checks.
- Slot booking/outcome edge cases.
- AI endpoint availability and fallback behavior.
- Result: 2 critical defects + 1 blocker confirmed.

### API tests (negative + positive)
- 401 without token, 403 for admin-only action by recruiter session.
- Slot book happy-path and duplicate path.
- Result: duplicate path currently 500.

### Load tests
- Steady (10 min total), spike (2 min), soak (10 min time-boxed), plus write endpoints.
- Artifacts: `.tmp/qa_load_20260226_153730/summary.csv`, raw files in same folder.

### Security checklist (OWASP-lite)
- Security headers present.
- Brute-force/rate-limit tests passed.
- Role checks partially pass (session-based), bearer recruiter broken.
- CSRF relaxed in local/test-like mode (not prod-grade enforcement).

## 5) Automated Test Evidence

### Backend pytest packs
- `23 passed` (`auth/security/schedule/domain/timezone` pack).
- `71 passed` (`scoping/slots/candidates/status` pack).
- `58 passed` (`double-booking/idempotency/slot transitions` pack).
- `30 passed` (`AI/KB/interview-script` pack).
- `15 passed` (`dashboard/services` pack).
- `37 passed` (`rate-limit/perf-metrics/surface/intro-day/webapp` pack).

Subtotal backend: **234 passed**.

### Frontend unit
- `11 passed` (`vitest`).

### Frontend e2e
- `37 passed` (`playwright`, smoke + regression + a11y).

Grand total executed: **282 tests passed**.

### Test data set used (minimum 10 candidate archetypes)

| ID | Archetype | Key attributes | Covered by |
|---|---|---|---|
| TD-01 | New lead | no tests, no slot | candidates API/e2e smoke |
| TD-02 | Test1 completed | eligible for scheduling | `test_admin_candidate_schedule_slot.py` |
| TD-03 | Waiting slot | incoming queue candidate | `test_dashboard_and_slots.py` |
| TD-04 | Requested other time | incoming substatus `requested_other_time` | `test_dashboard_and_slots.py` |
| TD-05 | Slot pending | slot offered, waiting confirmation | `test_admin_candidate_schedule_slot.py` |
| TD-06 | Interview scheduled | booked slot + interview stage | `test_status_service_transitions.py` |
| TD-07 | Interview confirmed | confirmed-by-candidate path | `test_double_booking.py`, `test_slot_status_transitions.py` |
| TD-08 | Interview declined | decline transition with reason | `test_candidate_rejection_reason.py` |
| TD-09 | Intro-day scheduled/confirmed | intro-day lifecycle | `test_intro_day_status.py`, `test_intro_day_recruiter_scope.py` |
| TD-10 | Terminal statuses | hired/not hired/declined finals | `test_candidate_actions.py`, `test_status_service_transitions.py` |

## 6) Scenario Matrix

| Feature | Scenario | Expected | Result | Evidence |
|---|---|---|---|---|
| Auth | Admin token login | 200 + bearer token | PASS | manual curl |
| Auth | API without token | 401 | PASS | `/api/profile` |
| Auth | Recruiter token login+use | 200 on `/api/profile` | **FAIL** | `profile_status=401` |
| Auth | Recruiter session login+use | 200 on `/api/profile` | PASS | session cookie check |
| Roles | Recruiter -> admin endpoint | 403 | PASS | `/api/candidates/{id}/assign-recruiter` |
| Scope | Recruiter forced own slots scope | ignores foreign recruiter_id | PASS | `/api/slots?recruiter_id=7` returns own |
| Candidates | List + filters API | 200, valid payload | PASS | `/api/candidates` |
| Slots | Bulk create | slots created | PASS | `/api/slots/bulk_create` |
| Slots | Book free slot (new candidate) | 200 | PASS | slot `136` + tg `837685732` |
| Slots | Book non-free slot | 400 `slot_not_free` | PASS | repeated book |
| Slots | Book free slot with candidate already booked elsewhere | business 4xx/409 | **FAIL** (`500`) | slot `137` + tg `999201` |
| Slots | Outcome update idempotent | 200 repeat safe | PASS | `/api/slots/134/outcome` |
| Dashboard | Summary API | 200 stable | PASS | `/api/dashboard/summary` |
| Dashboard | Incoming API | 200 stable | PASS | `/api/dashboard/incoming` |
| AI | Interview script endpoint | valid AI response | **BLOCKED** (`501 ai_disabled`) | `/api/ai/candidates/*/interview-script` |
| Security | Response security headers | present | PASS | HEAD/GET checks |
| Security | Brute-force/rate-limit tests | pass | PASS | `tests/test_security_auth_hardening.py`, `test_rate_limiting.py` |
| Data | Status transitions consistency | valid lifecycle | PASS | `test_status_service_transitions.py` |
| Data | Duplicate slot constraints | handled safely | PASS (domain level), **FAIL** (API book path) | domain tests + manual repro |
| UI e2e | Core screens and regressions | no console 4xx/5xx, render ok | PASS | Playwright 37/37 |

## 7) Bug Backlog (Top + Full)

### Top critical findings
1. QA-001 — Recruiter bearer token unusable.
2. QA-002 — Duplicate candidate booking returns 500.
3. QA-003 — AI interview-script scope blocked by `ai_disabled` in local env.

### Detailed bug reports (standardized)

#### QA-001
- Title: Recruiter receives OAuth token but cannot access protected API (`401`).
- Severity: Critical
- Priority: P0
- Environment: local, commit `c478383`
- Preconditions: recruiter auth account exists (id `6`), valid password.
- Steps:
  1. `POST /auth/token` with recruiter credentials.
  2. Call `GET /api/profile` with `Authorization: Bearer <token>`.
- Expected: `200`, recruiter principal in payload.
- Actual: `401 {"detail":"Authentication required"}`.
- Evidence: manual API run, response captured in session.
- Suspected root cause: `backend/apps/admin_ui/security.py` resolves bearer JWT only for admin username; no DB `AuthAccount` resolution for non-admin token subject.
- Suggested fix: add JWT subject -> `AuthAccount` lookup and principal mapping for recruiter tokens, then apply active-check.
- Acceptance criteria:
  - Recruiter bearer token gets `200` on `/api/profile`.
  - Role-scoped endpoints work with bearer (same as session behavior).
  - Add integration tests for recruiter bearer auth.

#### QA-002
- Title: `POST /api/slots/{slot_id}/book` returns `500` for duplicate-candidate booking conflict.
- Severity: Critical
- Priority: P0
- Environment: local, commit `c478383`
- Preconditions: candidate already booked with same recruiter on another active slot.
- Steps:
  1. Create new free slot (`/api/slots/bulk_create`).
  2. Book new slot with candidate already booked elsewhere.
- Expected: business error (`400/409`) with clear code (duplicate candidate booking).
- Actual: `500 Internal Server Error`.
- Evidence:
  - manual repro on slot `137` with tg `999201`.
  - load run `write_slot_book`: `2540/2540` errors (`500`).
  - `/metrics`: `http_requests_total{route="/api/slots/{slot_id}/book",status="500"}=2540`.
- Suspected root cause: unhandled DB/domain conflict in API handler (`api_slot_book`) instead of using domain reservation conflict path.
- Suggested fix: route booking through domain service (`reserve_slot`) and map duplicate/occupied conflicts to deterministic 4xx.
- Acceptance criteria:
  - duplicate candidate booking returns 4xx with stable error code.
  - no 5xx from expected booking conflicts.
  - add integration test for duplicate candidate booking via API.

#### QA-003 (Blocker)
- Title: AI interview script endpoints unavailable in local (`ai_disabled`).
- Severity: Blocker
- Priority: P1
- Environment: local, commit `c478383`
- Preconditions: none.
- Steps: call `GET /api/ai/candidates/{id}/interview-script`.
- Expected: generation/cached response per contract.
- Actual: `501 {"ok":false,"error":"ai_disabled"}`.
- Evidence: manual API calls for existing/non-existing candidates both return 501.
- Suspected root cause: AI feature flag/config disabled in current env.
- Suggested fix: provide stage-like env with AI enabled and non-prod key/model to validate acceptance end-to-end.
- Acceptance criteria:
  - endpoint works with real provider or deterministic fake in staging profile.
  - schema-validation path and retries can be observed in integration tests.

#### QA-004
- Title: SQLite autoupgrade warning in e2e startup (`ALTER COLUMN ...` unsupported).
- Severity: Minor
- Priority: P2
- Environment: Playwright e2e test server.
- Preconditions: `npm run test:e2e`.
- Steps: run e2e startup.
- Expected: clean startup without migration SQL errors.
- Actual: warning logged: `Automatic schema upgrade skipped ... near "ALTER": syntax error`.
- Evidence: e2e logs in test run output.
- Suspected root cause: generic autoupgrade path runs PostgreSQL-style SQL on SQLite.
- Suggested fix: guard migration/autoupgrade by dialect or disable auto-upgrade in SQLite e2e mode.
- Acceptance criteria:
  - no SQL syntax warning in e2e boot logs.
  - e2e DB setup remains deterministic.

## 8) Load Test Report

Artifacts:
- `.tmp/qa_load_20260226_153730/summary.csv`
- `.tmp/qa_load_20260226_153730/*.raw`
- `.tmp/qa_metrics_after.txt`

### Protocol used
- Steady: 4 segments x 150s (total 10 min):
  - `/api/dashboard/summary`, `/api/candidates`, `/api/slots`, `/api/dashboard/incoming`
- Spike: 2 segments x 60s (total 2 min):
  - `/api/dashboard/summary`, `/api/candidates`
- Write stress: 2 segments x 60s:
  - `/api/slots/{id}/book`, `/api/slots/{id}/outcome`
- Soak: 600s (time-boxed in this cycle):
  - `/api/dashboard/summary`

### Measured results (from summary.csv)
| Phase | RPS | p95 | p99 | Error rate |
|---|---:|---:|---:|---:|
| steady_dashboard_summary | 400.50 | 0.014s | 0.020s | 0.00% |
| steady_candidates_list | 124.50 | 0.208s | 0.220s | 0.00% |
| steady_slots_list | 224.10 | 0.044s | 0.159s | 0.00% |
| steady_incoming | 323.00 | 0.015s | 0.019s | 0.00% |
| spike_dashboard_summary | 339.00 | 0.096s | 0.105s | 0.00% |
| spike_candidates_list | 107.00 | 0.597s | 0.621s | 0.00% |
| write_slot_book | 42.33 | 0.433s | 0.525s | 100.00% (500) |
| write_slot_outcome | 78.00 | 0.235s | 0.328s | 0.00% |
| soak_dashboard_summary | 195.16 | 0.006s | 0.009s | 0.00% |

### Knee of curve (observed)
- Primary knee observed on `GET /api/candidates` near spike profile:
  - steady: p95 ~208ms at ~124 RPS
  - spike: p95 ~597ms at ~107 RPS
- `dashboard_summary` remained stable under same pattern.

### DB/Queue observations
- DB pool acquire histograms available in `/metrics`; for `/api/candidates` tail reaches high buckets under load.
- Host-level DB CPU/IO and queue worker internals are not available in this local sandbox run (blocker for full infra-level attribution).

## 9) Risks for Release (P0/P1)
- P0: Recruiter bearer auth broken (mobile/API clients relying on token flow cannot operate).
- P0: Booking conflict path returns 500 (production incident risk, retries amplify noise).
- P1: AI script acceptance blocked in current environment (feature readiness unknown end-to-end).

## 10) Fix Backlog for 1–2 Sprints

### Sprint 1 (stability + auth)
1. P0 / S: Fix recruiter bearer principal resolution in `security.py`.
2. P0 / M: Refactor `api_slot_book` to use domain reservation conflict handling, map conflicts to 4xx.
3. P0 / S: Add integration tests for bearer recruiter auth and duplicate booking conflict.
4. P1 / S: Add explicit error contract for booking conflicts (`duplicate_candidate`, `slot_not_free`, etc.).

### Sprint 2 (perf + observability)
1. P1 / M: Optimize `GET /api/candidates` query path for spike tail latency (projection/index/N+1 audit).
2. P1 / M: Add perf budget tests for candidates endpoint (p95 guardrails in controlled profile).
3. P2 / S: SQLite e2e startup migration guard (dialect-aware autoupgrade).
4. P2 / M: Stage profile with AI enabled for interview-script acceptance and synthetic dataset replay.

## 11) Regression Checklist (post-fix)
- Auth:
  - recruiter bearer token -> `/api/profile` = 200.
  - admin/recruiter scope parity (session vs bearer).
- Slots:
  - duplicate booking returns 4xx (no 5xx).
  - idempotent outcome updates keep 200 and no duplicate side effects.
- API contracts:
  - stable error codes for booking/status mutations.
- Performance:
  - rerun steady/spike/soak profile and compare p95/p99 deltas.
- AI:
  - `interview-script` generate/refresh/feedback flow in AI-enabled stage.
- Regression packs:
  - backend targeted suites + frontend unit + e2e smoke/regression.

## 12) Blockers / Gaps (honest constraints)
- AI interview-script end-to-end validation blocked by `ai_disabled` (env-level).
- Host-level DB CPU/IO metrics unavailable in this local sandbox run.
- Direct DB introspection from sandboxed Python session is restricted; verification done through API/metrics/tests.
