# PostgreSQL-Proof Expansion Tranche

## Executive Summary

- The PostgreSQL-backed proof contour was expanded from the minimal P0 subset to the next priority layer of stateful domain behavior without rewriting the full test harness.
- The expanded proof now passes on isolated PostgreSQL: `make test-postgres-proof` finished with `17 passed, 1 warning`.
- The broad backend baseline also remains green after the expansion and duplicate-test cleanup: `make test` finished with `1011 passed, 18 skipped`.
- Readiness improves from “narrow PG proof only” to a stronger but still bounded production-like posture. Updated recommendation remains `CONDITIONAL GO`.

## Scope Selection Rationale

- Scheduling manual repair workflow was added because it mutates persisted `Slot` / `SlotAssignment` ownership state and SQLite-backed confidence is weak around conflict/repair semantics.
- Remaining high-value recruiter write behavior was expanded through persisted blocker verification on kanban-sensitive scheduling conflict paths, because fast harnesses can miss database-backed split-brain state.
- MAX duplicate-owner runtime and cleanup-sensitive behavior was expanded beyond fail-closed runtime into PostgreSQL-backed preflight classification, because uniqueness rollout safety depends on real persisted evidence grouping.
- Portal recovery / restart / re-entry stayed in the tranche because session versioning, active-journey replacement, and resume-cookie restore all depend on stored state rather than pure request logic.
- Outbox proof was added only for the database-sensitive single-consumer claim path, where row-level ownership semantics matter; the rest of delivery remains outside this tranche because it is more about application logic and broker behavior than PostgreSQL semantics.

## What Changed

- Cleaned [tests/integration/test_postgres_stateful_proof.py](/Users/mikhail/Projects/recruitsmart_admin/tests/integration/test_postgres_stateful_proof.py) so each PostgreSQL-sensitive scenario is represented once; duplicate definitions that silently overwrote earlier tests were removed.
- Expanded PostgreSQL-backed proofs in [tests/integration/test_postgres_stateful_proof.py](/Users/mikhail/Projects/recruitsmart_admin/tests/integration/test_postgres_stateful_proof.py) to cover:
  - manual repair denial for cross-owner duplicate active assignments
  - kanban write blocked by persisted scheduling split-brain
  - MAX invite idempotent reuse for same owner
  - MAX invite conflict without duplicate row creation for different owner
  - MAX preflight `safe_auto_cleanup` classification
  - MAX preflight `manual_review_only` classification
  - portal restart creates a new active journey
  - portal restart blocks when interview state is already confirmed
  - portal resume-cookie restoration after browser restart
  - portal slot reserve denied when assignment owns scheduling
  - outbox single-consumer claim semantics
- Updated [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md), [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md), and [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md) so the expanded PostgreSQL confidence boundary is explicit for future agents.

## Validation Performed

### PostgreSQL-backed proof tranche

```bash
make test-postgres-proof
```

Result:

- `17 passed, 1 warning in 8.43s`

### Repo-level backend baseline

```bash
make test
```

Result:

- `1011 passed, 18 skipped, 117 warnings in 293.80s (0:04:53)`

## PostgreSQL-Proof Coverage After Expansion

### Proven on PostgreSQL now

- clean migration execution on isolated `rs_test`
- scheduling `slot propose -> pending offer`
- scheduling `confirm -> reschedule request`
- scheduling `assignment_authoritative` repair
- scheduling manual-repair denial on unsupported cross-owner duplicate active assignments
- recruiter kanban write blocked by persisted scheduling conflict
- MAX duplicate-owner runtime fail-closed behavior
- MAX invite reuse idempotency for same owner
- MAX invite reuse conflict without duplicate candidate creation for different owner
- MAX preflight classification for `safe_auto_cleanup`
- MAX preflight classification for `manual_review_only`
- portal session-version mismatch -> `needs_new_link`
- portal restart -> new active journey
- portal restart denied for confirmed interview state
- portal resume-cookie recovery after browser restart
- portal slot reserve denied when assignment owns scheduling
- outbox claim is single-consumer

### Still mainly SQLite-backed or otherwise outside this tranche

- the broad backend suite as a whole
- recruiter read-side contract across all surfaces
- browser/e2e proof for portal recovery and recruiter repair UX
- full delivery/outbox/retry matrix
- production-data MAX cleanup execution
- full cross-surface consistency and analytics/KPI verification

## Risks Remaining

- The main backend gate is still the fast default harness; PostgreSQL proof is meaningful but intentionally narrow.
- Recruiter-facing repair UI is still not landed, so repair workflow remains backend-contract proven rather than end-to-end operator proven in the browser.
- MAX cleanup execution is still not implemented/proven in this repo; only runtime fail-closed behavior and preflight classification are covered here.
- PostgreSQL proof still relies on an isolated local DDL-capable `rs_test` contour rather than a standardized repo-wide app-role vs migrator-role matrix.

## Updated Readiness Recommendation

- Verdict: `CONDITIONAL GO`
- Safe to advance now:
  - scheduling-sensitive backend evolution within the proven repair/conflict boundary
  - portal recovery/restart/re-entry work within the proven session and restart contract
  - MAX uniqueness-preparation work that depends on fail-closed runtime and preflight classification
- Still constrained:
  - do not treat the entire platform as broadly PostgreSQL-verified
  - do not overstate operator readiness for scheduling repair until the recruiter-facing UI tranche lands
  - do not treat cleanup execution as ready until replica/export-backed execution tooling exists

## Assumptions

- Work stayed inside the isolated PostgreSQL `rs_test` contour.
- No live provider, production replica, or local dev product database was used.
- The goal of this tranche was proof expansion, not a full harness migration or product-semantic rewrite.
