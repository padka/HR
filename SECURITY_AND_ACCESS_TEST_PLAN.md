# Security and Access Test Plan

## 1. Access Model Under Test
- Web principals: `admin`, `recruiter`.
- Candidate is not a web principal; candidate-facing API uses Telegram WebApp auth in `backend/apps/admin_api/webapp/auth.py`.
- Admin UI protection is enforced through `require_principal`, `require_admin`, scoping helpers in `backend/core/scoping.py`, and object guards in `backend/core/guards.py`.
- Recruiter access policy is intentionally `404` on foreign objects to avoid existence leaks.

## 2. Security Surfaces
- Session cookie auth for admin UI.
- Bearer token auth for admin UI.
- Optional dev/test-only bypasses: `ALLOW_LEGACY_BASIC`, `ALLOW_DEV_AUTOADMIN`.
- Telegram WebApp `initData` auth header.
- CSRF for mutating admin routes.
- Metrics and health endpoints.
- Staff chat threads, attachments, thread members, and candidate task handoff.
- File/avatar uploads.
- Export/report generation and logs containing candidate data.

## 3. Threat-Oriented Priorities

### P0
- RBAC bypass or IDOR for candidate, slot, city, attachment, or workflow objects.
- Candidate or recruiter can mutate data outside scope.
- Session/bearer auth inconsistency breaks expected protection.
- Dev bypass flags usable in production profile.
- Candidate WebApp auth can be replayed or spoofed.

### P1
- Metrics or diagnostics exposure to unauthenticated clients.
- CSRF gaps on mutating admin endpoints.
- PII leakage through logs, exports, or attachments.
- Improper proxy-trust rate limiting or IP handling.

## 4. Role and Route Matrix

| Role / actor | Surfaces to validate | Expected access |
|---|---|---|
| Unauthenticated web | `/api/*`, websocket calendar, metrics | Denied except explicitly public health probes |
| Admin | All admin UI routes and scoped data | Full access |
| Recruiter | Only own candidates/slots/cities and allowed mutations | Scoped access only, foreign object => 404 |
| Candidate WebApp user | `/api/webapp/*` for own identity only | Own booking data only |
| Candidate without valid initData | `/api/webapp/*` | Denied |

## 5. Test Matrix

### Auth and session tests
- Admin session login/logout.
- Recruiter session login/logout.
- Admin bearer token to protected API.
- Recruiter bearer token to protected API.
- Bearer token invalid signature, expired token, inactive account.
- Production profile rejects `ALLOW_LEGACY_BASIC` and `ALLOW_DEV_AUTOADMIN`.

### Authorization tests
- Recruiter requests foreign candidate detail, delete, assign, workflow action.
- Recruiter requests foreign slot list/detail/mutations.
- Recruiter requests city not linked via `recruiter_cities`.
- Recruiter accesses admin-only routers: recruiters, simulator, workflow admin routes, message templates admin flows.
- Staff chat thread member add/remove/read against foreign thread.
- Staff attachment download for foreign thread.
- Candidate WebApp tries to cancel or reschedule someone else’s booking.

### Object reference abuse tests
- Guess sequential candidate ids.
- Guess slot ids across recruiters.
- Guess city ids and reminder policy endpoints.
- Guess attachment ids in `/api/staff/attachments/{attachment_id}`.
- Guess thread ids and member ids in staff chat routes.

### CSRF tests
- POST/PATCH/PUT/DELETE without CSRF token on session-authenticated routes.
- Confirm bearer-auth requests are handled under expected CSRF policy.
- Validate avatar upload and other multipart forms enforce protection consistently.

### WebApp security tests
- Missing `auth_date`.
- Stale `auth_date`.
- Future timestamp beyond allowed skew.
- Invalid signature.
- Valid signature for one user used against another user’s booking id.

### Security header and hardening tests
- CSP/nonces on admin UI pages.
- HSTS and secure cookies in production profile.
- Rate-limit behavior with and without trusted proxy headers.
- Metrics endpoint allowlist/auth policy.

## 6. Specific Route Packs To Automate First

### P0 pack
- `/auth/login`, `/auth/token`, `/auth/logout`
- `/api/profile`
- `/api/candidates/{candidate_id}`
- `/api/candidates/{candidate_id}/actions/{action_key}`
- `/api/candidates/{candidate_id}/assign-recruiter`
- `/api/candidates/{candidate_id}/schedule-slot`
- `/api/candidates/{candidate_id}/schedule-intro-day`
- `/api/slots/{slot_id}/approve_booking`
- `/api/slots/{slot_id}/reject_booking`
- `/api/cities/{city_id}` and reminder policy endpoints
- `/api/staff/attachments/{attachment_id}`
- `/api/webapp/booking`, `/api/webapp/reschedule`, `/api/webapp/cancel`

### P1 pack
- `/api/notifications/feed`, `/api/notifications/logs`, retry/cancel endpoints
- `/api/staff/threads/*`
- `/api/bot/integration`
- `/api/message-templates/*`
- `/api/test-builder/graph*`
- `/metrics` and `/health/notifications`

## 7. PII and Auditability Checks
- Ensure candidate FIO, phone, Telegram identifiers, HH URLs, and attachment names are not emitted into logs unless intentionally redacted.
- Verify audit log records who changed candidate status, slot assignment, recruiter assignment, and intro-day scheduling.
- Check that exported or downloaded files honor scope and do not expose foreign candidate data.

## 8. Security Automation Plan

### On every PR
- Fast auth and RBAC smoke for top mutations and detail endpoints.
- WebApp auth negative tests.
- Brute force and rate-limit regression tests.
- Metrics exposure and websocket auth smoke.

### Nightly
- Full recruiter/admin route matrix.
- Attachment/thread/member access matrix.
- CSRF matrix for session-authenticated mutating routes.
- Log redaction and audit completeness checks.

### Pre-release
- Staging run against production-like proxy and cookie settings.
- Manual validation of real login and real WebApp initData flow.
- Review of secrets and feature-flag production defaults.

## 9. Expected Findings to Resolve Before Go
- Any recruiter path that returns actual foreign object data instead of `404`.
- Any mutating route working without auth or with incorrect CSRF handling.
- Any dev bypass enabled in production.
- Any attachment/export path accessible across scope boundaries.
- Any missing audit trail for slot scheduling, intro-day scheduling, or candidate status changes.
