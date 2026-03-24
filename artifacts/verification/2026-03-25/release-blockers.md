# Release Blockers

## Purpose
Явный список блокеров для Release Gate v2 по состоянию на verification snapshot 2026-03-25.

## Owner
QA / Release Engineering

## Status
Active

## Last Reviewed
2026-03-25

## Source Paths
- `artifacts/verification/2026-03-25/*`
- `docs/qa/release-gate-v2.md`

## Related Diagrams
- `docs/qa/release-gate-v2.md`

## Change Policy
Если blocker снят или появляется новый, обновлять этот файл вместе с verification snapshot и ссылкой на подтверждающий тест/документ.

## Current Status
- Открытых release blockers не зафиксировано.
- Полный baseline run завершен green; подтверждение в `verification-snapshot.md`.

## Gate Checklist
| Area | Status | Evidence |
| --- | --- | --- |
| Backend suite | Green | `make test`, `make test-cov` |
| Frontend static/unit/build | Green | `lint`, `typecheck`, `test`, `build:verify` |
| Browser smoke | Green | `test:e2e:smoke` |
| Full browser regression | Green | `test:e2e` |
| Canonical docs pack | Green | `docs/README.md`, `docs/architecture/*`, `docs/data/*`, `docs/frontend/*`, `docs/security/*`, `docs/qa/*`, `docs/runbooks/*`, `docs/adr/*` |
