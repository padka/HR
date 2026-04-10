# Release Blockers

## Purpose
Явный список блокеров для readiness verdict по состоянию на isolated QA snapshot 2026-04-06.

## Owner
QA / Release Engineering

## Status
Active

## Last Reviewed
2026-04-06

## Current Gate Decision
- Gate decision: **NO-GO**
- Reason: unresolved scheduling write regression plus incomplete production-like persistence proof

## Current Blockers
| Blocker | Severity | Why It Blocks |
| --- | --- | --- |
| `make test` is red on slot propose write path | Critical | Repo-wide backend baseline is not release-clean; scheduling-sensitive mutation behavior is not trustworthy |
| Main automated harness is largely SQLite-backed | High | Current green signal overstates platform readiness for Postgres/migration/runtime-sensitive paths |
| No disposable clean-Postgres verification path in this audit | High | Broad readiness claim cannot be made for migration/runtime correctness |
| Recruiter-facing repair UI not landed/validated | High | Repair workflow is backend-contract strong but operator product flow is not end-to-end validated |

## Non-Blockers But Watch Items
| Item | Severity | Notes |
| --- | --- | --- |
| Messenger long-poll traffic | Medium | Expected and functioning, but remains a sustained-traffic hotspot to monitor |
| Portal browser recovery e2e gap | Medium | Backend/API contract strong; browser-level regression could still slip |
| SQLite e2e bootstrap warning | Low | Noise, not current blocker |
| Warning debt in test logs | Low | Pydantic/sqlite warnings reduce signal clarity |

## Exit Criteria For Re-Assessment
1. `make test` returns green again.
2. Slot propose regression is either fixed or explicitly re-baselined with updated business contract and tests.
3. PostgreSQL verification path is made truthful and repeatable.
4. Repair workflow UX boundary is made explicit:
   - either recruiter-facing UI is landed and tested
   - or operator-only/API-only posture is documented and accepted
