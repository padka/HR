# Operations Runbook

This runbook is for staging and production operators. It is intentionally
command-oriented and assumes secrets are supplied through approved channels.

## Service Status

```bash
systemctl status recruitsmart-maxpilot-admin-api --no-pager
systemctl status recruitsmart-admin --no-pager
systemctl status recruitsmart-bot --no-pager
systemctl status nginx --no-pager
systemctl status postgresql --no-pager
systemctl status redis-server --no-pager
```

Network and resource checks:

```bash
ss -tulpn
df -h
free -m
nginx -t
```

External production ports must remain limited to 80/443.

## Restart Order

1. Confirm DB and config backups exist.
2. Start/restart backend/admin API.
3. Start/restart admin frontend service if separate.
4. Start/restart bot if bot code or env changed.
5. Run `nginx -t`.
6. Reload nginx.
7. Run smoke checks.

Do not restart PostgreSQL or Redis unless the incident explicitly requires it.

## Backups

Database backup:

```bash
pg_dump "$DATABASE_URL" --format=custom --file "$BACKUP_FILE"
```

Config backup targets:

- nginx site configs;
- systemd unit files;
- environment files, copied without printing contents;
- current release directory or deployed git ref.

Record backup paths in the release report.

## Rollback

Rollback requires:

- previous release ref;
- DB backup path;
- env/config backup path;
- nginx backup path;
- service restart commands.

Runtime rollback:

```bash
git checkout "$ROLLBACK_REF"
systemctl restart recruitsmart-maxpilot-admin-api
systemctl restart recruitsmart-bot
nginx -t
systemctl reload nginx
```

Restore database only when the failed rollout mutated schema/data and the
incident lead approves restore over compensation.

## Smoke Commands

Candidate routing:

```bash
curl -sSI https://candidate.recruitsmart.ru/apply/main
curl -sSI 'https://candidate.recruitsmart.ru/candidate-flow/start?campaign=main'
```

Static asset cache:

```bash
curl -sSI 'https://candidate.recruitsmart.ru/assets/<hashed-file>.js'
```

OpenAPI and public APIs should be checked with safe synthetic inputs only. Do
not paste sensitive provider responses into reports.

## DB Integrity Checks

Run readonly SQL before and after production rollout:

```sql
SELECT COUNT(*) FROM (
  SELECT max_user_id
  FROM users
  WHERE NULLIF(BTRIM(max_user_id), '') IS NOT NULL
  GROUP BY max_user_id
  HAVING COUNT(*) > 1
) duplicate_groups;

SELECT COUNT(*) FROM (
  SELECT telegram_id
  FROM users
  WHERE telegram_id IS NOT NULL
  GROUP BY telegram_id
  HAVING COUNT(*) > 1
) duplicate_groups;

SELECT COUNT(*) FROM (
  SELECT telegram_user_id
  FROM users
  WHERE telegram_user_id IS NOT NULL
  GROUP BY telegram_user_id
  HAVING COUNT(*) > 1
) duplicate_groups;
```

Expected result for each query: `0`.

## No-Slots Incident Response

If active campaign `main` has zero future available slots:

- verify manual availability fallback is enabled and saving requests;
- notify recruiter/backoffice owner;
- bulk-create future slots only with the approved dry-run capable command;
- do not manually edit slot rows without a backup and audit note.

## HH Sync Incident Response

For HH 401/403/429/network failures:

- verify the job summary and last successful sync timestamp;
- treat 403 as permission/reauth action, not a hot retry loop;
- rotate HH Client Secret if compromise is suspected or confirmed;
- inspect logs only after redaction is verified.

## Telegram Polling Incident Response

For polling timeouts:

- verify last successful update timestamp;
- check backoff is bounded and not hot-looping;
- verify pending updates were not dropped;
- do not switch to webhook without secret-token validation and nginx path
  hardening.

## Log Redaction Verification

Use safe dummy values only. Confirm new app and nginx logs contain masked values
for sensitive key names and no raw dummy values.
