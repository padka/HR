# Comprehensive QA Report

## Purpose
Комплексный QA-аудит CRM/ATS платформы в isolated QA contour. Отчет фиксирует реальный test signal, ограничения среды, открытые риски и readiness verdict без оптимистичных допущений.

## Owner
QA / Release Readiness / Reliability Audit

## Status
Complete

## Last Reviewed
2026-04-06

## Environment
- Mode: isolated QA contour only
- Repository: `Attila Recruiting`
- Branch: `codex/recruiter-ui-tranche-p0-p1`
- Commit: `e3938a5`
- Worktree state at audit time: dirty (`69` entries in `git status --short`)
- Allowed infrastructure: local test runners, temporary SQLite test DBs, local Redis
- Explicitly not used: local dev DB mutations, live-local MAX probing, provider-backed end-to-end delivery, disposable PostgreSQL database creation

## 1. Executive Summary
- Проверялась вся платформа как связанная CRM/ATS система: recruiter surfaces, canonical lifecycle/state contract, scheduling integrity/repair, portal/session recovery, delivery/MAX reliability, auth/permission boundaries, data consistency, degraded-mode operability и performance sanity.
- Система уже имеет сильную platform-quality основу в read-side contract, portal/MAX/session hardening, auth boundary hardening и delivery reliability. Эти зоны дают хороший engineering signal и выглядят пригодными для дальнейшего развития малыми безопасными tranche.
- Система остается only conditionally reliable в scheduling-sensitive write scope. Главный факт: repo-wide backend baseline сейчас не green. `make test` падает на scheduling write path, где `POST /api/slots/{slot_id}/propose` возвращает `403` вместо ожидаемого `201`.
- Второй ключевой фактор риска: часть test landscape создает ложное чувство защищенности. `pytest` и Playwright в текущем harness в основном работают на SQLite, а не на production-like PostgreSQL. Поэтому platform readiness для scheduling-sensitive и migration-sensitive направлений доказана не полностью.
- Итоговый verdict: **NO-GO** для широкого следующего этапа развития при предпосылке "без высокого риска скрытых регрессий". Для узких направлений возможен controlled progress, но не для scheduling-sensitive expansion и не для broad readiness declaration.

## 2. Test Strategy Overview
| Testing Type | Goal | Zones Covered | Method Used | Signal |
| --- | --- | --- | --- | --- |
| Functional | Проверить критические бизнес-сценарии | recruiter list/detail/dashboard/messenger, candidate create, portal/session, booking/invite | Playwright critical/smoke + stateful pytest API suites | Strong for isolated contour |
| Regression | Проверить, не сломан ли baseline | repo-wide backend/frontend gates | `make test`, frontend gates, targeted suites | Mixed: frontend green, backend red |
| Integration | Проверить stateful и broker-level поведение | portal/MAX/scheduling API, Redis broker | API-level pytest, Redis integration test | Good for tested slices, weak for Postgres |
| API / contract | Проверить wire contract и blocker semantics | canonical state contract, portal/session, write contract, MAX preflight | targeted pytest on router/service contracts | Strong |
| State transition | Проверить allowed/disallowed transitions | lifecycle use cases, scheduling conflict/repair, hired/not hired | targeted pytest | Strong |
| Negative | Проверить fail-closed behavior | stale token/session, invalid invite, unauthorized access, blocked writes | targeted pytest | Strong |
| Edge-case | Проверить fragile transitional states | ownership ambiguity, multiple active assignments, split-brain, header recovery | targeted pytest | Strong for backend contract |
| Exploratory | Проверить UX-critical flows beyond pure unit/API assertions | recruiter flows, messenger, mobile candidate detail, candidate creation | guided browser passes via Playwright | Partial but meaningful |
| UX-critical flow verification | Проверить user-facing operational clarity | dashboard, list, detail, messenger, mobile tabs | `critical-flows.spec.ts` | Strong for current browser scope |
| Compatibility | Проверить supported scenario compatibility | desktop Chromium, mobile Safari-like viewport | Playwright Chromium desktop + mobile emulation | Partial only; no Firefox/WebKit matrix |
| Role / permission | Проверить access boundaries | auth/session/CSRF/admin/recruiter separation | targeted pytest | Strong |
| Security-oriented verification | Проверить fail-closed trust boundaries | portal/session/MAX/auth/token surfaces | targeted pytest + doc/code audit | Strong in tested contours |
| Data consistency | Проверить contract consistency между surfaces | candidates list/detail/dashboard/kanban/scheduling summaries | contract-aware pytest + browser surfaces | Good on read-side, limited on live persistence posture |
| Reliability / resilience | Проверить idempotency, retries, degraded paths | outbox, Redis broker, MAX invite reuse, stale denial | targeted pytest + Redis integration | Strong |
| Performance sanity | Проверить hot spots без full load program | dashboard/incoming polling, messenger long-poll, bundle size, query patterns | build budget + code inspection + e2e network traces | Moderate |
| Readiness / operability | Проверить health, explicit degraded mode, diagnosability | `/health`, messenger/system health semantics, degraded policy | Playwright health + code/doc inspection | Moderate |

## 3. Test Coverage Assessment
### Strong Coverage
- Portal/session API and recovery contract:
  - token exchange
  - stale token rejection
  - `recoverable`
  - `needs_new_link`
  - `session_version` invalidation
- MAX ownership and delivery contract:
  - same invite + same user idempotency
  - same invite + different user conflict
  - stale token denial
  - public onboarding fallback
  - ownership preflight classification
- Security/auth/permission boundaries:
  - unauthenticated route denial
  - protected surface checks
  - production guardrails for legacy auth flags
  - CSRF policy checks
- Lifecycle and recruiter contract:
  - canonical filters/buckets/kanban semantics
  - dedicated lifecycle use cases
  - blocker semantics
  - refreshed canonical state after writes
- Scheduling conflict/repair backend contract:
  - conflict surfacing
  - `repair_workflow`
  - manual repair subset
  - assignment-authoritative flow
- Delivery reliability:
  - outbox retry
  - deduplication
  - notification log idempotency
  - Redis broker dequeue/requeue/DLQ/claim-stale

### Conditional Coverage
- Recruiter browser surfaces:
  - list/detail/dashboard/messenger/candidate create are green in browser
  - but browser-level coverage is still Chromium-only
- Data consistency across surfaces:
  - read-side contract consistency is well asserted
  - persistence posture is still mostly SQLite-backed
- Operability/degraded mode:
  - explicit degraded semantics exist in code and were observed in e2e startup/runtime
  - not proven under production-like sustained failure scenarios
- Analytics/KPI:
  - dashboard KPI widgets render and API endpoints answer
  - business correctness and large-data behavior remain partial

### Weak Coverage
- True PostgreSQL migration/runtime behavior under isolated repeatable QA run
- Browser-level portal recovery journey (`/candidate/start` and `/candidate/journey`) as end-to-end UX
- Recruiter-facing repair UI, because frontend repair surface was not found in landed UI
- Production-like performance/load behavior under realistic traffic and external provider conditions
- Multi-browser compatibility beyond current Chromium project

### Misleading Coverage Zones
- `tests/conftest.py` forces the main pytest harness to SQLite and also rewrites `TEST_DATABASE_URL`, which means a nominally "repo-wide" backend pass is not a clean PostgreSQL confidence signal.
- `frontend/app/playwright.config.ts` runs browser flows against a temporary SQLite DB. This is useful for UX/smoke, but not enough for Postgres-sensitive readiness claims.
- The repo contains many tests, but count alone is not protection:
  - backend test files: `171`
  - frontend unit/component test files: `17`
  - Playwright specs: `13`
  - integration test files under `tests/integration`: `2`
- Test landscape has heavy mock/monkeypatch reliance:
  - files referencing mocks/monkeypatch patterns: `98`
- Only a limited subset explicitly asserts the new canonical contract fields:
  - files referencing key contract fields such as `candidate_next_action`, `operational_summary`, `state_reconciliation`, `scheduling_summary`, `blocking_state`, `repair_workflow`, `session_version`, `ownership_ambiguous`: `12`

## 4. Validation Performed
Полный command log и результаты вынесены в [verification-snapshot.md](./verification-snapshot.md). Ключевые прогоны:

| Area | Command Set | Result |
| --- | --- | --- |
| Backend repo-wide baseline | `make test` | Red |
| Frontend static/unit/build baseline | `lint`, `typecheck`, `test`, `build:verify` | Green |
| Browser smoke | `npm --prefix frontend/app run test:e2e:smoke` | Green |
| Browser UX-critical | `cd frontend/app && npx playwright test tests/e2e/critical-flows.spec.ts` | Green |
| Health / operability | `cd frontend/app && npx playwright test tests/e2e/health.spec.ts` | Green |
| Portal/session contract | `tests/test_candidate_portal_api.py` | Green |
| MAX ownership/reliability | `tests/test_max_candidate_flow.py tests/test_max_owner_preflight.py` | Green |
| Security/auth/CSRF | `tests/test_admin_surface_hardening.py tests/test_security_auth_hardening.py tests/test_admin_csrf_policy.py` | Green |
| Lifecycle/write contract | `tests/test_candidate_lifecycle_use_cases.py tests/test_candidate_write_contract.py tests/test_workflow_hired.py` | Green |
| Scheduling conflict/repair | targeted `tests/test_admin_candidate_schedule_slot.py` + `tests/test_admin_candidates_service.py` | Green |
| Reliability/outbox/Redis | retry/dedup/idempotency/broker suites | Green |
| Webapp booking/invite | booking/manual booking/invite/auth suites | Green |

## 5. Findings by Testing Type
| Testing Type | Findings |
| --- | --- |
| Functional | Recruiter list/detail/dashboard/messenger/candidate create are green in browser. Portal exchange/recovery and webapp booking/invite flows are green in targeted API suites. |
| Regression | Overall regression bar is red because `make test` fails on scheduling write path. Frontend baseline is green, so the red signal is concentrated in backend scheduling mutation behavior. |
| Integration | Redis broker integration is green. Stateful API integration around portal/MAX/scheduling is meaningful. True Postgres integration remains unproven in this isolated run. |
| API / contract | Canonical recruiter state contract, blocker payloads, portal recovery states and MAX ownership semantics are consistently exercised and look coherent. |
| State transition | Dedicated lifecycle use cases and hired/not-hired transitions are green. Scheduling transition integrity paths are green in targeted subsets, but one repo-wide slot propose path regressed. |
| Negative | Fail-closed behavior is strong on stale portal token, stale session version, invalid invite, unauthorized routes and blocked recruiter writes. |
| Edge-case | Multiple active assignments, split-brain states, ownership ambiguity and same-invite/different-owner behavior are explicitly surfaced and tested. |
| Exploratory | Guided exploratory browser flows found no new visible UX break in recruiter detail, messenger, mobile tabs or candidate creation. Exploratory depth is limited by lack of live provider and missing repair UI. |
| Role / permission | Strong signal: unauthenticated access, wrong auth mode, protected route gating and legacy production flag denial all passed. |
| Security-oriented verification | Strong fail-closed posture in tested surfaces. No evidence of relaxed auth or token trust boundary regressions in isolated QA contour. |
| Data consistency | Read-side consistency is good: canonical filters, queue/kanban semantics, reconciliation and scheduling summaries align in tested routes. Persistence posture across PostgreSQL remains only partially evidenced. |
| Reliability / resilience | Outbox retry/dedup/idempotency and Redis broker behavior are strong. MAX invite reuse/conflict behavior is strong. |
| UX-critical flow verification | Strong isolated-browser signal on dashboard, candidates, slots, messenger and mobile candidate detail. Portal browser recovery remains only partially covered. |
| Compatibility | Only partial signal. Supported Chromium desktop/mobile-like scenarios are green. No Firefox/WebKit evidence was gathered in this run. |
| Performance sanity | Bundle budgets are green. Hot paths use explicit batching/eager loading patterns. Messenger long-poll is expected and operational, but remains a sustained-traffic hotspot to watch. |
| Readiness / operability | Health endpoint is green. Degraded-mode posture is explicit in code and visible in test runtime. Clean Postgres proof is missing, so operability confidence is incomplete. |

## 6. Findings by Product Zone
| Product Zone | Assessment | Notes |
| --- | --- | --- |
| Recruiter surfaces | Good, but not release-clean | Browser list/detail/dashboard/messenger/candidate create are green. Repair workflow UI is not landed. |
| Lifecycle / state contract | Strong | Canonical filters, next action, operational summary, reconciliation and blocker semantics are coherent in targeted suites. |
| Scheduling | Fragile / blocked | Conflict/repair semantics are strong, but repo-wide baseline is red on slot propose write path. |
| Repair workflow | Backend-strong, UX-partial | Backend contract is explicit and tested. Recruiter-facing repair UI was not found, so operator experience is not validated as a UI flow. |
| Portal / onboarding | Strong in API contract, partial in browser | Recovery, stale denial and session version handling are solid. Browser end-to-end portal UX remains only partial. |
| Delivery / MAX | Strong | Invite/idempotency/conflict/preflight behavior is well covered and looks stable in isolated QA. |
| Security / auth | Strong | Auth boundaries, CSRF policy and fail-closed semantics are well covered. |
| Data integrity / consistency | Good on read-side, conditional on persistence layer | Cross-surface contract signal is good. Production-like DB behavior is not fully proven. |
| Analytics / KPI | Partial | KPI surfaces render and APIs respond, but correctness under large datasets was not validated in this audit. |
| Maintainability hotspots as regression risk | Medium to high | Scheduling write side is transitional; SQLite-forced harness hides true DB behavior; messenger polling deserves ongoing watch. |

## 7. Risk Register
| ID | Severity | Where | How Reproduced / Observed | Why It Matters | Covered by Tests | Blocks Development |
| --- | --- | --- | --- | --- | --- | --- |
| RR-001 | Critical | Scheduling write path | `make test` fails in [tests/test_admin_candidate_schedule_slot.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_admin_candidate_schedule_slot.py) because `POST /api/slots/{id}/propose` returns `403` instead of expected `201` | Active regression in recruiter/scheduling mutation baseline | Yes, directly | Yes for scheduling-sensitive scope |
| RR-002 | High | Test harness truthfulness | [tests/conftest.py](/Users/mikhail/Projects/recruitsmart_admin/tests/conftest.py) rewrites main pytest path to SQLite; Postgres migration integration is effectively skipped | Inflates confidence and can hide DB-specific regressions | Yes, by inspection and command evidence | Yes for broad readiness claims |
| RR-003 | High | Postgres verification posture | Disposable Postgres DB could not be created because local role lacks `CREATE DATABASE`; clean migration/runtime proof was not completed | Migration/runtime safety for next tranche is partial, not proven | Partially | Yes for migration-sensitive scope |
| RR-004 | High | Scheduling repair operator UX | Backend repair contract exists; frontend repair UI was not found | Safe repair may require backend/API/manual operator knowledge instead of landed product UI | Yes, by code/test audit | Yes for expanding repair-first product UX |
| RR-005 | Medium | Portal browser recovery UX | Portal browser recovery is covered by route/unit/API tests, but not by dedicated browser e2e | Real browser regressions in cabinet recovery could slip through | Partially | No, but limits confidence |
| RR-006 | Medium | Messenger / polling hotspot | Playwright critical flows observed repeated long-poll requests and 1-3s warnings; code shows persistent long-poll loops | Likely okay now, but sustained traffic cost remains sensitive | Yes, partially | No, watch item |
| RR-007 | Medium | Operability under degraded mode | Degraded-mode semantics exist and were observed, but not validated against production-like failure drill | On-call confidence is lower than code structure suggests | Partially | No, but limits bold rollout |
| RR-008 | Low | SQLite e2e bootstrap noise | E2E boot logs show `ALTER TABLE ... TYPE` warning skipped on SQLite | Not a prod bug, but adds noise and can mask real bootstrap issues | Yes | No |
| RR-009 | Low | Warning debt | Pydantic protected namespace warning and SQLite datetime deprecation warnings remain | Noise in QA logs and CI makes failures harder to read | Yes | No |

## 8. Readiness Verdict
**Verdict: NO-GO**

Причина не в общем качестве системы, а в сочетании двух фактов:
- есть подтвержденный unresolved write-side regression в scheduling-sensitive path;
- current evidence overstates platform readiness because the main automated harness is largely SQLite-backed.

Это означает следующее:
- **не готово** декларировать broad low-risk readiness для следующего этапа развития как единой платформы;
- **не готово** идти в scheduling-sensitive expansion, migration-sensitive changes или aggressive release claims;
- **можно двигать точечно** read-side recruiter UX, isolated contract cleanup, delivery/MAX observability и другие зоны, не завязанные на unresolved scheduling write path и не требующие нового Postgres proof.

## 9. What Must Be Fixed Next
1. Разобрать и закрыть regression на `slot propose` write path, затем вернуть `make test` в green baseline.
2. Исправить test harness truthfulness: не подменять clean Postgres integration signal SQLite-режимом для тех suites, которые декларируются как PostgreSQL-backed.
3. Добавить reproducible PostgreSQL verification path, который не зависит от прав `CREATE DATABASE` в ручном локальном окружении.
4. Либо посадить recruiter-facing repair UI, либо явно признать repair backend-only workflow и закрепить operator runbook/acceptance boundary.
5. Добавить browser-level portal recovery e2e для `/candidate/start` и `/candidate/journey`.
6. Зафиксировать explicit scheduling write ownership regression checklist перед следующим tranche.

## 10. What Can Safely Progress Now
- Recruiter read-side UX polish на уже стабилизированном canonical contract.
- Further hardening and cleanup around `candidate_next_action`, `operational_summary`, `state_reconciliation`, filter/bucket semantics.
- Delivery/MAX observability, ownership preflight workflows, non-schema rollout prep.
- Portal product polish, если она не меняет auth/session/token semantics.
- Reliability/operability improvements and diagnostics around degraded mode, health surfaces and polling observability.

## 11. Assumptions and Limits
- Audit executed only in isolated QA contour.
- No runtime code fixes were applied during the audit.
- Existing command results were reused as evidence when still valid in the same worktree.
- Main automated harness is heavily SQLite-backed:
  - `pytest` main path through `tests/conftest.py`
  - Playwright through `frontend/app/playwright.config.ts`
- Disposable PostgreSQL database could not be created because local role lacks `CREATE DATABASE`.
- A direct Postgres reachability probe succeeded (`select 1`), but this is not sufficient proof of clean migration/runtime readiness.
- No live provider/MAX probing and no local dev DB mutation were performed.
- Compatibility signal is limited to Chromium desktop and mobile emulation.
- Recruiter-facing repair UI was not found in landed frontend code, so repair UX conclusions are backend-contract-only.

## Related Evidence
- [verification-snapshot.md](./verification-snapshot.md)
- [release-blockers.md](./release-blockers.md)
- [regression-register.md](./regression-register.md)
