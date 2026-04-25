# Architecture

## Runtime Components

| Component | Primary path | Responsibility |
| --- | --- | --- |
| Admin UI backend | `backend/apps/admin_ui/app.py` | FastAPI admin app, SPA host, auth/session/CSRF boundary, admin APIs. |
| Public/admin API | `backend/apps/admin_api/main.py` | Candidate-access APIs, MAX launch/webhook, HH callback boundary. |
| Bot runtime | `backend/apps/bot/app.py`, `bot.py` | Telegram bot runtime, polling, messaging flows. |
| Frontend SPA | `frontend/app` | React admin UI and bounded mini-app surfaces. |
| Built frontend | `frontend/dist` | Static bundle served by backend/nginx. |
| Domain layer | `backend/domain` | Candidate, slot, HH, scheduling, messaging, and repository logic. |
| Migrations | `backend/migrations`, `scripts/run_migrations.py` | Schema evolution and migration runner. |

## Storage And Services

- PostgreSQL is the primary system of record.
- Redis is used for notification broker/cache scenarios where configured.
- nginx is the public edge for candidate/admin domains in production.
- systemd or Docker Compose may manage runtime services depending on contour.

## Request Flow

Candidate public flow:
1. Candidate opens campaign route.
2. Edge redirects or serves candidate shell.
3. Public campaign API returns active providers.
4. Verification start API returns provider-specific start or authorize payload.
5. Candidate-access APIs resolve session and journey state.
6. Candidate books a slot or submits manual availability.

Admin flow:
1. Recruiter/admin authenticates to the admin UI.
2. SPA calls admin APIs with session auth and CSRF for state-changing requests.
3. Backend enforces principal scoping and writes domain state.
4. Notifications, HH sync, and dashboard state update through backend services.

Provider callback flow:
1. Provider redirects or posts to a callback/webhook endpoint.
2. Backend validates provider proof or expected callback state.
3. Sensitive callback query keys are redacted from logs.
4. Candidate or integration state is updated through shared domain services.

## Auth And Callback Boundaries

- Admin UI uses server-side auth/session handling and CSRF protection.
- Candidate-access sessions are server issued and validated.
- Telegram/MAX provider identity is validated server-side.
- HH OAuth/API errors are classified and handled without exposing secrets.
- Public error responses must be safe and must not include PII or tracebacks.

## Network Boundary

Production should expose only HTTP/HTTPS externally:
- public ports: 80 and 443;
- PostgreSQL, Redis, admin-api internals, and admin UI internals must remain local/private;
- new public ports require an explicit architecture and security review.

## Environment Differences

Local:
- may use `.env.local`;
- may auto-run dev migrations when explicitly enabled;
- may use local/fake providers.

Staging:
- must be production-like or explicitly marked code-only;
- must disable dev overrides and local verification;
- must select migration mode explicitly;
- must have isolated DB/Redis/secrets from production.

Production:
- `ENVIRONMENT=production`;
- `DEBUG=false`;
- no `.env.local` override;
- migrations only after backup and reconciliation;
- secrets rotated through secure channels only;
- no raw sensitive parameters in logs.
