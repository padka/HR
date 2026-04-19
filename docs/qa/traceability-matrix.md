# Traceability Matrix

## Header
- Purpose: матрица трассировки от критичных рисков и flow к docs, тестам, owner и release gate.
- Owner: QA / Architecture
- Status: Canonical, P0
- Last Reviewed: 2026-04-16
- Source Paths: `docs/architecture/*`, `docs/security/*`, `docs/qa/*`, `tests/`
- Related Diagrams: `docs/qa/critical-flow-catalog.md`, `docs/qa/release-gate-v2.md`

## Matrix

| Flow / risk | Source of truth docs | Primary tests | Owner | Gate |
| --- | --- | --- | --- | --- |
| Candidate lifecycle | `docs/architecture/core-workflows.md`, `docs/data/data-dictionary.md` | backend pytest, API integration, browser smoke | Backend + QA | Release Gate v2 |
| Slot booking / reschedule / intro-day | `docs/architecture/core-workflows.md`, `docs/data/data-dictionary.md` | backend pytest, browser flow, DB integration | Backend / QA | Release Gate v2 |
| Recruiter dashboard / candidate detail | `docs/frontend/route-map.md`, `docs/frontend/screen-inventory.md` | frontend unit, browser smoke | Frontend | Release Gate v2 |
| Telegram delivery reliability | `docs/architecture/core-workflows.md`, `docs/runbooks/broker-degradation.md`, `docs/frontend/state-flows.md` | integration, retry/idempotency tests, delivery health unit, system delivery smoke | Backend / Frontend / QA | Release Gate v2 |
| HH sync / import | `docs/architecture/core-workflows.md`, `docs/security/auth-and-token-model.md` | integration tests, mapping regressions | Backend | Release Gate v2 |
| Auth / session / CSRF | `docs/security/auth-and-token-model.md`, `docs/security/trust-boundaries.md` | security regression matrix, integration tests | Security + Backend | Release Gate v2 |
| OpenAPI truth gate | `README.md`, `docs/qa/master-test-plan.md`, `docs/qa/release-gate-v2.md` | `make openapi-check`, tooling regressions | Backend / QA | Release Gate v2 |
| Health / protected metrics | `docs/architecture/runtime-topology.md`, `docs/security/trust-boundaries.md` | health auth regressions, metrics auth regressions | Backend / Security | Release Gate v2 |

## Strategy Notes
- Legacy candidate portal implementation is unsupported and is not tracked here as a current release flow.
- Historical MAX runtime is unsupported and is not tracked here as a current release flow.
- Future standalone candidate web flow and future MAX mini-app/channel adapter remain target-state product directions, but they are intentionally excluded from the current release gate until a separate runtime contract exists.
