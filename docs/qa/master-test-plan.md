# Master Test Plan

## Header
- Purpose: единый тест-план для RecruitSmart Admin на Phase 0: стабилизация, регрессия и выпуск релиз-кандидатов без изменения текущей runtime-модели.
- Owner: QA / Release Engineering
- Status: Canonical, P0
- Last Reviewed: 2026-04-19
- Source Paths: `backend/`, `frontend/app/`, `docs/architecture/*`, `docs/security/*`, `tests/`
- Related Diagrams: `docs/qa/critical-flow-catalog.md`, `docs/qa/traceability-matrix.md`, `docs/qa/release-gate-v2.md`
- Change Policy: обновлять при изменении test surface, критичных flow или release gate.

## Goal
План фиксирует обязательные уровни тестирования для текущего supported runtime и для repo-local verification flow.

## Current Scope
Тест-план покрывает текущую архитектуру:
- FastAPI backend
- React SPA в `frontend/app`
- Telegram bot runtime
- Telegram Mini App / recruiter webapp
- bounded MAX controlled pilot surface: `/api/max/launch`, `/api/max/webhook`, `/miniapp`, shared `/api/candidate-access/*`, operator rollout controls
- scheduling, messaging, HH sync, AI copilot / interview script

Не входят в текущий runtime scope:
- legacy candidate portal implementation;
- historical MAX runtime.

Остаются target-state notes, но не текущим test surface:
- future standalone candidate web flow;
- full MAX runtime/channel rollout beyond the bounded pilot;
- SMS / voice fallback integration.

## Test Levels

| Level | What it verifies | Examples | Required |
| --- | --- | --- | --- |
| Static checks | syntax, types, lint, schema drift, build | `make test`, `make openapi-check`, frontend lint/typecheck/build | Required for RC |
| Unit / component | isolated logic | backend pytest, frontend unit tests | Required for changed modules |
| Integration | DB, queues, webhook/idempotency, API contracts | PostgreSQL, Redis, internal workflows | Required for high-risk changes |
| Browser / smoke | critical supported browser flows | dashboard, candidates, scheduling, system page | Required for RC |
| Full E2E | supported release regression | critical flow catalog | Required for RC where maintained |
| Non-functional | security, perf smoke, observability | auth, CSRF, logs, alerts, protected metrics | Required for RC and high-risk |

## Coverage Strategy
- Backend changes validate first with targeted pytest, then with broader backend gate as needed.
- Frontend changes validate unit/component tests, then `lint`, `typecheck`, `test`, `build:verify`.
- Any change touching routes, schemas, contracts, or OpenAPI tooling must run `make openapi-check` as a mandatory repo-local gate.
- Health/metrics hardening changes must include anonymous-negative and authenticated-positive checks where relevant.
- Canonical docs and verification docs must not advertise unsupported legacy surfaces as current runtime.
- Changes touching bounded MAX pilot surfaces must run a targeted MAX pilot proof suite even though MAX is not a supported live messaging runtime rollout.

## Minimal Mandatory Commands

```bash
make openapi-check
make test
make test-cov
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
```

### Targeted MAX Pilot Proof
Для bounded MAX launch/auth changes дополнительно прогонять:

```bash
pytest tests/test_max_auth.py tests/test_max_launch_invites.py tests/test_max_launch_api.py tests/test_messenger_max_seam.py tests/test_runtime_surface_stabilization.py tests/test_max_webhook_api.py tests/test_max_miniapp_shell.py tests/test_max_e2e_pilot_flow.py -q
```

Для mounted MAX candidate mini-app and shared candidate-access surface дополнительно прогонять:

```bash
pytest tests/test_max_launch_api.py tests/test_candidate_access_api.py tests/test_max_candidate_chat.py tests/test_max_miniapp_shell.py tests/test_max_e2e_pilot_flow.py -q
```

Для operator-facing MAX rollout surface дополнительно прогонять:

```bash
pytest tests/test_admin_max_runtime_surfaces.py tests/test_max_launch_api.py tests/test_candidate_access_api.py -q
```

И при изменении admin UI или operator visibility в списках/карточках:

```bash
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

Для pilot-proof evidence дополнительно нужен authenticated browser walkthrough со скриншотами или явной фиксацией ограничения, если Computer Use недоступен. Он должен покрывать и operator MAX surfaces, и candidate `/miniapp`, включая intake-first launch, Test1 progression, no-slots manual-availability success, booked return state и bounded recovery cards.

## Acceptance Criteria
- All mandatory commands are green.
- For each supported critical flow there are at least two layers of verification.
- No undocumented critical regression remains in the release candidate.
- Canonical docs and tracked OpenAPI stay aligned with the live runtime surface.
- Bounded MAX pilot proof can show either real non-prod provider success or an explicit external blocker; fake provider success is never acceptable.
