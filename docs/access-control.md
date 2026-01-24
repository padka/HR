# Access Control – RecruitSmart (web)

## Principal model
- `principal_type`: `admin` | `recruiter`
- `principal_id`: PK of corresponding entity (`admins.id` or `recruiters.id`)
- Stored in the session cookie payload only as `{principal_type, principal_id}`; derived role is resolved on each request (no long-lived role caching).
- Candidate is **never** a web principal; interacts only via Telegram.

## Auth accounts
- Table `auth_accounts` (to be added):
  - `id`, `username` (unique), `password_hash`, `principal_type` enum(`admin`,`recruiter`), `principal_id` (int FK-like), `is_active`, `created_at`, `updated_at`.
- Login endpoint verifies credentials, then writes `{principal_type, principal_id}` into the signed session cookie.
- Dependencies/guards:
  - `get_current_principal()` → returns typed principal (`Admin` or `Recruiter`) or 401.
  - `require_admin()`, `require_principal()` helpers.

## Scoping rules (server-side only)
- Candidates: `users.responsible_recruiter_id = current_recruiter.id`.
- Slots: `slots.recruiter_id = current_recruiter.id`.
- Cities: join via `recruiter_cities` M2M (ACL source of truth). `responsible_recruiter_id` is **not** ACL.
- Dashboard/KPI: computed from the same scoped sets (candidates, slots, cities).
- Admin: no scoping (sees all).
- Error policy: recruiter receives **404** when requesting an object outside scope (avoid existence leaks); admin may get 403 only where explicitly required.

## Scoping module (to implement)
- `backend/core/scoping.py`:
  - `scope_candidates(query, principal)`
  - `scope_slots(query, principal)`
  - `scope_cities(query, principal)`
  - Applied to **all** list/detail/search/bulk endpoints; no manual `where` in routers.

## Endpoints/areas requiring scoping
- Admin UI (FastAPI):
  - Candidates: list/search/bulk/detail.
  - Slots: list/calendar/overlap/approve/reschedule/detail.
  - Cities: list/detail.
  - Dashboard aggregates.

## City ACL decision
- Use **M2M `recruiter_cities`** as the authoritative ACL.
- `responsible_recruiter_id` remains metadata, not used for access checks.

## UI notes
- Admin UI remains full-access.
- Recruiter sees only scoped data; menu shows “Мои встречи/кандидаты/нагрузка” but relies on server scoping (no client-side protection).

## Error & audit
- Out-of-scope access by recruiter → 404 and should be logged (audit trail).

