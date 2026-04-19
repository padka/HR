# Supported Channels

## Purpose
Каноническая матрица channel/runtime surface в RecruitSmart. Документ разделяет:
- текущий supported runtime;
- bounded controlled-pilot surfaces, которые уже смонтированы, но default-off и не являются production rollout;
- legacy or historical implementation, которая больше не является runtime promise;
- future target state, который сохраняется как продуктовая цель, но не включён в текущий runtime.

## Owner
Platform Engineering

## Status
Canonical

## Last Reviewed
2026-04-19

## Source Paths
- `backend/apps/admin_ui/app.py`
- `backend/apps/admin_api/main.py`
- `backend/apps/admin_api/max_launch.py`
- `backend/apps/admin_api/max_miniapp.py`
- `backend/apps/admin_api/candidate_access/router.py`
- `backend/apps/admin_ui/services/max_rollout.py`
- `backend/apps/admin_ui/routers/system.py`
- `backend/apps/admin_ui/routers/hh_integration.py`
- `backend/apps/admin_api/hh_sync.py`
- `backend/core/settings.py`
- `docker-compose.yml`
- `max_bot.py`
- `frontend/app/src/app/main.tsx`
- `frontend/app/openapi.json`

## Runtime Matrix

| Channel / surface | Status | Runtime / entrypoint | Primary env / config | Primary HTTP/API surface | Notes |
| --- | --- | --- | --- | --- | --- |
| Admin SPA | Supported | `backend.apps.admin_ui.app` + `frontend/dist` | `DATABASE_URL`, `REDIS_URL`, `SESSION_SECRET`, `ADMIN_USER`, `ADMIN_PASSWORD`, `ALLOW_DESTRUCTIVE_ADMIN_ACTIONS`, `METRICS_ENABLED`, `METRICS_IP_ALLOWLIST` | `/app/*`, `/auth/*`, admin UI `/api/*`, public `/health`, `/ready`, `/healthz`, protected `/metrics`, protected `/metrics/notifications`, operator-only `/health/bot`, operator-only `/health/notifications` | Main recruiter/admin browser runtime. |
| Telegram bot runtime | Supported | `python bot.py` / `backend.apps.bot.app` | `BOT_ENABLED`, `BOT_TOKEN`, `BOT_CALLBACK_SECRET`, `BOT_INTEGRATION_ENABLED`, `BOT_AUTOSTART`, `BOT_NOTIFICATION_RUNTIME_ENABLED` | Operator visibility through admin UI system surfaces and protected health/metrics | Telegram remains the only supported live messaging runtime today. |
| Telegram Mini App / recruiter webapp | Supported | `backend.apps.admin_api.main` | `SESSION_SECRET`, `BOT_CALLBACK_SECRET`, `DATABASE_URL`, `REDIS_URL` | `/api/webapp/*`, `/api/webapp/recruiter/*` | Separate service boundary from `admin_ui`. |
| HH integration | Supported | `backend.apps.admin_ui.routers.hh_integration` | `HH_INTEGRATION_ENABLED`, `HH_CLIENT_ID`, `HH_CLIENT_SECRET`, `HH_REDIRECT_URI`, `HH_WEBHOOK_*` | `/api/integrations/hh/*` | Admin/operator HH control plane. |
| n8n HH sync callbacks | Supported external automation layer | `backend.apps.admin_api.hh_sync` | `HH_WEBHOOK_SECRET` | `/api/hh-sync/callback`, `/api/hh-sync/resolve-callback` | External automation callback boundary, protected by webhook secret. |
| Bounded MAX launch/auth + webhook shell | Guarded pilot boundary | `backend.apps.admin_api.main` + `backend.apps.admin_api.max_launch` | `MAX_ADAPTER_ENABLED`, `MAX_BOT_TOKEN`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_BOT_API_SECRET`, `MAX_WEBHOOK_URL`, `MAX_INIT_DATA_MAX_AGE_SECONDS` | `/api/max/launch`, `/api/max/webhook` | Mounted bounded bootstrap/auth and webhook ingress. Fail-closed when disabled or unconfigured. `MAX_BOT_ENABLED` is a compatibility alias, not the canonical switch; `MAX_WEBHOOK_SECRET` is a legacy secret alias. |
| Bounded MAX candidate mini-app surface | Guarded pilot boundary | `backend.apps.admin_api.main` + `backend.apps.admin_api.max_miniapp` + `frontend/app` | `MAX_ADAPTER_ENABLED`, `MAX_BOT_TOKEN`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_BOT_API_SECRET`, `MAX_INIT_DATA_MAX_AGE_SECONDS` | `/miniapp`, `/api/candidate-access/*` | Mounted and implemented for bounded controlled pilot. Global entry now starts a hidden-draft intake flow, while personal `start_param` invites and contact recovery remain bounded resume paths. Uses shared candidate journey and shared `candidate_access` contracts. Default-off and fail-closed when disabled or unconfigured. Not a production MAX rollout. |
| MAX bounded rollout surface | Guarded operator pilot boundary | `backend.apps.admin_ui.app` + `backend.apps.admin_ui.services.max_rollout` | `MAX_INVITE_ROLLOUT_ENABLED`, `MAX_ADAPTER_ENABLED`, `MAX_BOT_TOKEN`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL` | `POST /api/candidates/{candidate_id}/max-launch-invite`, `POST /api/candidates/{candidate_id}/max-launch-invite/revoke` | Protected recruiter/operator control surface for preview, issue/send, rotate/reuse, revoke, and invite/launch observability. Preview/send remain distinct and default-off. No analytics cutover or production channel activation is implied. |
| Legacy candidate portal implementation | Unsupported | no live runtime | historical `candidate_portal_*` settings are not part of the supported runtime contract | `/candidate*` returns `410 Gone`; `/api/candidate/*` is absent from live/tracked OpenAPI | Legacy implementation removed from supported runtime. |
| Future standalone candidate web flow | Target state | reserved future surface only | future product/runtime decision required | no mounted route or advertised API today | Keep conceptually separate from the removed legacy portal implementation. |
| Historical MAX runtime | Unsupported | no default runtime; `max_bot.py` retained only as disabled historical stub | historical `MAX_*` settings are not part of supported default runtime | no supported production runtime surface; compose keeps `max_bot` behind `profiles: [max]` only | Standard compose/runtime must not depend on this path. |
| Future full MAX runtime / channel rollout | Target state | reserved future surface only | future product/runtime/security decision required | no production MAX runtime contract today | Keep separate from the already mounted bounded controlled-pilot surfaces above. |
| SMS / voice fallback | Required integration target | not implemented today | future provider/runtime decision required | none | Product target only; no current runtime promise. |

## Supported Surface Rules
- `GET /healthz`, `GET /ready`, and `GET /health` may stay public because they are shallow probes.
- `GET /health/bot` and `GET /health/notifications` are operator-only diagnostic surfaces and must not be treated as public health probes.
- `/metrics` and `/metrics/notifications` must stay protected by auth and/or deployment boundary allowlist.
- OpenAPI truth is generated from live `admin_ui` and `admin_api` app factories, not hand-maintained DTO snapshots.
- `/api/max/launch`, `/api/max/webhook`, `/miniapp`, and `/api/candidate-access/*` are bounded controlled-pilot surfaces, not a production MAX runtime activation.
- `/miniapp` is MAX-only at bootstrap time: outside the MAX client it must fail closed with explicit guidance instead of attempting candidate launch without signed `initData`.
- The primary global MAX entry semantics are now intake-first: first launch creates a hidden draft candidate, opens shared Test1 immediately, and delays operator-visible CRM activation until intake completion.
- `admin_ui` MAX rollout controls are pilot-only operator surfaces. They do not imply browser rollout, SMS rollout, analytics cutover, or full MAX runtime activation.
- `MAX_ADAPTER_ENABLED=false` and `MAX_INVITE_ROLLOUT_ENABLED=false` remain the safe baseline for controlled-pilot readiness.
- Telegram remains the only supported live messaging runtime today even though the bounded MAX pilot surface is implemented.

## Cleanup Recorded Here

### Removed from tracked/live API truth
- `/api/candidate/*` paths are removed from tracked OpenAPI and are no longer advertised as live runtime contract.
- Legacy mutating `GET /candidates/{candidate_id}/resend-test2` is excluded from schema and returns `410 Gone`.
- Historical MAX helper/runtime routes are not part of the supported admin UI contract.

### Retained only as historical or target-state reference
- `docker-compose.yml` still contains `max_bot`, but only behind `profiles: [max]`.
- `max_bot.py` is retained only as an explicit disabled stub.
- Historical candidate route files under `frontend/app/src/app/routes/candidate/*` are not mounted in `frontend/app/src/app/main.tsx`.
- Product/architecture target docs may describe future standalone candidate web flow, future full MAX rollout, or SMS/voice fallback, but those notes must not be read as current runtime availability.

### Canonical docs aligned to this matrix
- `README.md`
- `docs/architecture/overview.md`
- `docs/architecture/runtime-topology.md`
- `docs/architecture/core-workflows.md`
- `docs/frontend/route-map.md`
- `docs/frontend/state-flows.md`
- `docs/frontend/screen-inventory.md`
- `docs/security/trust-boundaries.md`
- `docs/qa/critical-flow-catalog.md`
- `docs/qa/master-test-plan.md`
- `docs/qa/release-gate-v2.md`
