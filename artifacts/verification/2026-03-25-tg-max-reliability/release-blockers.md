# Release Blockers

## Purpose
Explicit blocker list for Release Gate v2 after the Telegram/MAX reliability hardening tranche.

## Owner
QA / Release Engineering

## Status
Active

## Last Reviewed
2026-03-25

## Source Paths
- `artifacts/verification/2026-03-25-tg-max-reliability/*`
- `docs/qa/release-gate-v2.md`

## Related Diagrams
- `docs/qa/release-gate-v2.md`

## Change Policy
If a blocker appears or is resolved, update this file together with the authoritative verification snapshot.

## Current Status
- Open release blockers: none.
- Full release gate completed green for the Telegram/MAX reliability tranche.

## Gate Checklist
| Area | Status | Evidence |
| --- | --- | --- |
| Backend suite | Green | `make test`, `make test-cov` |
| Frontend static/unit/build | Green | `lint`, `typecheck`, `test`, `build:verify` |
| Browser smoke | Green | `test:e2e:smoke` |
| Full browser regression | Green | `test:e2e` |
| Delivery / linking / session regressions | Green | targeted pytest bundle in `verification-snapshot.md` |
| Canonical docs + runbooks | Green | `docs/architecture/*`, `docs/security/*`, `docs/runbooks/*`, `docs/qa/*`, `docs/adr/*` |
