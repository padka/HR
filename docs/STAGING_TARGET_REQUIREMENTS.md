# Staging Target Requirements

Status: required before executing staging validation.

Application-code baseline: `rc/hardening-candidate-scale-20260425-19`.

Docs-inclusive handoff target: `rc/hardening-candidate-scale-20260425-20`
after the docs-only commit is tagged and CI passes.

## Current Discovery Result

- No concrete staging host or staging domain was found in the repository.
- No GitHub environment or deployment target is configured for this repository.
- No CI deploy job for staging was found.
- Local SSH config exposes `maxpilot-vps` and `prod-ssr` only.
- `maxpilot-vps` and `prod-ssr` are treated as production or live-like contours and must not be used as staging.
- Staging and production were not touched during RC-19 validation.

## Option A: Dedicated Staging VPS

Preferred for production-like validation.

Required properties:
- Separate host from production.
- Separate candidate/admin domains, for example `staging-candidate.recruitsmart.ru` and `staging-admin.recruitsmart.ru`, or approved alternatives.
- Separate PostgreSQL database.
- Separate Redis instance, database index, or namespace.
- Separate env files.
- No production secrets except explicitly approved sandbox or limited credentials.
- HTTPS enabled.
- nginx or equivalent proxy configured.
- Deploy user, release directory, backup path, and rollback command documented.
- Logs accessible without exposing secrets.

Acceptance criteria:
- Production services and production database are not shared.
- Deploy can run migrations explicitly and observably, or can disable them explicitly.
- Rollback can restore the previous staging release and staging DB backup.

## Option B: Isolated Staging Clone On Existing Infrastructure

Allowed only if isolation is explicit.

Required properties:
- Separate Unix user and release directory.
- Separate internal ports bound to localhost.
- Separate PostgreSQL database or schema.
- Separate Redis database index or namespace.
- Separate nginx `server_name` entries.
- No shared production env file.
- Resource limits documented so staging cannot starve production.
- Service names distinguish staging from production.

Acceptance criteria:
- Restarting staging cannot restart production services.
- Schema changes cannot affect the production DB.
- Logs and backups are separated.

## Option C: Ephemeral Docker Staging

Useful for release smoke, not sufficient for full production-like validation unless nginx and HTTPS are included.

Required properties:
- Docker Compose staging profile.
- Isolated PostgreSQL and Redis.
- Seeded test data.
- Controlled host/port exposure.
- No production secrets.
- Disposable release directory and explicit cleanup.

Acceptance criteria:
- Candidate/admin smoke can run end to end.
- External providers use sandbox or fake credentials.
- The environment is clearly marked as not production-like if nginx/HTTPS are absent.

## Required Staging Env Flags

- `ENVIRONMENT=production` or approved staging-production-like value.
- `DEBUG=false`.
- `AUTO_MIGRATE=false` unless migration is run as an explicit deploy step.
- `MIGRATION_HISTORY_RECONCILED=true` for migration-enabled staging.
- `RUN_MIGRATIONS=true` for migration-enabled staging.
- `RUN_MIGRATIONS=false` and `CODE_ONLY_DEPLOY_APPROVED=true` for code-only staging.
- Local verification and dev overrides disabled.

## Required Access

- Staging host or CI deploy target.
- Deploy user.
- Secure DB connection channel.
- Log access for app, bot, nginx/proxy, and migration runner.
- nginx/proxy config access.
- Rollback command.
- Permission to back up staging DB before migration-enabled validation.

## Pre-Staging Checklist

- CI green for the selected RC tag.
- RC tag selected and immutable.
- Migration mode selected.
- `scripts/staging_schema_compatibility.sql` ready.
- Staging DB backup path known if migrations will run.
- Smoke commands prepared.
- Rollback command prepared.

## Decision Table

| Condition | Decision |
| --- | --- |
| No staging target exists | Production remains NO-GO. |
| Staging target exists but migrations cannot be controlled | Staging NO-GO. |
| Staging target exists and migrations are disabled | Code-only staging smoke allowed. |
| Staging target exists and migration recovery is approved | Migration-enabled staging is preferred. |

## Current Blocker

Production remains NO-GO until an approved staging target exists and staging smoke is green.
