# Data Model

This document summarizes release-critical invariants. The schema source of truth remains the migrations and SQLAlchemy models.

## Users And Identity Fields

Candidate/user identity can include:
- `max_user_id`;
- `telegram_id`;
- `telegram_user_id`;
- campaign/source/provider metadata;
- contact fields and recruiter/admin workflow fields.

Critical invariant:
- no duplicate non-empty MAX identity;
- no duplicate Telegram identity where uniqueness is expected;
- ambiguous candidates must not be auto-merged without explicit business logic.

## MAX Identity Constraint

The hardening release reconciles production migration history through:
- `0104_candidate_web_public_intake`;
- `0105_unique_users_max_user_id`.

The critical PostgreSQL index is:

```sql
CREATE UNIQUE INDEX uq_users_max_user_id_nonempty
ON users (max_user_id)
WHERE max_user_id IS NOT NULL AND max_user_id <> '';
```

Before applying this index, duplicate groups must be checked and resolved through an approved process. The migration must not delete data automatically.

## Slots And Reservations

Slots represent interview capacity. Reservations and assignments must protect:
- no double booking;
- no silent replacement except explicit allowed flows;
- deterministic status transitions;
- recruiter/campaign capacity rules where implemented.

`slot_reservation_locks` must keep a unique lock key index compatible with process-local and database-level reservation serialization.

## Manual Availability

Manual availability captures candidate-provided scheduling preferences when no slot is available. Data should include:
- candidate/session/application reference;
- campaign/provider reference where available;
- timezone;
- 2-3 preferred windows or free-form availability;
- contact channel;
- comment;
- status and timestamps.

Ambiguous text without date context is not a precise appointment.

## Idempotency Keys

Persistent idempotency protects retry-sensitive flows:
- candidate/application creation;
- booking or reservation actions where supported;
- provider callback handling where supported.

Retries must not duplicate candidate records, assignments, messages, or business events.

## HH Sync Jobs

HH sync jobs track:
- queued/running/done/dead/forbidden/retry-scheduled states where implemented;
- retry counters and next retry time;
- failure code/category;
- result metadata;
- timestamps for retention and dashboard summaries.

Critical behavior:
- 403 becomes a controlled forbidden state;
- 401 triggers refresh or reauth-needed handling;
- 429 respects provider rate limits where available;
- network/5xx errors use bounded backoff and jitter.

## Critical Indexes And Checks

Release-critical checks:
- `uq_users_max_user_id_nonempty` exists after migration-enabled validation;
- duplicate groups for `max_user_id`, `telegram_id`, and `telegram_user_id` are zero;
- slot reservation lock unique index exists;
- HH jobs indexes support status/time summary queries or the code degrades without hot paths.
