# Migration Reconciliation 0104/0105

Date: 2026-04-25

## Summary

Result: **actual files recovered locally, pending CI/staging verification**.

The missing production migration history was recovered from the adjacent local
worktree `/Users/mikhail/Projects/recruitsmart_admin_browser_candidate`.

Recovered files:

- `backend/migrations/versions/0104_candidate_web_public_intake.py`
- `backend/migrations/versions/0105_unique_users_max_user_id.py`

The files were not present in the `release/hardening-artifact-freeze` branch or
in fetched remote refs before recovery.

## Recovery Evidence

Local recovery source:

- worktree: `/Users/mikhail/Projects/recruitsmart_admin_browser_candidate`
- branch: `codex/browser-candidate-pilot-audit`
- observed status: the migration files were untracked in that worktree
- no staging or production access was used
- no database mutation was performed during recovery

Searches performed before recovery:

- `git fetch --all --tags --prune`
- `git log --all --name-only -- backend/migrations/versions`
- `git grep` across `git rev-list --all`
- `/tmp/recruitsmart-hardening-worktree.patch`
- `/tmp/recruitsmart-hardening-index.patch`
- `/tmp/recruitsmart-hardening-untracked.tgz`
- sibling local worktrees under `/Users/mikhail/Projects`

## Revision Chain

The recovered linear chain is:

```text
0103_persistent_application_idempotency_keys
  -> 0104_candidate_web_public_intake
  -> 0105_unique_users_max_user_id
```

`0104_candidate_web_public_intake` is additive-only and creates:

- `candidate_web_campaigns`
- `candidate_web_public_intakes`

`0105_unique_users_max_user_id` is a narrow integrity migration for MAX identity.

## 0105 Index Definition

Production audit reported index:

```text
uq_users_max_user_id_nonempty
```

Recovered PostgreSQL definition:

```sql
CREATE UNIQUE INDEX uq_users_max_user_id_nonempty
ON users (max_user_id)
WHERE max_user_id IS NOT NULL AND btrim(max_user_id) <> '';
```

SQLite test definition:

```sql
CREATE UNIQUE INDEX uq_users_max_user_id_nonempty
ON users (max_user_id)
WHERE max_user_id IS NOT NULL AND trim(max_user_id) <> '';
```

The index allows multiple `NULL` and empty-string values and rejects duplicate
non-empty MAX user ids.

## Safety Properties

- No destructive DDL is introduced.
- `0104` creates new tables only.
- `0105` creates a unique partial index only.
- `0105` is idempotent when the target index already exists.
- Historical duplicate cleanup is intentionally not embedded in the migration.
- Production must verify duplicate count for non-empty `max_user_id` is `0`
  before any migration-enabled rollout.

Required preflight duplicate check:

```sql
SELECT max_user_id, COUNT(*)
FROM users
WHERE max_user_id IS NOT NULL AND btrim(max_user_id) <> ''
GROUP BY max_user_id
HAVING COUNT(*) > 1;
```

## ORM Metadata Alignment

`backend/domain/candidates/models.py` now reflects the production index:

```text
uq_users_max_user_id_nonempty
```

This keeps SQLAlchemy metadata aligned with the recovered production schema.

## Tests

Added coverage:

- `tests/test_candidate_web_migrations.py`
- `tests/integration/test_migrations_postgres.py`

Expected local commands:

```bash
python -m py_compile \
  backend/migrations/versions/0104_candidate_web_public_intake.py \
  backend/migrations/versions/0105_unique_users_max_user_id.py \
  tests/test_candidate_web_migrations.py

pytest -q tests/test_candidate_web_migrations.py
make test-postgres-proof
```

`make test-postgres-proof` requires a local PostgreSQL proof database and must
pass before migration-enabled staging or production rollout.

## Production Impact

If production is already at `0105_unique_users_max_user_id`, the recovered files
allow the migration runner to recognize the current revision instead of failing
with an unknown production head.

If production is at `0103`, `0104` and `0105` can be applied after backup and
duplicate preflight, subject to normal staging validation.

If production schema has the `0105` index but an unexpected `alembic_version`,
stop and reconcile explicitly. Do not stamp or fake a revision without approval.

## Rollback / Compensating Plan

Downgrades are intentionally non-destructive.

Compensating action if `0105` creates operational issues immediately after a
controlled migration-enabled deploy:

1. Stop writes that can bind MAX identities.
2. Verify a fresh database backup exists.
3. Restore the previous release code.
4. If and only if an approved incident decision requires removing the guard,
   drop `uq_users_max_user_id_nonempty` manually after capturing duplicate risk.
5. Keep any submitted candidate/manual availability data; do not delete business
   rows as part of rollback.

Production rollout remains blocked until CI and staging validation confirm this
recovered chain.
