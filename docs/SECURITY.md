# Security

RecruitSmart Maxpilot handles candidate identity, recruiter workflows,
verification redirects, messaging provider callbacks, and HH integration data.
Security controls must be enforced at the application boundary and at nginx.

## Production Environment Guard

Production-like public domains must not run with development settings.

Required posture:

- `ENVIRONMENT=production` for production.
- `DEBUG=false`.
- `.env.local` overrides disabled in production-like services.
- local verification disabled outside local/test.
- dev auth bypass disabled.
- public CORS origins explicitly listed, not wildcard.

The settings guard fails startup when production domains are combined with an
unsafe environment, unless an explicit non-production drill override is set.

## HTTP Headers

Candidate HTML should include:

- `Content-Security-Policy`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy`
- `Permissions-Policy`
- `Strict-Transport-Security` when HTTPS readiness for the selected host is
  confirmed

Baseline CSP policy:

```text
default-src 'self';
base-uri 'self';
object-src 'none';
frame-ancestors 'none';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:;
connect-src 'self';
form-action 'self';
upgrade-insecure-requests;
```

Broaden CSP only after a browser smoke proves which external origin is required.

## Cache Policy

- HTML shells, callbacks, and candidate pages with query-sensitive inputs must
  not be dangerously cached.
- Hashed static assets may use long immutable cache headers.
- OAuth and verification callback responses should avoid referrer leakage.

## Secret Handling

- Secrets are passed through environment or a secrets store only.
- Secrets are never committed.
- `.env` files are not release artifacts.
- Reports must mask values and may mention key names only for diagnostics.
- HH Client Secret rotation must be performed through a secure channel.
- Telegram bot credentials must not appear in logs, shell history, docs, or CI
  output.

## Log Redaction

Logs must redact sensitive query/body/header keys before writing:

- `poll_token`
- `code`
- `state`
- `token`
- `access_token`
- `refresh_token`
- `client_secret`
- authorization headers

Verification requires sending safe dummy values and confirming the new logs
contain masked values only.

## OAuth And Callback Boundaries

OAuth callback and provider handoff routes are public ingress points. They must:

- return safe errors without stack traces;
- avoid logging raw callback parameters;
- use short-lived or hashed references where possible;
- preserve existing public API contracts during hardening.

## Public Port Policy

Production may expose only 80/443 externally. PostgreSQL, Redis, admin API
internals, n8n, and service-local ports must remain local/private.

## Required Security Smoke

```bash
curl -sSI https://candidate.recruitsmart.ru/apply/main
curl -sSI 'https://candidate.recruitsmart.ru/candidate-flow/start?campaign=main'
ss -tulpn
```

Do not paste sensitive command output into reports. Mask host-specific process
details when they include credentials or local secret paths.
