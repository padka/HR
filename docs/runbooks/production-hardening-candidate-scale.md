# Production Hardening Candidate Scale Runbook

Scope: `candidate.recruitsmart.ru`, `admin.recruitsmart.ru`, `maxpilot-vps`.

Do not print secrets, tokens, OAuth codes, `state`, `poll_token`, database passwords, or raw env files in terminal history or reports.

## 1. Preflight Inventory

```bash
git status --short
git branch --show-current
git log -1 --oneline
systemctl status recruitsmart-maxpilot-admin-api recruitsmart-admin recruitsmart-bot nginx postgresql redis-server --no-pager
ss -tulpn
nginx -t
```

Expected external network boundary: only 80/443 are public. Postgres, Redis, admin-api, admin-ui, and n8n stay local.

## 2. Backups Before Deploy

Create a dated restricted backup directory:

```bash
sudo install -d -m 0700 /root/recruitsmart-backups/$(date -u +%Y%m%dT%H%M%SZ)
```

Database backup:

```bash
sudo -u postgres pg_dump --format=custom --file=/root/recruitsmart-backups/<stamp>/recruitsmart.dump <database_name>
```

Nginx config backup:

```bash
sudo tar --numeric-owner --xattrs -czf /root/recruitsmart-backups/<stamp>/nginx.tgz /etc/nginx
```

Systemd unit/env backup without printing contents:

```bash
sudo tar --numeric-owner --xattrs -czf /root/recruitsmart-backups/<stamp>/systemd-units.tgz \
  /etc/systemd/system/recruitsmart-maxpilot-admin-api.service \
  /etc/systemd/system/recruitsmart-admin.service \
  /etc/systemd/system/recruitsmart-bot.service
sudo find /opt/recruitsmart_maxpilot -maxdepth 1 -type f -name '.env*' -exec sudo cp --preserve=mode,ownership,timestamps {} /root/recruitsmart-backups/<stamp>/ \;
sudo chmod 0600 /root/recruitsmart-backups/<stamp>/.env*
```

## 3. Deploy Order

1. Pull or rsync the reviewed release artifact.
2. Install dependencies if the lockfiles changed.
3. Run backend checks and migrations on staging/clean DB first.
4. Build frontend and verify assets are fingerprinted under `/assets`.
5. Apply migrations in production only after backup.
6. Set `ENVIRONMENT=production`, `DEBUG=false`, no wildcard CORS, no dev auth bypass.
7. Validate nginx config with `nginx -t`.
8. Restart in order: `recruitsmart-maxpilot-admin-api`, `recruitsmart-admin`, `recruitsmart-bot` if changed, then `nginx reload`.
9. Run smoke tests below.
10. Watch logs for at least one HH sync cycle and one bot polling/notification cycle.

## 4. HH Secret Rotation

1. Revoke/replace HH Client Secret in HH developer/employer cabinet.
2. Update the secret in the server env store without echoing it.
3. Reload systemd daemon only if unit files changed.
4. Restart affected services.
5. Verify HH OAuth and API with masked logs only.

Commands:

```bash
sudo systemctl restart recruitsmart-maxpilot-admin-api recruitsmart-admin
sudo journalctl -u recruitsmart-maxpilot-admin-api -n 200 --no-pager | \
  sed -E 's/((client_secret|access_token|refresh_token|code|state|poll_token|token)=)[^&[:space:]]+/\1REDACTED/g'
```

## 5. Nginx Logs And Sensitive Query Params

Do not delete raw historical logs before backup and incident-retention decision.

Recommended sequence:

```bash
sudo install -d -m 0700 /root/recruitsmart-backups/<stamp>/nginx-raw-logs
sudo cp --preserve=mode,ownership,timestamps /var/log/nginx/access.log* /root/recruitsmart-backups/<stamp>/nginx-raw-logs/
sudo sh -c "zcat -f /var/log/nginx/access.log* | sed -E 's/((poll_token|code|state|token|access_token|refresh_token|client_secret)=)[^&[:space:]]+/\1REDACTED/g' > /root/recruitsmart-backups/<stamp>/nginx-access.sanitized.log"
```

Production nginx access format should not include raw `$request_uri` on OAuth/callback/token routes. Prefer `$uri` plus request metadata. If full URI is needed for non-sensitive routes, split locations and use a sanitized format for:

- `/apply`
- `/candidate-flow`
- `/miniapp`
- `/api/max/launch`
- OAuth callback routes
- public token/poll routes

After config change:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Verification:

```bash
sudo sh -c "tail -n 200 /var/log/nginx/access.log" | \
  grep -E 'poll_token=|code=|state=|client_secret=|access_token=|refresh_token=' && echo "FAIL" || echo "OK"
```

## 6. Smoke Tests

Candidate public:

```bash
curl -sSI https://candidate.recruitsmart.ru/apply/main
curl -sSI 'https://candidate.recruitsmart.ru/candidate-flow/start?campaign=main'
curl -sSI 'https://candidate.recruitsmart.ru/assets/<hashed-js-file>.js'
```

Expected:

- `/apply/main` redirects to `/candidate-flow/start?campaign=main`.
- Candidate HTML is `200 text/html`.
- HTML has `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, and HSTS.
- Hashed assets have `Cache-Control: public, max-age=31536000, immutable`.
- HTML/callback/token pages are not cached with immutable policy.

Backend services:

```bash
curl -sS https://candidate.recruitsmart.ru/healthz
curl -sS https://candidate.recruitsmart.ru/ready | jq .
systemctl status recruitsmart-maxpilot-admin-api recruitsmart-admin recruitsmart-bot --no-pager
journalctl -u recruitsmart-maxpilot-admin-api -n 200 --no-pager
journalctl -u recruitsmart-bot -n 200 --no-pager
```

Database integrity:

```sql
select count(*) from slots where starts_at > now() and status = 'free';
select max(created_at), status, count(*) from hh_sync_jobs group by status;
select max_user_id, count(*) from users where nullif(max_user_id, '') is not null group by max_user_id having count(*) > 1;
select telegram_id, count(*) from users where telegram_id is not null group by telegram_id having count(*) > 1;
select telegram_user_id, count(*) from users where telegram_user_id is not null group by telegram_user_id having count(*) > 1;
```

Expected:

- Future slots for active campaign are above `MIN_FUTURE_SLOTS_WARNING`, or manual availability fallback is verified.
- Identity duplicate queries return zero rows.
- `uq_users_max_user_id_nonempty` still exists.

HH sync:

- Admin `GET /api/integrations/hh/jobs` returns `summary` counts by status and recent jobs.
- Mock/staging 403 marks HH job as `forbidden`, sets connection status to `error`, and does not emit `hh.sync.worker.unhandled_failure`.
- 429 respects `Retry-After`.
- Network/5xx retries with backoff.
- Retention cleanup removes only terminal jobs older than policy while keeping recent dead/forbidden rows per connection.

Telegram:

- `/start` smoke succeeds.
- Polling does not hot-loop on `TelegramNetworkError`.
- `delete_webhook` does not drop pending updates in the hardened polling path.

## 7. Rollback

Code rollback:

```bash
git checkout <previous_release_ref>
sudo systemctl restart recruitsmart-maxpilot-admin-api recruitsmart-admin recruitsmart-bot
```

Nginx rollback:

```bash
sudo tar -xzf /root/recruitsmart-backups/<stamp>/nginx.tgz -C /
sudo nginx -t
sudo systemctl reload nginx
```

ENV rollback:

- Restore previous env file from the restricted backup.
- Do not print file contents.
- Restart affected service.

HH worker rollback:

- Roll back code only; do not delete `hh_sync_jobs`.
- `forbidden` is terminal and safe to leave for follow-up retry after reauth/permission fix.

Telegram rollback:

```bash
curl -sS "https://api.telegram.org/bot<token>/deleteWebhook?drop_pending_updates=false"
sudo systemctl restart recruitsmart-bot
```

Manual availability rollback:

- Do not delete submitted manual availability requests.
- If UI rollback hides the panel, export pending manual requests for backoffice handling first.

Migrations rollback:

- Use migration downgrade only if it is implemented and tested on staging.
- If no destructive schema changes were deployed, prefer code rollback and leave additive columns/indexes in place.

## 8. GO / NO-GO

GO requires all of:

- Future slots exist for `main` or manual availability fallback is verified end-to-end; preferred both.
- `ENVIRONMENT=production` confirmed without printing env contents.
- Candidate HTML security headers are present.
- New logs do not contain sensitive query params.
- HH 403 is controlled and does not create traceback storm.
- HH secret is rotated or the rotation window is explicitly scheduled before launch.
- Telegram bot has hardened polling or validated webhook with secret token.
- Static hashed assets are immutable cached; HTML is not dangerously cached.
- Identity duplicate checks remain zero.
- No new public ports are open.

NO-GO if any smoke fails, migration state does not match the release chain, HH secret remains known-compromised without a rotation window, or future slots/manual fallback are not available.
