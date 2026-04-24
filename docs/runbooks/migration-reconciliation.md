# Migration Reconciliation

Date: 2026-04-25

## Summary

Result: **recovered after freeze**.

The release branch originally ended at `0103_persistent_application_idempotency_keys`.
The production audit states production is at `0105_unique_users_max_user_id` and has
the unique index `uq_users_max_user_id_nonempty`.

Actual `0104` and `0105` files were later recovered from the adjacent local
worktree `/Users/mikhail/Projects/recruitsmart_admin_browser_candidate` and
committed into the release branch. See
`docs/MIGRATION_RECONCILIATION_0105.md` for the detailed recovery report,
revision chain, index SQL, safety notes, and tests.

## Local Migration State

- Migration runner package: `backend.migrations.versions`
- Migration storage table: `alembic_version`
- Local migration count before recovery: 107
- Local first revision: `0001_initial_schema`
- Local head revision before recovery: `0103_persistent_application_idempotency_keys`
- Local head revision after recovery: `0105_unique_users_max_user_id`
- Local tail:
  - `0098_tg_max_reliability_foundation`
  - `0099_add_users_phone_normalized`
  - `0099a_refresh_interview_confirmation_copy`
  - `0101_add_hh_outbound_job_fields`
  - `0102_phase_a_schema_foundation`
  - `0103_persistent_application_idempotency_keys`
  - `0104_candidate_web_public_intake`
  - `0105_unique_users_max_user_id`

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

## Findings Before Recovery

- `0105_unique_users_max_user_id` was found only in `docs/runbooks/release-artifact-freeze-notes.md`.
- `uq_users_max_user_id_nonempty` was found only in `docs/runbooks/production-hardening-candidate-scale.md`.
- No `backend/migrations/versions/*0104*.py` file was found.
- No `backend/migrations/versions/*0105*.py` file was found.
- No migration file defining `uq_users_max_user_id_nonempty` was found.
- Existing MAX identity schema is introduced earlier by `0090_add_messenger_fields.py`, which creates a non-unique lookup index `ix_users_max_user_id`.
- Migration discovery is linear: `backend/migrations/runner.py` sorts by `revision` and rejects out-of-order `down_revision` values.
- The runner does not support multi-head reconciliation for unknown production revisions; an unknown `alembic_version` raises `Database is at unknown migration revision`.

## Recovery Finding

- `0104_candidate_web_public_intake.py` and `0105_unique_users_max_user_id.py`
  were found in `/Users/mikhail/Projects/recruitsmart_admin_browser_candidate`.
- The recovered `0105` creates `uq_users_max_user_id_nonempty` with PostgreSQL
  predicate `max_user_id IS NOT NULL AND btrim(max_user_id) <> ''`.
- ORM metadata now reflects the same unique partial index.

## Safe Deployment Interpretation

Safe to deploy without migrations: **yes, if the deployment procedure explicitly skips migration execution** and code compatibility is validated against the production schema.

Migration reconciliation required before deploy: **recovered locally, but still requires CI and staging migration proof** before any migration-enabled production rollout.

## Required Next Step

Before migration-enabled production rollout:

- run CI on the committed recovery;
- run clean PostgreSQL migration proof;
- run staging schema compatibility;
- verify production duplicate checks before any unique-index creation path;
- do not stamp or fake a revision without a separate approved reconciliation.
