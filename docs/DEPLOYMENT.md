# Deployment

Deployment is gated by CI, migration reconciliation, staging validation,
production preflight, and production smoke. RC-19 is application-code frozen and
CI-green. Production remains NO-GO until the remaining runtime gates pass.

## CI Process

Required CI gates:

- backend full pytest suite;
- Python matrix;
- frontend lint, typecheck, tests, and build;
- OpenAPI drift check;
- contour preflight for maxpilot/admin;
- py_compile;
- critical Ruff `F,E9` gate on touched files;
- artifact build.

Full Ruff remains baseline-red by documented waiver. It must not be reported as
green until the baseline is paid down.

## Release Tags

RC tag format:

```text
rc/hardening-candidate-scale-YYYYMMDD-N
```

Final tag format:

```text
vYYYY.MM.DD-hardening-candidate-scale
```

Tags must point to clean Git refs. Dirty worktree release artifacts are
forbidden.

## Staging Deploy

No concrete staging target is currently available. See
[docs/STAGING_TARGET_REQUIREMENTS.md](/Users/mikhail/Projects/recruitsmart_admin/docs/STAGING_TARGET_REQUIREMENTS.md).

Preferred staging mode after target creation:

```bash
MIGRATION_HISTORY_RECONCILED=true
RUN_MIGRATIONS=true
AUTO_MIGRATE=false
```

Code-only fallback:

```bash
RUN_MIGRATIONS=false
CODE_ONLY_DEPLOY_APPROVED=true
AUTO_MIGRATE=false
```

Code-only staging smoke is useful but is not a substitute for migration-enabled
validation when schema changes must be exercised.

## Production Preflight

Production preflight must capture:

- current deployed ref;
- service statuses;
- `ss -tulpn`;
- disk and memory;
- `nginx -t`;
- DB backup;
- nginx/systemd/env backups without printing secret values;
- readonly DB checks;
- HH secret rotation readiness;
- rollback commands.

## Production Rollout

Production rollout preconditions:

- CI green on selected release ref;
- staging smoke green;
- migration path validated;
- production backups complete;
- HH secret rotation path ready;
- rollback ready.

Rollout order:

1. Announce change window internally.
2. Deploy exact release ref or final tag.
3. Run migrations only when reconciled and backed up.
4. Apply production env flags.
5. Apply rotated HH secret.
6. Apply nginx headers/cache/log config.
7. Run `nginx -t`.
8. Restart app services and reload nginx.
9. Run production smoke.

## Production Smoke

Smoke must verify:

- candidate redirect and HTML shell;
- public campaign `main`;
- Telegram/MAX/HH verification starts;
- invalid public token safe 404;
- slots or manual availability fallback;
- security headers;
- HTML and asset cache policy;
- no raw sensitive query values in new logs;
- identity duplicate counts remain zero;
- HH and Telegram stability;
- no new public ports.

## Branch Cleanup

Do not delete release branches until:

- production smoke is green;
- main contains the release;
- final production tag exists;
- deployed ref and rollback ref are recorded;
- safety artifacts are archived or explicitly retained.
