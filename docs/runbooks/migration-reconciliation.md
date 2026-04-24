# Migration Reconciliation

Date: 2026-04-25

## Summary

Result: **not recovered**.

The local repository still ends at `0103_persistent_application_idempotency_keys`.
The production audit states production is at `0105_unique_users_max_user_id` and has
the unique index `uq_users_max_user_id_nonempty`.

No `0104` or `0105` migration files were recovered from local files or fetched Git
history. Production rollout remains blocked for any workflow that runs migrations
until the missing migration history is recovered from the VPS/release artifact/backup
or a formal reconstructed migration plan is approved.

## Local Migration State

- Migration runner package: `backend.migrations.versions`
- Migration storage table: `alembic_version`
- Local migration count: 107
- Local first revision: `0001_initial_schema`
- Local head revision: `0103_persistent_application_idempotency_keys`
- Local tail:
  - `0098_tg_max_reliability_foundation`
  - `0099_add_users_phone_normalized`
  - `0099a_refresh_interview_confirmation_copy`
  - `0101_add_hh_outbound_job_fields`
  - `0102_phase_a_schema_foundation`
  - `0103_persistent_application_idempotency_keys`

## Production Audit State

- Reported production revision: `0105_unique_users_max_user_id`
- Reported production index: `uq_users_max_user_id_nonempty`
- Reported integrity: duplicate counts by `max_user_id`, `telegram_id`, `telegram_user_id` were 0 at audit time.

## Search Performed

Commands were run locally only:

- `git fetch --all --tags --prune`
- `git branch -a`
- `git tag`
- `git log --all --oneline -- backend/migrations scripts/run_migrations.py scripts/contour_preflight.py`
- tree grep across `git rev-list --all` for:
  - `0105_unique_users_max_user_id`
  - `uq_users_max_user_id_nonempty`
  - `persistent_application_idempotency_keys`
  - `0104`
  - `0105`
  - `unique_users`
  - `max_user_id`
- filesystem search excluding `.git`:
  - `find . -type f | grep -E '0104|0105|unique_users|max_user_id'`

Evidence artifacts:

- Branch list: `/tmp/recruitsmart-migration-branches.txt`
- Tag list: `/tmp/recruitsmart-migration-tags.txt`
- Migration history log: `/tmp/recruitsmart-migration-git-log.txt`
- Tree grep outputs: `/tmp/recruitsmart-migration-treegrep-*.txt`
- Filesystem search output: `/tmp/recruitsmart-migration-find.txt`

## Findings

- `0105_unique_users_max_user_id` was found only in `docs/runbooks/release-artifact-freeze-notes.md`.
- `uq_users_max_user_id_nonempty` was found only in `docs/runbooks/production-hardening-candidate-scale.md`.
- No `backend/migrations/versions/*0104*.py` file was found.
- No `backend/migrations/versions/*0105*.py` file was found.
- No migration file defining `uq_users_max_user_id_nonempty` was found.
- Existing MAX identity schema is introduced earlier by `0090_add_messenger_fields.py`, which creates a non-unique lookup index `ix_users_max_user_id`.
- Migration discovery is linear: `backend/migrations/runner.py` sorts by `revision` and rejects out-of-order `down_revision` values.
- The runner does not support multi-head reconciliation for unknown production revisions; an unknown `alembic_version` raises `Database is at unknown migration revision`.

## Safe Deployment Interpretation

Safe to deploy without migrations: **only if the deployment procedure explicitly skips migration execution** and code compatibility is validated against the production schema.

Migration reconciliation required before deploy: **yes**, for any rollout path that runs the migration runner.

## Required Next Step

Before production rollout, recover the missing migration files from one of:

- production VPS release directory;
- previous deployment artifact;
- backup/snapshot;
- maintainer machine or branch not available in current refs.

If the files cannot be recovered, prepare a separate approval request for formal reconstruction:

- reconstruct `0104` only if its intended schema can be proven;
- reconstruct `0105_unique_users_max_user_id` to match the audited production unique index;
- keep operations idempotent;
- use the exact revision id if production `alembic_version` requires it;
- test on a clean DB and on a DB at `0103`;
- verify duplicate identity checks before any unique-index creation.

No fake migration, stamp, or production migration action is approved by this report.
