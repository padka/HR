# Migrations

This document is the current RecruitSmart Maxpilot migration policy for the
hardening release stream.

## Tooling

- Migration runner: [scripts/run_migrations.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/run_migrations.py)
- Alembic versions: [backend/migrations/versions](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions)
- Staging schema check: [scripts/staging_schema_compatibility.sql](/Users/mikhail/Projects/recruitsmart_admin/scripts/staging_schema_compatibility.sql)
- PostgreSQL proof gate: `make test-postgres-proof`

Application startup must not apply schema changes. Migrations are a separate
deploy step with explicit flags and a backup-first rollout plan.

## Current Chain

The hardening release restored the production-observed chain:

```text
0103_persistent_application_idempotency_keys
  -> 0104_candidate_web_public_intake
  -> 0105_unique_users_max_user_id
```

`0104_candidate_web_public_intake` is additive-only. It creates public candidate
campaign and intake tables used by the browser candidate flow.

`0105_unique_users_max_user_id` aligns the repository with the production audit
fact that `uq_users_max_user_id_nonempty` exists on `users(max_user_id)`.

PostgreSQL index definition:

```sql
CREATE UNIQUE INDEX uq_users_max_user_id_nonempty
ON users (max_user_id)
WHERE max_user_id IS NOT NULL AND btrim(max_user_id) <> '';
```

The full recovery record is in
[docs/MIGRATION_RECONCILIATION_0105.md](/Users/mikhail/Projects/recruitsmart_admin/docs/MIGRATION_RECONCILIATION_0105.md).

## Safety Rules

- Never invent a migration revision to make a deployment pass.
- Never stamp staging or production without an approved reconciliation plan.
- Never run migrations against staging or production without a fresh DB backup.
- Never embed duplicate cleanup in the `0105` migration. Duplicate identity
  remediation is a separate, reviewed data operation.
- Keep migrations small, reversible where possible, and backward-compatible with
  the previous application version.
- Prefer additive DDL before runtime cutover.

## Environment Flags

Migration-enabled deploy:

```bash
MIGRATION_HISTORY_RECONCILED=true
RUN_MIGRATIONS=true
AUTO_MIGRATE=false
```

Code-only staging validation:

```bash
RUN_MIGRATIONS=false
CODE_ONLY_DEPLOY_APPROVED=true
AUTO_MIGRATE=false
```

`CODE_ONLY_DEPLOY_APPROVED=true` is only valid for a documented validation pass.
It is not a permanent production posture.

## Local Validation

```bash
make test-postgres-proof
make openapi-check
```

`make test-postgres-proof` verifies migration behavior against a local
PostgreSQL proof database. It is required after migration changes and before any
staging migration-enabled validation.

## Staging

Staging may use one of two modes:

- Migration-enabled: preferred after staging backup and readonly compatibility
  checks.
- Code-only: allowed only when schema is already compatible and migration
  execution is explicitly disabled.

Before a migration-enabled staging pass, run:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/staging_schema_compatibility.sql
```

Do not use production or live-like hosts as staging.

## Production

Production migration preconditions:

- staging smoke is green;
- production DB backup completed and verified;
- `MIGRATION_HISTORY_RECONCILED=true`;
- duplicate groups for `max_user_id`, `telegram_id`, and `telegram_user_id` are
  zero;
- rollback release ref and backup path are recorded;
- deploy window is approved.

If production already reports `0105_unique_users_max_user_id`, the recovered
files allow the migration runner to recognize the current head. If production
has the `0105` index but an unexpected migration version, stop and reconcile
explicitly.

## Rollback And Compensating Plan

Runtime rollback is the primary path:

1. Stop application writes if the incident affects identity or scheduling.
2. Restore previous release code.
3. Restore env/nginx/systemd files from backup if they were changed.
4. Restore DB from the pre-deploy backup only if the failed step mutated data or
   schema in a way that cannot be safely compensated.

The `0104` and `0105` downgrades intentionally avoid destructive drops. If an
incident decision requires removing an index or table, that is a separate manual
database change with explicit approval and backup confirmation.
