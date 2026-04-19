# Release Gate v2

## Header
- Purpose: описать обязательный релизный гейт для release candidate в RecruitSmart Admin.
- Owner: QA / Release Engineering
- Status: Canonical, P0
- Last Reviewed: 2026-04-19
- Source Paths: `backend/`, `frontend/app/`, `docs/qa/*`, `docs/security/*`, `docs/data/*`
- Related Diagrams: `docs/qa/critical-flow-catalog.md`, `docs/qa/traceability-matrix.md`
- Change Policy: не снижать baseline без отдельного ADR.

## Goal
Release Gate v2 блокирует выпуск, пока не выполнены обязательные проверки по качеству, безопасности, observability и текущим supported flows.

## Mandatory Checks

### 1. Static checks
- `make openapi-check`
- `make test`
- `make test-cov`
- `npm --prefix frontend/app run lint`
- `npm --prefix frontend/app run typecheck`
- `npm --prefix frontend/app run test`
- `npm --prefix frontend/app run build:verify`

`make openapi-check` обязателен для любого change set, который меняет routes, schemas, API contracts или OpenAPI tooling.

### 2. Browser / E2E
- `npm --prefix frontend/app run test:e2e:smoke`
- `npm --prefix frontend/app run test:e2e`

### 3. Security regression matrix
- admin session
- recruiter session / bearer flows
- destructive endpoints feature flag + CSRF + typed confirmation
- Telegram runtime/operator diagnostics auth boundary
- protected metrics boundary
- webhook trust
- rate limiting

Не включать в эту матрицу как current runtime:
- legacy candidate portal token/session recovery;
- historical MAX runtime invite/onboarding flow.

### 3.1 MAX bounded pilot gate
Применяется только для change set, который трогает MAX launch/auth shell, MAX adapter seam, mounted `/miniapp`, shared candidate-access MAX surface или release-gate proof для MAX.

- Run the canonical operator checklist in `docs/qa/max-pilot-rollout-checklist.md`.
- `MAX_ADAPTER_ENABLED=false` and `MAX_INVITE_ROLLOUT_ENABLED=false` remain the safe baseline before readiness is proven.
- `GET /health/max` and `POST /health/max/sync` are admin-only checks; `POST /health/max/sync` also requires CSRF.
- `/api/max/launch`, `/api/max/webhook`, `/miniapp`, and protected admin MAX invite endpoints remain fail-closed when MAX is disabled, rollout is disabled, or the pilot is unconfigured.
- `start_param` stays short, opaque and PII-free.
- MAX launch preview stays dry-run when adapter is disabled.
- Preview and send stay distinct; real send requires explicit operator action, adapter readiness, and a configured token.
- Candidate list/detail operator surfaces must expose bounded MAX channel and rollout state without raw token/provider internals.
- Candidate access session bootstrap works through `/api/max/launch` when signed `init_data` is valid.
- Bounded proof covers the mounted candidate mini-app at `/miniapp` plus the shared `/api/candidate-access/*` surface used by MAX: `me`, `journey`, `test1*`, booking context, slots, bookings, manual-availability, confirm/reschedule/cancel, and `chat-handoff`.
- Bounded proof covers hidden-draft intake bootstrap, Test1 completion, no-slots manual-availability, and slot confirm/reschedule on the existing shared seams, but not a full MAX runtime promise.
- Telegram smoke remains green.
- OpenAPI drift remains clean.
- No real MAX send path is enabled by default.
- Candidate detail operator surface exposes invite/send/launch state without raw `start_param` or raw launch URL leakage in non-dry-run responses.
- Authenticated browser proof must exist for candidates list visibility, candidate detail MAX card/modal states, and candidate `/miniapp` states. If provider creds are absent, only fail-closed runtime proof plus an explicit external blocker is acceptable; do not simulate successful provider smoke.
- Any live restart on `recruitsmart-admin.service` or `recruitsmart-maxpilot-admin-api.service` must be preceded by `python scripts/contour_preflight.py --contour <admin|maxpilot> --root <contour_root>`. Partial file-by-file deploys without contour preflight do not pass the release gate.

### 4. Migration preflight
- проверка совместимости миграций с текущей схемой;
- проверка rollback surface;
- проверка критичных таблиц и nullable/default изменений.

### 5. Perf smoke
- `/api/candidates`
- `/api/dashboard/*`
- slot booking / reschedule
- `/api/system/messenger-health`

### 6. Observability verification
- public health checks expose only shallow payload;
- operator diagnostics require auth;
- logs do not leak secrets or unnecessary PII;
- protected metrics stay behind auth and/or deployment boundary;
- runbook exists for known failure domains.

## Gate Decision

| State | Decision |
| --- | --- |
| All checks green | Release candidate can proceed |
| Static check fails | Block release candidate |
| Security / migration / perf smoke fails | Block release candidate |
| Undocumented critical regression exists | Block release candidate |
| Only non-critical known issue exists with explicit waiver | Release owner decision required |

## Strategy Notes
- Future standalone candidate web flow remains a target-state product direction, but it is not part of the current release gate.
- Full MAX mini-app/channel runtime rollout remains a target-state product direction and is not part of the general release gate.
- Mounted `/miniapp` and shared `/api/candidate-access/*` are part of the bounded MAX pilot gate, not of the general production release gate.
- SMS / voice fallback remains a target-state integration direction, but it is not part of the current release gate.
