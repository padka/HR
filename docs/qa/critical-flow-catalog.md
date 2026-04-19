# Critical Flow Catalog

## Header
- Purpose: каталог критичных flow, которые должны покрываться тестами, release gate и runtime docs.
- Owner: QA / Architecture
- Status: Canonical, P0
- Last Reviewed: 2026-04-19
- Source Paths: `docs/architecture/*`, `docs/security/*`, `backend/`, `frontend/app/`
- Related Docs: `docs/architecture/supported_channels.md`, `docs/qa/traceability-matrix.md`

## Supported Critical Flows

| Flow | Description | Primary surface | Source of truth |
| --- | --- | --- | --- |
| Candidate lifecycle | Создание, просмотр, статусные переходы, recruiter actions | admin UI + SPA | `docs/data/data-dictionary.md`, `docs/route-inventory.md` |
| Slot scheduling / reschedule / intro day | Запись, перенос, подтверждение, массовые операции | admin UI + SPA | `docs/data/data-dictionary.md`, `docs/route-inventory.md` |
| Telegram messaging | Отправка, retry, operator visibility, health | bot runtime + admin UI | `docs/architecture/runtime-topology.md`, `docs/security/trust-boundaries.md` |
| Telegram Mini App / recruiter webapp | Recruiter mobile/webapp surfaces | admin API | `docs/architecture/runtime-topology.md`, `docs/frontend/route-map.md` |
| MAX bounded candidate mini-app | Signed MAX launch, `/miniapp`, hidden-draft intake bootstrap, shared candidate-access journey/Test1/booking/manual-availability/chat-handoff for controlled pilot | admin API + SPA | `docs/architecture/supported_channels.md`, `docs/frontend/route-map.md`, `docs/frontend/state-flows.md` |
| MAX bounded operator rollout surface | Invite preview/send/revoke plus operator visibility for MAX linkage and launch state | admin UI + SPA | `docs/architecture/supported_channels.md`, `docs/qa/max-pilot-rollout-checklist.md` |
| HH integration | OAuth, imports, sync jobs, HH actions | admin UI + admin API callbacks | `docs/security/auth-and-token-model.md`, `docs/architecture/supported_channels.md` |
| n8n HH callbacks | External automation callback contract | admin API | `docs/security/auth-and-token-model.md` |
| Auth / session / CSRF | Browser auth, JWT, CSRF, destructive guards | admin UI | `docs/security/auth-and-token-model.md`, `docs/security/trust-boundaries.md` |
| Health / protected metrics | Public shallow probes plus protected operator diagnostics and metrics | admin UI + admin API | `docs/architecture/runtime-topology.md` |
| OpenAPI truth gate | Drift check between tracked schema and live app factories | repo-local verification flow | `README.md`, `docs/qa/release-gate-v2.md` |

## Unsupported Or Target-State Surfaces

| Surface | Current status | QA expectation |
| --- | --- | --- |
| Legacy candidate portal implementation | unsupported | `/candidate*` should fail closed; no release promise |
| Historical MAX runtime | unsupported | default compose/runtime must not depend on MAX |
| Future standalone candidate web flow | target state | do not advertise as current runtime; no active route/API contract today |
| Future full MAX runtime / channel rollout | target state | do not advertise as current runtime; bounded `/miniapp` pilot does not equal production MAX runtime |
| SMS / voice fallback | target state | no active runtime or release gate yet |

## Coverage Expectations
- backend unit / integration for lifecycle, slot actions, destructive guards and auth/CSRF;
- anonymous-negative and authenticated-positive tests for operator-only health diagnostics;
- targeted MAX pilot smoke for `/api/max/launch`, `/api/max/webhook`, `/miniapp`, shared `/api/candidate-access/*`, rollout preview/send/revoke, webhook secret, and operator health pages;
- authenticated browser proof for candidates list visibility, candidate detail MAX card/modal states, and candidate `/miniapp` states;
- candidate `/miniapp` proof must cover hidden-draft intake bootstrap, manual review / legacy recovery, shared Test1 progression, booking empty states, no-slots manual-availability success, booked return state, and chat handoff;
- provider smoke must end either in real non-prod proof or in an explicit external blocker; no simulated provider success;
- OpenAPI drift check for live `admin_ui` and `admin_api`;
- frontend typecheck when tracked contracts change;
- targeted smoke/regression on health, metrics protection and operator surfaces.
