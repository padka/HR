# Staging Handoff

Status: ready for human/devops staging target assignment. Staging execution is
blocked until a real isolated staging target is provided.

## Selected Release Candidate

Use the latest docs-inclusive RC after the docs-only commit is created and CI
passes:

```text
rc/hardening-candidate-scale-20260425-20
```

If RC-20 is not created, use the application-code RC:

```text
rc/hardening-candidate-scale-20260425-19
```

RC-19 CI evidence:

- tag run: `24925853950`
- branch run: `24925852981`
- head: `abd96eaa80eca6f2c50d866b5abf5126690e75a9`

RC-20 CI evidence must be taken from the final release report after the tag and
branch runs complete. The tag is not valid for staging handoff until CI is
green.

## Required Staging Target Inputs

The operator must provide:

- host/domain;
- deploy user;
- selected deployment method;
- DB connection through secure channel;
- Redis endpoint/namespace;
- nginx/proxy config path;
- log access;
- current staging release ref;
- rollback command;
- approval to create a staging DB backup before migration-enabled validation.

Do not use `maxpilot-vps` or `prod-ssr` as staging.

## Deploy Mode Decision

Preferred mode: migration-enabled staging.

Use only if:

- staging DB backup is complete;
- readonly compatibility check passed;
- `MIGRATION_HISTORY_RECONCILED=true`;
- migrations are explicit and observable.

Fallback mode: code-only staging.

Use only if:

- staging DB must not be mutated;
- schema is already compatible;
- `RUN_MIGRATIONS=false`;
- `CODE_ONLY_DEPLOY_APPROVED=true`;
- `AUTO_MIGRATE=false`.

Code-only smoke does not prove migration execution safety.

## Schema Compatibility Command

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f scripts/staging_schema_compatibility.sql
```

This script is readonly and reports:

- migration version;
- `uq_users_max_user_id_nonempty`;
- identity duplicate groups;
- candidate public intake tables/indexes;
- manual availability columns;
- reservation lock indexes;
- HH sync job columns/indexes/counts;
- future free slots count.

## Backup Requirement

Before any migration-enabled staging validation:

```bash
pg_dump "$DATABASE_URL" --format=custom --file "$STAGING_BACKUP_FILE"
```

Record backup path, size, timestamp, and restore command. Do not print
connection values.

## Smoke Checklist

Candidate:

- `/apply/main` redirects to `/candidate-flow/start?campaign=main`;
- candidate shell returns 200 HTML;
- campaign `main` is active;
- Telegram/MAX/HH verification start responses are valid;
- invalid token returns safe 404 `poll_not_found`;
- slots and manual availability fallback are both verified.

Security/cache:

- CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy,
  Permissions-Policy, and HSTS where applicable;
- HTML no-store/no-cache;
- hashed assets immutable cached;
- gzip if configured.

Operations:

- no migration surprise;
- no stack traces;
- no raw sensitive dummy values in logs;
- HH 403 controlled;
- no SQLAlchemy transaction storm;
- Telegram polling not hot-looping;
- no unexpected public port exposure.

## Rollback Checklist

- previous release ref recorded;
- config backup path recorded;
- DB backup path recorded when DB is mutated;
- service restart order known;
- nginx config validates after restore;
- smoke rerun after rollback.

## Blocker Statement

Production remains NO-GO until a staging target exists and staging smoke is
green. Production also requires preflight backups, HH secret rotation,
nginx/log verification, DB integrity checks, and production smoke.
