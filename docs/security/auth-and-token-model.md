# Auth And Token Model

## Purpose
Описать модель аутентификации и токенов RecruitSmart Admin: session cookie, bearer JWT, CSRF token, candidate portal token, MAX invite/deeplink token, HH OAuth state, webhook secrets и правила их использования.

## Owner
Security / Backend Platform

## Status
Canonical

## Last Reviewed
2026-03-25

## Source Paths
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/security.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/auth.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/ai.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/hh_integration.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/core/auth.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py`
- `/Users/mikhail/Projects/recruitsmart_admin/backend/domain/hh_integration/oauth.py`
- `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/client.ts`
- `/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/api/candidate.ts`

## Related Diagrams
- `docs/security/trust-boundaries.md`
- `docs/runbooks/auth-session-incident.md`
- `docs/runbooks/portal-max-deeplink-failure.md`

## Change Policy
- Любая смена auth/token semantics требует обновления этого документа, regression tests и incident runbooks.
- Token TTL, cookie flags и CSRF bypass rules не менять без отдельного review.
- Local dev allowances must remain host-scoped and environment-scoped.

## Token Inventory

| Token / secret | Where issued | Where used | TTL / scope | Storage |
| --- | --- | --- | --- | --- |
| Session cookie | `SessionMiddleware` | admin/recruiter browser sessions | cookie lifetime, server-side session payload | browser cookie |
| Bearer JWT | `/auth/token` | API clients / browser fallback | `access_token_ttl_hours` | client header |
| CSRF token | `/api/csrf` | state-changing admin requests | session-bound | browser memory / header |
| Candidate portal token | `sign_candidate_portal_token()` | `/api/candidate/session/exchange` and portal requests | `candidate_portal_token_ttl_seconds`, bound to `candidate_id + journey_session_id + session_version` | query param / header |
| Candidate invite token | `generate_candidate_invite_token()` / `issue_candidate_invite_token()` | MAX deep link generation and linking | server-generated, rotated per candidate/channel, status-tracked in DB | query param / DB token table |
| MAX mini-app token | `sign_candidate_portal_token(... entry_channel="max")` | MAX mini app entry | portal TTL, includes `journey_session_id + session_version` | startapp token |
| HH OAuth state | `sign_hh_oauth_state()` | OAuth callback correlation | `hh_oauth_state_ttl_seconds` | query param |
| HH webhook key | `webhook_url_key` | HH webhook receiver path | long-lived secret | path segment |
| Webhook secret | `max_webhook_secret`, `hh_webhook_secret` | external webhook subscription verification | provider-defined | env secret |

## Primary Auth Flows

```mermaid
sequenceDiagram
  autonumber
  participant B as Browser
  participant A as Admin UI
  participant S as Session/JWT/Auth
  participant D as DB

  B->>A: POST /auth/login
  A->>D: verify account / recruiter existence
  A->>S: set session payload {type,id}
  A-->>B: 303 redirect + session cookie

  B->>A: GET /api/... with session cookie
  A->>S: resolve principal from session or bearer JWT
  A-->>B: scoped response
```

```mermaid
sequenceDiagram
  autonumber
  participant C as Candidate browser / MAX mini app
  participant P as /api/candidate
  participant D as DB

  C->>P: POST /session/exchange {signed portal token}
  P->>D: validate token signature + candidate_id + journey_session_id + session_version
  P->>D: create / touch portal session
  P-->>C: journey payload + server session

  C->>P: GET/POST portal API with cookie or x-candidate-portal-token
  P->>P: validate portal session or header token
  P->>D: verify active journey and matching session_version
  P->>D: persist candidate state
  P-->>C: refreshed journey
```

## Admin Session Model

- Admin and recruiter browser auth are resolved in `backend.apps.admin_ui.security`.
- Session payload stores only principal identity, not reusable permissions cache.
- `AuthAccount` is the DB-backed account path; configured admin username/password remains an explicit bootstrap path.
- JWT access tokens are signed with `session_secret`; bearer JWT is acceptable for API clients, but browser local sessions may take precedence on localhost when both exist.
- CSRF protection is enforced for state-changing admin requests via middleware + `require_csrf_token()`.

## Candidate Portal Model

- Portal token is a signed, time-limited token built with `itsdangerous.URLSafeTimedSerializer`.
- Portal token payload contains `candidate_id`, `entry_channel`, `journey_session_id` and `session_version`.
- Portal session is server-managed and lives under `candidate_portal` session key.
- Requests can recover from missing browser cookies by sending the portal token in one of:
  `x-candidate-portal-token`, `x-candidate-portal-access-token`, `x-candidate-portal-session-token`.
- Header-token recovery is valid only when the referenced journey session still exists, remains `active`, and `session_version` matches the current DB value.
- `relink`, invite rotation, explicit security recovery and similar ownership-changing actions bump `session_version` and invalidate stale browser/header sessions.
- Portal responses must never be treated as admin/recruiter auth.

## MAX Model

- Admin-generated MAX link uses an invite token plus an optional mini-app token.
- Deep link format is provider-specific and uses `start=...` or `startapp=...`.
- Raw invite tokens are treated as secrets after issuance: recruiter-facing `channel-health` surfaces expose only invite metadata, and audit log entries store invite ids / rotation metadata instead of token values.
- MAX runtime deduplicates webhook updates before processing to prevent duplicate side effects.
- Only one active MAX invite is canonical per candidate. New admin rotation supersedes previous active invite instead of creating parallel active links.
- Reuse of the same invite by the same `max_user_id` is idempotent. Reuse by another `max_user_id` is treated as conflict and must not create duplicate linking side effects.
- `messenger_platform` is no longer silently overwritten on every MAX entry. Preferred channel changes only when candidate has no linked channel yet or an explicit operator action rotates ownership.
- Public MAX placeholder onboarding remains feature-flagged and is non-default for production. Invite-based linking is the canonical production path.

## HH Model

- HH OAuth authorize URL is built from signed state that includes principal and return target.
- Callback is valid only when state is intact and principal matches the authenticated admin.
- HH access and refresh tokens are encrypted at rest.
- HH webhook receiver is authenticated by the URL key; logs must not expose it.

## CSRF Rules

- CSRF is required for state-changing admin UI requests.
- SPA fetch layer first requests `/api/csrf`, then sends `x-csrf-token`.
- Candidate portal API intentionally bypasses CSRF because its auth surface is the signed portal token and portal session, not the admin session.
- Dev/test host allowlisting exists only for local iteration and must not widen production trust.

## Secret Handling Rules

- Store long-lived secrets in environment/secret manager only.
- Rotate secrets if exposure is suspected: `SESSION_SECRET`, `BOT_TOKEN`, `BOT_CALLBACK_SECRET`, `hh_client_secret`, `max_bot_token`, webhook secrets.
- Do not echo request bodies or headers containing tokens into debug logs.
- Use redacted identifiers and request IDs for supportability.

## Security Regression Areas

- Session fixation and cross-principal session reuse.
- JWT acceptance for the wrong principal type or stale account.
- CSRF header bypass on admin mutations.
- Candidate portal token replay, stale `session_version` reuse, or accidental reuse as admin auth.
- MAX invite token reuse, conflict linking, superseded invite acceptance, or leakage in logs.
- HH OAuth callback principal mismatch or replay.
- Webhook secret exposure and webhook replay handling.
