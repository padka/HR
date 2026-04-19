# RS-DATA-012: Phase A Backfill Readiness Report

## Status
Blocked

## Date
2026-04-16

## Scope
Read-only readiness audit for `RS-SPEC-010` profiler:
- [docs/architecture/specs/rs-spec-010-primary-application-resolver-event-publisher-backfill.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/specs/rs-spec-010-primary-application-resolver-event-publisher-backfill.md)
- [scripts/profile_phase_a_backfill_readiness.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/profile_phase_a_backfill_readiness.py)
- [tests/test_profile_phase_a_backfill_readiness.py](/Users/mikhail/Projects/recruitsmart_admin/tests/test_profile_phase_a_backfill_readiness.py)

## Environment
- Python runner: `.venv/bin/python`
- Python version: `3.13.7`
- Environment: `development`
- DB target: PostgreSQL via `postgresql+asyncpg` on local `localhost:5432`
- DB name: masked local RecruitSmart development database

## Read-Only Safety
- Profiler reviewed as read-only: aggregate `SELECT` queries only
- No writes, no migrations, no commits, no backfill, no manual data repair
- No candidate names, phones, Telegram IDs, MAX IDs, emails, tokens, raw payloads, or secrets emitted in success output
- Error handling sanitized to avoid leaking raw driver details in `stderr`

## Execution Summary
Profiler execution was attempted against the configured `.env.local` database and failed before aggregate counts could be collected.

Observed result:
- profiler exit code: `1`
- failure class: `ProgrammingError`
- sanitized message: `database schema is unavailable or not migrated`

Direct read-only schema introspection confirmed the blocker:
- Phase A tables present in target DB: `0 / 16`
- `candidate_journey_sessions` bridge columns present: `0 / 4`
- missing bridge columns include:
  - `application_id`
  - `last_access_session_id`
  - `last_surface`
  - `last_auth_method`

## Checks Performed
- Environment/dependency check
- Read-only profiler code review
- Security/PII review
- Focused profiler test run
- Direct profiler execution against `.env.local`
- Read-only schema introspection via `information_schema`

## Counts
Profiler data-quality counts were **not produced** because execution stopped on schema mismatch before the first full aggregate pass.

Available execution-level counts:

| Metric | Value |
| --- | --- |
| `phase_a_tables_present_count` | `0 / 16` |
| `candidate_journey_bridge_cols_present_count` | `0 / 4` |
| `profiler_exit_code` | `1` |
| `profiler_test_cases_passed` | `4` |

## Required Data-Quality Checks
The profiler is designed to cover these buckets, but all live counts are currently blocked by the missing Phase A schema:
- `phone_normalized` duplicates
- Telegram identity conflicts
- `max_user_id` conflicts
- HH-linked candidates
- HH identity conflicts
- `source` / `desired_position` without deterministic vacancy
- `slot_assignments` link gaps
- active `slot_assignments` conflicts
- `chat_messages` integrity gaps
- `outbox_notifications` / `notification_logs` mapping gaps
- detailization / interview artifact gaps
- AI provenance gaps
- journey / access gaps
- duplicate invite chains

## Blockers
### Execution blockers
- The configured live database has not been migrated to Phase A additive schema.
- `candidate_journey_sessions.last_access_session_id` is absent in the target DB.
- None of the Phase A additive tables required by later backfill stages are present in the target DB.

### Phase B blockers implied by spec
- identity collisions remain unmeasured until profiler can run
- scheduling anchor conflicts remain unmeasured until profiler can run
- invite/access chain conflicts remain unmeasured until profiler can run

## Warnings
- The profiler itself is healthy and read-only, but current findings are incomplete because they are schema-blocked, not data-complete.
- Test run emits an existing Pydantic warning unrelated to this task.
- Shell is not running inside an activated venv, but `.venv/bin/python` is healthy and was used directly.

## Ambiguous Buckets
The following buckets are expected by spec but currently have no live counts due the schema blocker:
- `outbox_mapping_gaps`
- `notification_log_mapping_gaps`
- `journey_access_gaps`

## Recommended Manual Review Queues
The profiler defines these review queues. Counts are unavailable until the schema blocker is removed.

| Queue | Intended purpose |
| --- | --- |
| `identity_conflicts_review` | phone, Telegram, and MAX ownership conflicts |
| `ambiguous_demand_review` | weak demand hints with no deterministic requisition |
| `scheduling_link_review` | missing or conflicting scheduling anchors |
| `delivery_mapping_review` | chat / outbox / notification reconstruction gaps |
| `ai_provenance_review` | AI rows without deterministic candidate/application provenance |
| `journey_access_review` | journey sessions, access-session gaps, duplicate invite chains |

## Lossless vs Non-Lossless Backfill
### Deterministic when data is clean
- exact strong anchors only
- unique phone ownership
- unique Telegram ownership
- unique MAX ownership
- exact HH linkage
- clean slot-assignment ownership
- unique invite chain per candidate/channel

### Partial
- weak demand-only candidates
- city-only candidates
- chat rows with candidate mismatch
- detailization rows without slot anchor
- AI provenance gaps
- outbox / notification artifacts with incomplete mapping

### Unsafe
- identity collisions
- scheduling conflicts
- invite token channel conflicts
- ambiguous ownership chains that would force merges or wrong application binding

### Fill-forward
- historical journey progress without safe access-session ownership
- advisory delivery evidence that cannot be reconstructed losslessly
- null-requisition application anchors where demand is weak but continuity is required

## Backfill Decision Table
| Entity | Backfill readiness | Blockers | Manual review needed | Phase recommendation |
| --- | --- | --- | --- | --- |
| Candidate identities (`phone`, Telegram, MAX, HH) | `unsafe` until measured | live profiler blocked; identity conflicts not yet counted | yes | unblock schema first, then run profiler before resolver hardening |
| Demand / requisition hints | `partial` | live profiler blocked; weak-demand buckets not counted | yes | null-requisition backfill only after profiler run |
| Slot assignments / scheduling anchors | `unsafe` until measured | live profiler blocked; scheduling conflict buckets not counted | yes | keep scheduling as legacy truth, repair anchors before Phase B dual-write |
| Messaging / delivery artifacts | `partial` | live profiler blocked; mapping gaps not counted | yes | advisory backfill or null-forward only |
| Detailization / interview artifacts | `partial` | live profiler blocked; orphan artifact counts not collected | maybe | use as evidence only, not authoritative interview reconstruction |
| AI provenance | `partial` | live profiler blocked; unmappable AI counts unknown | yes | candidate-scoped deterministic subset first |
| Journey / access sessions | `fill-forward` | missing Phase A bridge columns in DB | yes | apply Phase A schema, then treat historical rows as progress-first |
| Invite chains | `unsafe` until measured | live profiler blocked; duplicate active chains not counted | yes | review active token chains before access/session hardening |

## Commands Executed
```bash
.venv/bin/python -m py_compile scripts/profile_phase_a_backfill_readiness.py tests/test_profile_phase_a_backfill_readiness.py
.venv/bin/ruff check scripts/profile_phase_a_backfill_readiness.py tests/test_profile_phase_a_backfill_readiness.py
.venv/bin/python -m pytest -q tests/test_profile_phase_a_backfill_readiness.py
zsh -lc 'set -a; source .env.local; set +a; .venv/bin/python scripts/profile_phase_a_backfill_readiness.py --format text'
set -a; source .env.local; set +a; .venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from backend.core.settings import get_settings
...
PY
```

## Result Details
- `py_compile`: passed
- `ruff`: passed
- `pytest tests/test_profile_phase_a_backfill_readiness.py`: `4 passed`, `1 warning`
- live profiler run: blocked on schema mismatch
- read-only schema introspection: confirmed `0 / 16` Phase A tables and `0 / 4` journey bridge columns in the target DB

## What Must Happen Before Phase B
1. Apply Phase A additive schema to the target database used by `.env.local`.
2. Re-run the profiler unchanged in the same read-only mode.
3. Generate a second revision of this report with actual aggregate counts.
4. Only after that classify real blockers vs warnings vs ambiguous buckets for manual cleanup planning.

