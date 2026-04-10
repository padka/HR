# P0 Regression Recovery + PostgreSQL-Proof Tranche

## Executive Summary

- Backend baseline is green again on the current branch: `make test` passed with `1011 passed, 7 skipped`.
- The previously reported `slot propose` regression (`403` instead of `201`) did **not** reproduce on the current HEAD in isolated reruns or in the repo-level backend gate.
- The meaningful blocker that remained was inflated SQLite confidence. That is now reduced by a new PostgreSQL-backed tranche covering:
  - clean migration execution
  - scheduling `propose` path
  - scheduling `confirm + reschedule` path
  - slot vs slot-assignment repair/integrity path
  - MAX ownership ambiguity fail-closed path
  - portal session version recovery boundary
- PostgreSQL proof tranche now passes: `6 passed`.
- Updated recommendation: `CONDITIONAL GO`.
  - The original broad `NO-GO` caused by missing backend green baseline + no PG proof is no longer accurate.
  - Full-platform confidence is still not equivalent to “broad PostgreSQL-backed suite”, because the main backend gate remains the fast default harness and only the critical stateful subset is now proven on PostgreSQL.

## Problem Reproduction

### Slot propose blocker

- Original QA audit recorded `make test` failing on:
  - `tests/test_admin_candidate_schedule_slot.py::test_api_slot_propose_assigns_candidate_and_sets_slot_pending`
- Current reproduction attempts on the same branch:
  - isolated test rerun: green
  - full scheduling file rerun: green
  - repo-level `make test`: green
- Conclusion:
  - there is no longer a live reproducible `slot propose` failure on the current HEAD
  - the backend baseline itself is restored
  - no direct product-logic patch to the `slot propose` handler was required in this tranche

### PostgreSQL-proof blocker

- As soon as critical tests were forced onto PostgreSQL, two PostgreSQL-only defects surfaced immediately:
  1. migration runner executed the whole chain in one transaction, which broke enum-add migrations before later migrations could safely use new enum values
  2. `message_templates` sequence drift after table rebuild caused duplicate primary key failures in later template upsert migrations

## What Changed

### Harness / verification

- Added explicit PostgreSQL opt-in mode in [tests/conftest.py](/Users/mikhail/Projects/recruitsmart_admin/tests/conftest.py)
  - default suite behavior stays SQLite-backed
  - `TEST_USE_POSTGRES=1` preserves a PostgreSQL URL instead of force-overwriting it with SQLite
- Added PostgreSQL proof marker in [pytest.ini](/Users/mikhail/Projects/recruitsmart_admin/pytest.ini)
- Added dedicated verification target in [Makefile](/Users/mikhail/Projects/recruitsmart_admin/Makefile)
  - `make test-postgres-proof`
- Documented the new verification command in [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)

### PostgreSQL-backed proof tests

- Added [tests/integration/test_postgres_stateful_proof.py](/Users/mikhail/Projects/recruitsmart_admin/tests/integration/test_postgres_stateful_proof.py)
  - `slot propose -> pending offer`
  - `confirm -> reschedule request`
  - `assignment_authoritative` repair
  - MAX duplicate-owner ambiguity fail-closed
  - portal resume cookie/session version mismatch -> `needs_new_link`
- Reused existing [tests/integration/test_migrations_postgres.py](/Users/mikhail/Projects/recruitsmart_admin/tests/integration/test_migrations_postgres.py) inside the PostgreSQL tranche so clean migrations are now part of the same proof command

### PostgreSQL defects fixed

- Updated [backend/migrations/runner.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/runner.py)
  - migrations now run one-transaction-per-migration instead of one giant transaction for the whole chain
  - this fixes PostgreSQL enum visibility semantics during upgrades
- Updated [backend/migrations/versions/0034_message_templates_city_support.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0034_message_templates_city_support.py)
  - sequence for `message_templates.id` is resynced after ID-preserving table rebuild
- Updated [backend/migrations/versions/0086_update_interview_notification_templates.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0086_update_interview_notification_templates.py)
- Updated [backend/migrations/versions/0087_update_t1_done_template.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0087_update_t1_done_template.py)
- Updated [backend/migrations/versions/0088_upgrade_candidate_template_texts.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0088_upgrade_candidate_template_texts.py)
  - all three now resync the `message_templates` sequence before insert-on-miss behavior
  - this protects both clean upgrades and already-migrated DBs with stale sequence state

## Validation Performed

### Repo-level backend gate

```bash
make test
```

Result:

- `1011 passed, 7 skipped, 117 warnings in 297.05s`

### PostgreSQL-backed proof tranche

```bash
make test-postgres-proof
```

Result:

- `6 passed, 1 warning in 5.05s`

Covered tests:

- `tests/integration/test_migrations_postgres.py`
- `tests/integration/test_postgres_stateful_proof.py`

## PostgreSQL-Proof Coverage

### Proven on PostgreSQL now

- clean migration execution on isolated `rs_test`
- scheduling propose write path
- scheduling confirm/reschedule path
- slot vs slot-assignment repair/integrity path
- MAX ownership ambiguity fail-closed behavior
- portal session version mismatch / recovery boundary

### Still not broadly proven on PostgreSQL

- full backend suite
- recruiter read-side contract as a whole
- browser/e2e flows
- all portal UX flows in browser
- all delivery/outbox permutations
- full cross-surface consistency matrix

## Risks Remaining

- The main backend gate still relies on the default fast harness, so broad suite confidence remains mixed rather than fully PostgreSQL-backed.
- PostgreSQL proof currently depends on a local DDL-capable role for the isolated `rs_test` database; this tranche does not yet standardize a repo-wide migrator/app-role split for local automated testing.
- `slot propose` did not reproduce as failing on the current branch, so this tranche closes the blocker operationally by green baseline evidence, not by a direct functional patch to that route.

## Updated Readiness Recommendation

- Verdict: `CONDITIONAL GO`
- Safe to proceed:
  - scheduling/lifecycle work that depends on the validated critical paths above
  - MAX ownership uniqueness-preflight follow-up with the new PostgreSQL guardrail in place
  - portal/session recovery work within the already-proven boundary
- Still constrained:
  - do not treat the full backend suite as “production-like PostgreSQL verified”
  - do not remove caution around broader transitional recruiter surfaces or unproven browser flows

## Assumptions

- Work stayed inside the isolated `rs_test` contour.
- No local dev application DB was used for stateful product verification.
- PostgreSQL proof used a local DDL-capable role only to initialize and validate the isolated proof database.
- The current `slot propose` blocker is considered closed by reproducible green baseline evidence on the present HEAD, not by a route-level behavior change in this tranche.
