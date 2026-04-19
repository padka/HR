# RS-IDEMP-019: Persistent Idempotency And Concurrency For Application Writes

- Status: Proposed
- Date: 2026-04-16
- Scope: Phase B preparation only; no runtime wiring, no dual-write enablement, no migration in this task
- Companion docs:
  - [RS-SPEC-010](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/specs/rs-spec-010-primary-application-resolver-event-publisher-backfill.md)
  - [RS-RFC-007](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/rfc/rs-rfc-007-phase-a-schema-and-api-contract-pack.md)
  - [RS-PLAN-006](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/implementation/rs-plan-006-unified-migration-blueprint.md)

## 1. Problem Statement

Phase A added `applications`, `application_events`, pure resolver/publisher contracts, and ORM-backed adapters. That is enough for design-time and local adapter tests, but it is not yet enough for safe Phase B runtime integration.

Known blocker:

- `application_events` idempotency is implemented as read-before-write in application code.
- resolver create idempotency is currently stored only in `Session.info`.
- neither path has a durable cross-transaction claim point in PostgreSQL.

Result:

- same producer scope + same idempotency key can still race across transactions/processes;
- resolver create retries can mint duplicate `applications`;
- webhook and `n8n` duplicate callbacks are not yet protected by a DB-backed invariant.

Before any real dual-write or runtime integration, this must be hardened.

## 2. Current Limitation

### 2.1 `application_events`

Current Phase A state:

- `application_events.event_id` is unique.
- `application_events.idempotency_key` is nullable and not unique.
- current publisher normalizes producer-scoped idempotency in code, not in the database.
- current repository lookup is `SELECT by idempotency_key` followed by `INSERT`.

This is safe only for single-process, non-racing paths.

It is not safe for:

- concurrent same-key writes under PostgreSQL `READ COMMITTED`;
- callback retries from `n8n` or provider webhooks across workers/processes;
- timeout/retry cases where the second transaction cannot rely on shared process memory.

### 2.2 Resolver create path

Current Phase A state:

- `SqlAlchemyApplicationResolverRepository.get_created_application_by_idempotency()` reads from `session.info`.
- `create_application()` writes the idempotency hit only into the same `Session.info` cache.
- a fresh SQLAlchemy session does not see prior create idempotency state.

This is explicitly not cross-transaction safe.

### 2.3 UoW layer

`SqlAlchemyApplicationUnitOfWork` correctly enforces explicit transaction scope, but it does not itself solve:

- concurrent same-key claim;
- duplicate application create under separate transactions;
- database-level replay vs conflict resolution.

## 3. Current-State Analysis

### 3.1 What exists already

- pure idempotency helpers in [backend/domain/applications/idempotency.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/applications/idempotency.py)
- transactional publisher contract in [backend/domain/applications/events.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/applications/events.py)
- ORM-backed repositories in [backend/domain/applications/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/applications/repositories.py)
- explicit UoW boundary in [backend/domain/applications/uow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/applications/uow.py)
- Phase A schema foundation in [backend/domain/models.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py) and [0102_phase_a_schema_foundation.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0102_phase_a_schema_foundation.py)

### 3.2 What is missing

- durable cross-transaction idempotency ledger for `application_event` writes
- durable cross-transaction idempotency ledger for `resolver_create`
- database-enforced same-key conflict serialization
- PostgreSQL-backed concurrency proof for same-key racing transactions

### 3.3 Can current Phase A schema alone provide safe cross-transaction idempotency?

No.

Reason:

- `application_events.idempotency_key` is intentionally not hard-unique in Phase A.
- retrofitting uniqueness directly onto `application_events` would still not solve resolver create idempotency.
- current resolver create path has no persistent idempotency storage at all.

## 4. Options Considered

| Option | Summary | Safety | Migration risk | Phase A compatibility | PostgreSQL concurrency | Resolver create coverage | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | dedicated idempotency ledger table | high | low-medium | high | high | high | recommended |
| B | add scoped/hash columns + partial unique on `application_events` | medium | medium | medium | medium | low | reject |
| C | rely on normalized uniqueness inside `application_events` only | low-medium | high | low | medium | none | reject |
| D | keep advisory-only in app code | low | low | high | low | low | reject |

### 4.1 Option A: dedicated ledger table

Pros:

- additive and isolated from dirty legacy `application_events` history;
- works for both `application_event` and `resolver_create`;
- concurrency safety lives in PostgreSQL unique constraint, not process memory;
- stable for webhook/`n8n` duplicates across workers.

Cons:

- requires a separate additive migration candidate;
- introduces one extra write/update per protected operation.

### 4.2 Option B: new columns + partial unique on `application_events`

Pros:

- keeps event dedupe close to event storage.

Cons:

- still event-only, does not protect resolver create;
- forces more invasive schema mutation on an already additive Phase A table;
- partial unique logic becomes tightly coupled to producer rollout namespaces;
- conflict semantics remain awkward for existing nullable/legacy rows.

### 4.3 Option C: normalized uniqueness on current `application_events`

Pros:

- fewer tables.

Cons:

- incompatible with current Phase A decision to avoid hard uniqueness on `application_events.idempotency_key`;
- still does not cover resolver create;
- higher legacy pollution risk.

### 4.4 Option D: advisory-only

Pros:

- no schema work.

Cons:

- not acceptable before dual-write;
- cannot guarantee cross-process or cross-transaction safety;
- fails the stated Phase B blocker.

## 5. Recommended Design

### 5.1 Decision

A separate additive persistent idempotency schema is required before real Phase B runtime integration.

Recommended form:

- migration candidate: `0103_persistent_application_idempotency_keys`
- new table: `application_idempotency_keys`

This is intentionally broader than `application_event_idempotency_keys`, because the same ledger must protect:

- `application_event` publisher writes
- resolver/application-create writes

### 5.2 Minimal schema shape

Recommended table:

`application_idempotency_keys`

| Column | Type | Null | Notes |
| --- | --- | --- | --- |
| `id` | bigserial | no | PK |
| `operation_kind` | varchar(32) | no | `application_event` or `resolver_create` |
| `producer_family` | varchar(64) | no | same producer namespace used by contracts |
| `idempotency_key` | varchar(160) | no | raw caller key, not globally unique |
| `payload_fingerprint` | char(64) | no | canonical SHA-256 of normalized payload |
| `candidate_id` | bigint | no | FK to `users.id` |
| `application_id` | bigint | yes | FK to `applications.id`; set after create or on event replay anchor |
| `requisition_id` | bigint | yes | FK to `requisitions.id` |
| `event_id` | varchar(36) | yes | canonical event id for `application_event`; no FK required in initial cut |
| `correlation_id` | varchar(64) | no | same trace id used across flow |
| `source_system` | varchar(32) | no | producer origin |
| `source_ref` | varchar(255) | no | external/business anchor |
| `created_at` | timestamptz | no | default `now()` |
| `updated_at` | timestamptz | no | default `now()`, touched when `application_id` is filled |

Required unique/indexes:

- unique `(operation_kind, producer_family, idempotency_key)`
- index `(candidate_id, created_at desc)`
- index `(application_id, created_at desc)`
- index `(correlation_id)`

Deliberate choices:

- do not hard-unique `application_events.idempotency_key` in `0103`
- do not require `event_id` FK in the first cut; keep the ledger insert/update ordering simple

### 5.3 Why this is compatible with Phase A

- Phase A already left `application_events.idempotency_key` non-unique on purpose.
- the new ledger does not mutate or reinterpret dirty legacy rows.
- runtime can keep writing nothing to the new table until Phase B wiring is explicitly introduced.

## 6. Desired Behavior

### 6.1 Same key, same payload

For the same `(operation_kind, producer_family, idempotency_key)`:

- if `payload_fingerprint` matches, return the already committed resource
- do not create a second `application`
- do not append a second `application_event`

### 6.2 Same key, different payload

For the same `(operation_kind, producer_family, idempotency_key)`:

- if `payload_fingerprint` differs, return hard conflict
- do not overwrite or mutate the existing ledger row
- do not mutate previously committed business rows

### 6.3 Retry after timeout

- if first transaction committed, retry returns existing resource via ledger row
- if first transaction rolled back, retry behaves as a fresh request

### 6.4 Callback duplicates

For webhook or `n8n` retries:

- same external callback must map to the same `producer_family + idempotency_key`
- same payload reuses the existing event
- changed payload under the same key is a semantic conflict and must be surfaced

### 6.5 Resolver create duplicates

- same resolver create request with same producer namespace and key must reuse the same application
- different idempotency keys can still race logically if the caller is incorrect; that remains a domain-level duplicate detection concern, not an idempotency concern

## 7. Transaction Behavior

### 7.1 `application_event` publish

Desired Phase B sequence in one DB transaction:

1. Build canonical `event_id`, `correlation_id`, `payload_fingerprint`.
2. Try to insert `application_idempotency_keys` row with `operation_kind='application_event'`.
3. If inserted:
   - append `application_events` row with the same `event_id`
   - commit
4. If unique conflict:
   - fetch existing ledger row
   - compare `payload_fingerprint`
   - same fingerprint => fetch existing `application_events` row by `event_id` and reuse
   - different fingerprint => conflict

### 7.2 Resolver create

Desired Phase B sequence in one DB transaction:

1. Build deterministic create payload fingerprint from candidate/application-create request.
2. Try to insert `application_idempotency_keys` row with `operation_kind='resolver_create'` and `application_id=NULL`.
3. If inserted:
   - perform deterministic duplicate checks
   - insert `applications` row
   - update the ledger row with `application_id`, `requisition_id`, `updated_at`
   - commit
4. If unique conflict:
   - fetch existing ledger row
   - same fingerprint + existing `application_id` => reuse existing application
   - different fingerprint => conflict

Important:

- no autocommit assumptions
- no advisory-lock-only fallback
- if the business mutation fails, the ledger row must roll back with it

## 8. PostgreSQL Isolation And Concurrency Notes

### 8.1 Why current code is insufficient

Without a unique ledger row, two transactions can both do:

1. `SELECT no existing key`
2. `INSERT event/application`

Under PostgreSQL `READ COMMITTED`, this is a real race. The current code has no DB invariant to stop it.

### 8.2 Why the ledger works

With unique `(operation_kind, producer_family, idempotency_key)`:

- concurrent inserts for the same key serialize at the unique index
- the winner commits the canonical row
- the loser either blocks until the winner commits or aborts, then re-reads the committed ledger row

This means:

- `SERIALIZABLE` isolation is not required for idempotency correctness
- `READ COMMITTED` is acceptable if the unique ledger row is the first durable claim point

### 8.3 SQLite note

SQLite-based tests are useful for:

- contract validation
- basic persistence semantics
- rollback proof

SQLite is not sufficient proof for:

- PostgreSQL row/index contention
- lock timing
- concurrent same-key transaction races

Real PG concurrency tests must be added before runtime wiring.

## 9. Tests Needed

### 9.1 Safe to add now

- current limitation test: resolver create idempotency is session-scoped only
- current limitation test: `application_events` repository has no DB-backed same-key uniqueness guard

These tests document why `0103` is needed.

### 9.2 Required before Phase B wiring

- PostgreSQL-only concurrency test: same-key `application_event` publish from two sessions
- PostgreSQL-only concurrency test: same-key resolver create from two sessions
- conflict test: same key + different payload returns hard conflict
- timeout/retry replay test: committed first write is reused on retry
- rollback test: failed transaction leaves no ledger row and no event/application row

## 10. Rollout Phase

Recommended order:

1. approve this spec
2. prepare separate migration PR candidate for `0103_persistent_application_idempotency_keys`
3. add repository adapters for the new ledger table
4. add PostgreSQL concurrency tests
5. wire ledger into pure Phase B resolver create and event publisher
6. only then consider runtime dual-write integration

This task does not perform step 2 or beyond.

## 11. Rollback Behavior

Rollback remains simple because the design is additive:

- stop using the ledger-backed adapters
- keep reads on legacy/runtime truth
- leave `application_idempotency_keys` unused
- no route/API rollback required

Until Phase B integration starts, this is documentation-only plus isolated test coverage.

## 12. Decision Summary

- Current Phase A schema is not sufficient for safe cross-transaction idempotency.
- A separate additive persistent idempotency schema is required before dual-write.
- Recommended design is a dedicated ledger table, not hard uniqueness on current `application_events`.
- No migration is created in this task.
