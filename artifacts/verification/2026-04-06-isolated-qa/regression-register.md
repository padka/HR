# Regression Register

## Purpose
Реестр открытых regressions и confidence gaps, обнаруженных или подтвержденных isolated QA audit на 2026-04-06.

## Owner
QA / Reliability Audit

## Status
Active

## Last Reviewed
2026-04-06

## Confirmed Regression
### REG-001 — Slot propose write path no longer satisfies repo-wide baseline
- Area: scheduling / recruiter write flow
- Evidence:
  - `make test` fails in [tests/test_admin_candidate_schedule_slot.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_admin_candidate_schedule_slot.py)
  - failing case: `test_api_slot_propose_assigns_candidate_and_sets_slot_pending`
  - observed response: `403`
  - expected response: `201`
- Impact:
  - repo-wide backend baseline is red
  - scheduling-sensitive write confidence is broken
  - blocks clean readiness verdict
- Current status: Open

## Confidence Gaps That Behave Like Regressions In Planning
### GAP-001 — PostgreSQL proof is weaker than the suite names suggest
- Area: persistence / migrations / runtime truthfulness
- Evidence:
  - [tests/conftest.py](/Users/mikhail/Projects/recruitsmart_admin/tests/conftest.py) forces SQLite and rewrites `TEST_DATABASE_URL`
  - Playwright also runs on temporary SQLite
- Impact:
  - can hide DB-specific regressions
  - blocks bold rollout claims for migration-sensitive work
- Current status: Open

### GAP-002 — Repair workflow is backend-validated but not product-validated as UI
- Area: scheduling repair workflow
- Evidence:
  - backend repair contract and routes exist
  - no landed frontend repair UI was found in current code
- Impact:
  - operator usability and error-recovery clarity are not proven end-to-end
  - limits readiness for repair-heavy operational rollout
- Current status: Open

### GAP-003 — Portal browser recovery is not covered by dedicated browser e2e
- Area: candidate portal / onboarding
- Evidence:
  - route/unit/API coverage is good
  - dedicated browser flow for stale/resume/recovery was not executed
- Impact:
  - browser-only regressions may slip past current signal
- Current status: Open

### GAP-004 — Performance posture is sane, but not production-like
- Area: recruiter surfaces, messenger, dashboard/incoming
- Evidence:
  - bundle budgets green
  - code inspection shows explicit batching/eager loading in hot paths
  - messenger long-poll observed in browser traces
  - no production-like load run executed in this audit
- Impact:
  - safe to say "no obvious hotspot regression"
  - unsafe to say "capacity proven"
- Current status: Watch
