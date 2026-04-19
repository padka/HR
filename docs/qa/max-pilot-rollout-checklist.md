# MAX Controlled Pilot Rollout Checklist

## Header
- Purpose: controlled-pilot runbook for the bounded MAX launch/auth shell and operator rollout surface.
- Owner: Release Engineering / QA / Backend on-call
- Status: Canonical, pilot-only
- Last Reviewed: 2026-04-18
- Source Paths: `backend/core/settings.py`, `backend/apps/admin_api/main.py`, `backend/apps/admin_api/max_launch.py`, `backend/apps/admin_api/max_webhook.py`, `backend/apps/admin_ui/routers/system.py`, `backend/apps/admin_ui/services/max_runtime.py`, `backend/apps/admin_ui/services/max_rollout.py`, `backend/apps/admin_ui/routers/api_misc.py`, `docs/architecture/supported_channels.md`, `docs/qa/release-gate-v2.md`

## Scope
- In scope: bounded MAX invite rollout, MAX launch/auth shell, adapter health, operator smoke, rollback, support notes.
- Out of scope: full MAX production runtime, browser rollout, SMS rollout, analytics cutover, legacy MAX restoration.
- Current runtime promise: fail-closed unless the MAX adapter shell is explicitly enabled and configured.

## Environment Inventory

| Variable | Required for | Live code use | Default / note |
| --- | --- | --- | --- |
| `MAX_INVITE_ROLLOUT_ENABLED` | protected operator invite actions | `admin_ui` rollout gate | default `false`; safe baseline is `false` |
| `MAX_ADAPTER_ENABLED` | launch/auth shell and send path | `settings`, `admin_api`, `messenger/bootstrap`, `channel_state` | default `false`; `MAX_BOT_ENABLED` is a compatibility alias only |
| `MAX_BOT_TOKEN` | initData validation, adapter bootstrap, send auth | `settings`, `/api/max/launch`, rollout send | empty by default; required before real launch/send |
| `MAX_PUBLIC_BOT_NAME` | adapter/bootstrap metadata | `settings`, runtime snapshots | optional; used for runtime description and adapter bootstrap |
| `MAX_MINIAPP_URL` | adapter bootstrap and open-link capability | `settings`, `/health/max`, rollout payloads | optional; if present it is used for open-link affordances |
| `MAX_BOT_API_SECRET` | MAX webhook ingress auth | `settings`, `X-Max-Bot-Api-Secret` check on `/api/max/webhook` | canonical env for live webhook ingress; `MAX_WEBHOOK_SECRET` remains a legacy fallback |
| `MAX_WEBHOOK_URL` | environment inventory only | stored in `settings` | currently not consumed by live code paths |
| `MAX_INIT_DATA_MAX_AGE_SECONDS` | launch/auth freshness window | `/api/max/launch` and candidate access auth | default `86400`, minimum `60` |

## MAX Partner Panel Requirement
- The candidate-facing mini-app entry must be the system button configured in MAX Partner Platform, not a chat-level deep-link button.
- Configure it in `business.max.ru`:
  1. Open the organization profile.
  2. Go to `Чат-боты -> Чат-бот и мини-приложение -> Настроить`.
  3. Set the mini-app URL to the bounded pilot shell, for example `https://max.recruitsmart.ru/miniapp`.
  4. Choose the system button type (`Открыть`, `Старт`, `Играть`, or no label) and save.
- MAX docs state that after linking the mini-app, a visible launch button appears in the bot chat and deep links of the form `https://max.ru/<botName>?startapp=<payload>` should open the mini-app inside MAX instead of bouncing the user back to bot-start. Sources:
  - [MAX help: mini-app setup and button configuration](https://dev.max.ru/help/miniapps)
  - [MAX docs: adding the mini-app and `startapp` deep links](https://dev.max.ru/docs/webapps/introduction)
- Do not rely on a chat message button as the primary mini-app entry during controlled pilot. The bot welcome text should refer the candidate to the system mini-app button in the chat header.

## Preflight
- Confirm the pilot is still bounded and default-off.
- Confirm the deployment has the current MAX env set and no stale `MAX_BOT_ENABLED` override is masking `MAX_ADAPTER_ENABLED`.
- Confirm admin auth, CSRF, and operator access for `/health/max`, `/health/max/sync`, `/api/system/messenger-health`, and candidate rollout actions.
- Confirm the provider secret/header contract is known: incoming webhook auth uses `X-Max-Bot-Api-Secret`.
- Confirm there is a rollback owner and an external provider contact before the pilot is opened.
- Confirm no one expects `MAX_WEBHOOK_URL` to be enforced by the app; it is inventory only today.
- Confirm the mini-app URL is configured in MAX Partner Platform and that the system launch button is visible in the bot chat before inviting pilot candidates.

## Enable Order
1. Set `MAX_BOT_TOKEN`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_BOT_API_SECRET`, and `MAX_INIT_DATA_MAX_AGE_SECONDS` first.
2. Keep `MAX_INVITE_ROLLOUT_ENABLED=false` and `MAX_ADAPTER_ENABLED=false` while validating config and operator access.
3. Verify `GET /health/max` and `GET /api/system/messenger-health` as an admin; the runtime should still fail closed at this stage.
4. Enable `MAX_ADAPTER_ENABLED=true` only after launch/auth smoke is ready.
5. Enable `MAX_INVITE_ROLLOUT_ENABLED=true` only after adapter health and operator copy/preview are verified.
6. If `MAX_BOT_ENABLED` exists in the environment, remove it or keep it aligned with `MAX_ADAPTER_ENABLED`; do not treat it as the canonical switch.
7. If only `MAX_WEBHOOK_SECRET` exists in the environment, keep it aligned with `MAX_BOT_API_SECRET` until the legacy alias is retired.

## Smoke
- `GET /health/max` as admin: verify runtime snapshot exposes the configured env and does not claim a live runtime before the adapter is enabled.
- `POST /health/max/sync` as admin with CSRF: verify sync returns profile/subscription data when real provider credentials are present.
- `GET /api/system/messenger-health` as admin: verify MAX channel health is readable.
- `POST /api/max/launch` with valid signed `init_data`: verify fail-closed behavior when disabled/unconfigured and successful shared-session bootstrap when enabled.
- `POST /api/max/launch` with valid signed `init_data` and no `start_param`: verify first launch creates a hidden draft candidate, returns `binding.status=bound`, and issues a bounded candidate-access session without exposing the draft in operator CRM lists.
- `POST /api/candidate-access/contact` with `X-Max-Init-Data`: verify bounded contact recovery still works as a legacy/manual path, but is not the primary global entry flow.
- Complete shared Test1 from `/miniapp`: verify `fio` and `city` sync back into the hidden draft candidate profile before activation.
- If no slots are available, `POST /api/candidate-access/manual-availability`: verify note/window persistence, recruiter notification, `waiting_slot` state, and draft activation.
- Candidate rollout preview: verify `POST /api/candidates/{candidate_id}/max-launch-invite` returns preview-only state when adapter is disabled and a real send state only when the adapter is enabled and token is present.
- Candidate rollout revoke: verify `POST /api/candidates/{candidate_id}/max-launch-invite/revoke` clears active invite state for the pilot cohort.
- Authenticated browser proof: verify candidates list visibility plus candidate detail MAX card, preview modal, result modal, disabled states, and operator wording. If Computer Use is unavailable, capture browser automation screenshots and record the limitation explicitly instead of claiming full visual parity.
- Webhook ingress: verify `/api/max/webhook` rejects requests without `X-Max-Bot-Api-Secret` and accepts the known-good secret only.
- If provider creds are missing, stop after the fail-closed checks and record an external blocker; do not simulate a successful provider smoke.

## Rollback Order
1. Revoke or rotate any active pilot invites/sessions while operator access is still available.
2. Set `MAX_INVITE_ROLLOUT_ENABLED=false` to stop new operator actions first.
3. Set `MAX_ADAPTER_ENABLED=false` and remove/blank `MAX_BOT_TOKEN` if the runtime must be forced fully inert.
4. Disable or unsubscribe the external provider webhook/subscription, if one exists.
5. Re-run `GET /health/max` and `GET /api/system/messenger-health` to confirm the runtime is back to fail-closed state.

## Owners
- Release Engineering: change window, flag sequencing, evidence capture, rollback call.
- Backend on-call: launch/auth failures, webhook auth failures, adapter bootstrap issues.
- QA: smoke execution, expected-error capture, proof packaging.
- Ops / Integrations: provider subscription, secret rotation, external blocker confirmation.

## Support Notes
- `/api/max/launch` bounded binding states seen in live code: `bound`, `contact_required`, `manual_review_required`.
- `/api/max/launch` error codes seen in live code: `max_adapter_disabled`, `max_bot_token_missing`, `invalid_init_data`, `start_param_required`, `invalid_start_param`, `start_param_mismatch`, `launch_context_missing`, `launch_context_invalid`, `launch_context_revoked`, `launch_context_expired`, `candidate_unavailable`, `identity_mismatch`, `launch_context_ambiguous`.
- Global MAX entry now follows a hidden-draft intake path; `contact_required` and `/api/candidate-access/contact` remain only as bounded recovery/manual paths and must not replace the primary intake semantics.
- `admin_ui` rollout errors seen in live code: `adapter_disabled`, `bot_token_missing`, `candidate_not_bound`, `adapter_unavailable`, `message_or_token_missing`, `max_send_failed`.
- `GET /health/max` and `POST /health/max/sync` are admin-only diagnostics; `POST /health/max/sync` also requires CSRF.
- `POST /api/system/messenger-health/{channel}/recover` is admin-only and currently accepts only `telegram` and `max`.
- Real send remains bounded to candidates already linked to a `max_user_id` or to cohorts that first complete the bind-first webhook/launch path.
- If `/health/max` is healthy but launch/send fails, suspect token/secret/initData issues before suspecting routing.
- If the operator surface is disabled but old tokens still exist, revoke them before reopening the pilot.

## Proven / Not Proven
- Proven: bounded launch/auth shell exists, it fail-closes when disabled/unconfigured, and operator rollout actions are gated separately from the shell.
- Proven: webhook ingress is authenticated by `MAX_BOT_API_SECRET` with a legacy fallback to `MAX_WEBHOOK_SECRET`, and the candidate rollout surface redacts raw launch URLs in normal responses.
- Not proven: production MAX provider availability, durable external subscription health, or a supported full MAX runtime rollout.
- Not proven: historical MAX runtime restoration, browser rollout, SMS fallback rollout, or any channel binding path looser than exact phone match plus a single active application context.
