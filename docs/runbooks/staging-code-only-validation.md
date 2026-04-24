# Staging Code-Only Validation Contract

Date: 2026-04-25

Release ref: use the latest immutable `rc/hardening-candidate-scale-20260425-N`
tag created after this document commit. Do not move older RC tags.

Commit: verify with `git rev-parse <RC_TAG>^{}` before handoff.

## Scope

This runbook is for staging validation of the hardening release artifact only.
It must not be used to mutate production. It must not run migrations while the
`0104`/`0105` migration history is unresolved.

## Preconditions

- Use the exact immutable RC tag selected for CI handoff.
- Staging DB must already be production-like enough for the code.
- `RUN_MIGRATIONS=false` must be set.
- `CODE_ONLY_DEPLOY_APPROVED=true` must be set.
- `AUTO_MIGRATE=false` must be set for staging/prod-like app startup.
- No `MIGRATIONS_DATABASE_URL` is needed for code-only validation because no DDL
  must run.

If the deploy mechanism cannot force migrations off, staging validation is
NO-GO.

## Local Artifact Handoff

Create a new immutable RC tag from the final clean HEAD:

```bash
RC_TAG=rc/hardening-candidate-scale-20260425-<N>
git status --short
git tag -a "$RC_TAG" -m "RC hardening candidate scale 20260425-<N>" HEAD
git rev-parse "$RC_TAG^{}"
```

To hand off to CI, push the branch/tag from a clean worktree:

```bash
RC_TAG=rc/hardening-candidate-scale-20260425-<N>
git status --short
git push origin release/hardening-artifact-freeze
git push origin "$RC_TAG"
```

CI must run from the tag or branch ref, not from a local workspace.

## Deployment Contract

The docker deploy script now has an explicit migration contract:

- If `RUN_MIGRATIONS=false`, `CODE_ONLY_DEPLOY_APPROVED=true` is required.
- If migrations are enabled, `MIGRATION_HISTORY_RECONCILED=true` is required.
- Code-only mode starts app services with `docker compose up -d --no-deps ...`
  to avoid implicitly starting the `migrate` service through `depends_on`.
- Admin UI startup auto-migration is disabled for `ENVIRONMENT=staging` and
  `ENVIRONMENT=production`, and also respects `RUN_MIGRATIONS=false`.

Staging command if the staging host uses this docker deploy script:

```bash
ENVIRONMENT=staging \
RUN_MIGRATIONS=false \
CODE_ONLY_DEPLOY_APPROVED=true \
AUTO_MIGRATE=false \
./scripts/deploy_production.sh
```

If staging uses a different deployment system, it must enforce the same contract
before this release is deployed:

```bash
RUN_MIGRATIONS=false
CODE_ONLY_DEPLOY_APPROVED=true
AUTO_MIGRATE=false
```

## Read-Only Schema Compatibility

Run before smoke and before any code-only deploy if possible:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f scripts/staging_schema_compatibility.sql
```

Expected minimum result:

- `alembic_version` is production-like, ideally `0105_unique_users_max_user_id`.
- `uq_users_max_user_id_nonempty_exists` is `true`.
- duplicate groups for `max_user_id`, `telegram_id`, and `telegram_user_id` are
  all `0`.
- manual availability columns are present on `users`.
- `slot_reservation_locks` has `uq_slot_reservation_locks_key`.
- `hh_sync_jobs` has fields used by forbidden/retention handling:
  `status`, `candidate_id`, `result_json`, `failure_code`, timestamps, and retry
  fields.

If any required object is missing, stop staging validation. Do not run
migrations to repair it.

## Staging Smoke

Run only after schema compatibility passes and code-only deploy is confirmed:

```bash
curl -sSI https://candidate.staging.example/apply/main
curl -sSI 'https://candidate.staging.example/candidate-flow/start?campaign=main'
curl -sSI 'https://candidate.staging.example/assets/<hashed-file>.js'
```

Replace hostnames with the actual staging domains. Do not include real tokens in
commands or logs.

Required checks:

- `/apply/main` redirects to `/candidate-flow/start?campaign=main`.
- candidate shell returns `200` and `text/html`.
- public campaign `main` is active and providers are available.
- Telegram/MAX/HH verification start endpoints return structured start/authorize
  responses.
- invalid token returns safe `404 poll_not_found`.
- no-slots path shows manual availability and saves a request.
- slots path still allows booking when future slots exist.
- candidate HTML has CSP, frame, content-type, referrer, permissions, and HSTS
  headers where configured.
- HTML is not dangerously cached.
- hashed assets are `public, max-age=31536000, immutable`.
- sensitive dummy query values are redacted in logs.
- HH 403 is controlled and does not emit transaction storm logs.
- Telegram polling backoff is bounded and not hot-looping.
- no migration attempt appears in startup logs.

## Migration Recovery Track

Production preflight remains blocked until one of these is true:

- actual `0104`/`0105` files are recovered and committed;
- formal reconstruction is approved and tested;
- production deploy is explicitly approved as code-only with a migration waiver.

No fake migration, stamp, or production DDL is approved by this runbook.

## Rollback

For staging code-only validation:

```bash
git checkout <previous_staging_ref>
docker compose build --no-cache
docker compose up -d --no-deps admin_ui admin_api bot
```

If staging data was not mutated, DB rollback is not required. If any accidental
DDL/DML occurred, stop and use the staging backup/restore procedure for that
environment.
