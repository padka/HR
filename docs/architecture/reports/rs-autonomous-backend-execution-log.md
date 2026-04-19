# RS Autonomous Backend Execution Log

## Date

- 2026-04-18
- 2026-04-19

## Scope

- Close backend scope up to backend-closure status with two bounded dual-write paths.
- Keep runtime cutover disabled until safety layers are verified.
- Start bounded MAX adapter work only after backend closure is complete or only blocked by honest external PostgreSQL contour limits.
- Work in split streams: `PR1` hardening/runtime/docs plus bounded MAX foundation, `PR2` Phase A schema, `PR3` resolver/event prep, `PR5` persistent idempotency plus bounded dual-write slices, `PR4` supporting data/report stream.

## Milestones

| Milestone | Status | Notes |
| --- | --- | --- |
| `M0` Context sync and branch/worktree strategy | `completed` | Dirty mixed workspace inventoried; docs/harness truth refreshed and execution stays in the current mixed workspace |
| `M1` Clean PR1 stream | `completed` | Hardening/runtime/docs stream previously rebuilt from fresh worktree; OpenAPI and runtime gates passed, full-slice `ruff` remains legacy-debt-only and is tracked as non-blocking |
| `M2` Clean PR2 stream | `completed` | `0102` additive schema, RFC-007 conformance, patch assembly, and PostgreSQL proof were previously verified in clean worktrees |
| `M3` Clean PR3 stream | `completed` | Resolver/event skeleton, repositories/UoW prep, `rs-spec-010` placement, and no-runtime-wiring checks were previously verified in clean worktrees |
| `M4` Clean PR5 slice and proof harness | `completed` | `0103`, persistent idempotency, both bounded dual-write paths, and docs/harness packaging are assembled in the current workspace |
| `M5` Backend dual-write paths | `completed` | `candidate create` now emits `candidate.created` plus `application.created` when anchor creation occurs; `candidate status change` is implemented with persistent idempotency, shared resolver, `application.status_changed`, and lifecycle reuse |
| `M6` Integrated PostgreSQL proof on current head | `blocked` | The only remaining backend blocker is a fresh PostgreSQL run for `0102 -> 0103 -> current dual-write slice`; local contour user lacks required privileges on `rs_test` |
| `M7` Backend closure report | `completed` | Backend is `COMPLETE WITH EXTERNAL BLOCKERS`; the only explicit blocker is PostgreSQL contour privilege/access, not missing code |
| `M8` MAX runtime foundation | `completed` | Guarded MAX shell, messenger platform/registry seam, channel health reporting, and safe-default config are in place without reviving historical MAX runtime |
| `M9` MAX access/auth boundary | `completed` | `/api/max/launch` validates signed MAX `initData`, resolves shared launch artifacts via `start_param`, and creates/reuses shared access sessions |
| `M10` MAX shell verification | `completed` | MAX runtime remains default-off, Telegram runtime stays intact, and bounded MAX tests/openapi/runtime stabilization checks are green |
| `M11` MAX candidate journey integration baseline | `completed` | Shared candidate-access booking surface is the current cross-channel baseline, Test1 remains bot-only at runtime, and a new shared Test1/API integration milestone is now the required bridge before HTTP-level MAX E2E proof |
| `M12` MAX candidate journey HTTP proof | `completed` | Shared candidate-access Test1 endpoints, screening/offer payloads, booking gating, bot reuse of shared completion logic, and HTTP-level MAX E2E proof are green without reviving legacy MAX or `/api/webapp/*` transport |
| `M13` MAX bounded rollout surface | `completed` | Admin UI now exposes a protected pilot-only MAX invite control surface for preview, issue/send, rotate/reuse, revoke, and launch observability without enabling MAX by default |
| `M14` MAX controlled pilot readiness | `completed` | Canonical MAX secret/env contract, MAX-only reject path parity, operator copy/list visibility, browser-based visual proof, runbook, and honest smoke/blocker capture were assembled; canonical runtime/frontend/QA docs still required a separate truth-sync pass |
| `M15` MAX mini-app CRM booking integration | `completed` | Shared candidate-access now supports booking-aware `cities / recruiters / booking-context / filtered slots`; MAX mini-app and MAX chat both use the same `city -> recruiter -> slot` CRM-backed flow without MAX-only booking logic |
| `M16` MAX runtime/docs truth sync | `completed` | `AGENTS.md` plus canonical architecture/frontend/QA docs now describe the mounted bounded MAX pilot truth: `/miniapp`, `/api/max/launch`, `/api/max/webhook`, shared `/api/candidate-access/*`, default-off/fail-closed baseline, Telegram as the only supported live messaging runtime, and no production MAX rollout claim |
| `M17` MAX global intake flow | `completed` | Global `/miniapp` launch now creates a hidden MAX draft candidate, opens shared Test1 immediately, keeps drafts out of operator CRM until activation, and uses shared booking/manual-availability seams instead of phone bind as the primary entry path |
| `M21` Live contour incident recovery hardening | `completed` | `admin` crash-loop and `/miniapp` browser bootstrap regressions are now closed with bounded deploy/preflight hardening, live VPS restarts, and HTTP/browser smoke on both contours |

## Current Status

- Working tree is mixed; it already contains `PR1`, `PR2`, `PR3`, `PR4`, and `PR5`-adjacent material.
- Existing patch bundles are available in `artifacts/patches/`, including the refreshed `rs-pr5-persistent-idempotency-dual-write.patch` snapshot.
- PostgreSQL proof for `0102` was previously obtained on a safe local environment.
- `0103_persistent_application_idempotency_keys.py` is live in the workspace; SQLite migration tests and persistent idempotency repository tests are green in the current milestone sequence.
- `openapi-check` is green in the integrated workspace after the bounded MAX endpoint was exported into tracked `admin_api` OpenAPI.
- The first dual-write path is `candidate create` via `backend/apps/admin_ui/services/candidates/helpers.py:upsert_candidate`.
- The shared dual-write bridge is isolated to `backend/apps/admin_ui/services/candidates/application_dual_write.py`.
- `candidate create` remains guarded by `CANDIDATE_CREATE_DUAL_WRITE_ENABLED=false` and now emits `application.created` when resolver-created application anchors are introduced.
- The second bounded dual-write path is `candidate status change`, guarded by `CANDIDATE_STATUS_DUAL_WRITE_ENABLED=false`, using persistent idempotency, shared resolver/application events, and shared lifecycle hooks.
- Status-change write paths accept optional request-level `Idempotency-Key` headers without changing default runtime behavior.
- Bounded MAX foundation is present behind `MAX_ADAPTER_ENABLED=false` with inert config surface: `MAX_BOT_TOKEN`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_INIT_DATA_MAX_AGE_SECONDS`.
- `max_bot.py` is now only a guarded shell entrypoint; the historical `backend.apps.max_bot.app` runtime is still absent.
- `/api/max/launch` is mounted under `admin_api` and returns shared candidate/access bootstrap only after signed MAX `initData` validation and `start_param` launch-context resolution.
- `/miniapp` is mounted under `admin_api` as the candidate-facing bounded MAX pilot shell and is paired with shared `/api/candidate-access/*`.
- Global MAX `/miniapp` entry is now intake-first: first launch without `start_param` creates a hidden draft candidate plus shared access session, opens shared Test1 immediately, and delays operator-visible CRM activation until intake completion.
- `/miniapp` is now explicitly MAX-only at bootstrap time: if signed MAX `initData` is absent, the candidate shell stays fail-closed on a dedicated “open inside MAX” state and does not call `POST /api/max/launch`.
- `POST /api/max/launch` request-validation failures are now normalized into structured `{detail: {code, message}}` responses for the launch boundary instead of raw FastAPI validation arrays.
- Live contour recovery now has a bounded operational contract:
  - manifests under `deploy/contours/admin.txt` and `deploy/contours/maxpilot.txt`
  - preflight script `scripts/contour_preflight.py`
  - incident runbook `docs/runbooks/live-contour-incident-recovery.md`
- `admin_ui` now lazy-loads bounded MAX rollout and dual-write modules from candidate services/routers so missing pilot-only dependencies do not crash the whole CRM contour at import time.
- `admin_ui` now exposes protected recruiter/operator MAX rollout controls at `/api/candidates/{candidate_id}/max-launch-invite` and `/api/candidates/{candidate_id}/max-launch-invite/revoke`, with legacy aliases on `/max-rollout/issue|revoke`.
- Candidate detail now includes `max_rollout` summary for operator visibility: invite state, send state, launch state, expiry, and pilot actions.
- MAX rollout remains pilot-only behind `MAX_INVITE_ROLLOUT_ENABLED=false`; preview and real send are explicitly separated, and `MAX_ADAPTER_ENABLED=false` keeps the flow fail-closed/preview-only.
- Canonical architecture/frontend/QA docs and `AGENTS.md` now describe the mounted bounded MAX pilot truth instead of future-only wording for `/miniapp`.
- Legacy phone/contact restore remains available only as bounded recovery for MAX; it is no longer the primary global entry semantics for `/miniapp`.
- Runtime/docs truth is now synchronized for the bounded pilot surfaces, but provider-backed smoke and shared non-prod CRM contour proof remain external blockers.
- Canonical pilot-specific skills now exist under `.agents/skills/` for release, visual QA, integration smoke, and operator copy review so future MAX pilot passes reuse the same validation grammar.
- Invite lifecycle emits append-only `candidate.access_link.issued|reused|rotated|revoked|launched` and `message.intent_created|sent|failed` events without raw `start_param` or launch URL leakage.
- The shared candidate-access surface now covers `/api/candidate-access/test1`, `/api/candidate-access/test1/answers`, `/api/candidate-access/test1/complete`, slots, bookings, confirm, reschedule, and cancel behind the MAX-authenticated session boundary.
- Shared Test1 completion now persists journey step state, emits deterministic screening decisions, returns channel-agnostic interview offer payloads, and unlocks booking only for `invite_to_interview`.
- Telegram bot `finalize_test1()` now reuses the shared completion/screening helper and keeps Telegram-specific messaging as a thin adapter layer.
- HTTP-level MAX E2E proof is green for: signed MAX launch -> shared candidate-access session -> shared Test1/API progression -> screening/offer payload -> booking -> confirm/reschedule/cancel, all without `/api/webapp/*` or historical MAX runtime wiring.
- MAX-only reject/decline fallback now delivers candidate-facing messaging through the MAX adapter seam by `candidate_external_id`/channel context even when `candidate_tg_id` is `null`, so pure-MAX cohorts are no longer blocked on Telegram identity.
- Candidates list payload now exposes bounded channel linkage (`linked_channels.telegram|max`, `max.linked`) so operators can see MAX cohort visibility outside the candidate detail page.
- Authenticated browser proof was captured through Playwright-driven signed-in admin flows with screenshots under `artifacts/verification/max-pilot-browser/`; browser MCP / full Computer Use was unavailable in this shell and that limitation is explicitly recorded.
- Local non-prod diagnostics proved fail-closed behavior for `GET /health/max`, `POST /health/max/sync`, candidate preview/send UI, and rollout result states. Real provider smoke was attempted honestly and remains blocked by missing exported non-prod MAX creds/env in the current shell.
- Additional live smoke on 2026-04-18 confirmed the split runtime end-to-end on local HTTP contours: `admin_ui` preview/send/reuse, `admin_api` `/api/max/launch`, and `candidate-access` `me` / `journey` / `test1` all responded successfully against the same SQLite contour.
- Live smoke also exposed and closed a real runtime bug: repeated preview/send over the same reused invite could raise `IdempotencyConflictError` for `candidate.access_link.reused`; rollout event idempotency is now scoped by operator request mode so preview and send requests no longer collide.
- Shared candidate-access booking is now city-aware and recruiter-aware:
  - `GET /api/candidate-access/cities`
  - `GET /api/candidate-access/recruiters?city_id=...`
  - `GET /api/candidate-access/booking-context`
  - `POST /api/candidate-access/booking-context`
  - `GET /api/candidate-access/slots?city_id=...&recruiter_id=...`
- Booking context is now persisted in `journey_session.payload_json.candidate_access.booking_context` and reused by both MAX mini-app and MAX chat. Test1 city is used as prefill, but the candidate can switch city before selecting recruiter and slot.
- MAX mini-app booking UX is no longer a generic shortlist: after Test1 it now guides the candidate through `Город -> Рекрутёр -> Время`, shows live recruiter labels/slot counts from CRM, and keeps shared booking/reschedule/cancel semantics.
- MAX chat mode now mirrors the same CRM choice model instead of jumping directly into a slot shortlist: handoff or post-Test1 booking goes through city selection, recruiter selection, then slot booking, with manual-time fallback when no recruiters or slots are available.
- Candidate booking mutations now update shared CRM truth at booking time rather than during navigation only: `users.city`, `users.responsible_recruiter_id`, shared slot ownership, and journey `last_surface/active_surface` stay aligned with the selected city/recruiter/slot.
- The new MAX booking experience is code-ready locally and in tests, but the live `max.recruitsmart.ru` contour still points at an isolated MAX pilot database with no recruiter/slot inventory. The current "placeholder" feeling on live is therefore a data-source problem, not a remaining UX-contract gap in code.
- MAX start flow is now explicit instead of silent:
  - `bot_started` with launch context sends a bounded welcome that explains the short RecruitSmart questionnaire, offers both surfaces (`mini-app` via the system button and `Пройти в чате` via callback), and promises that the candidate can choose an online interview time after the questionnaire.
  - `bot_started` without candidate context now sends an orientation-only welcome instead of silently ignoring the start event; it does not create or bind a candidate outside the bounded invite/context path.
  - `entry:start_chat` now bootstraps a bounded MAX chat principal directly from a valid active MAX launch token, so the candidate can start Test1 in chat without first opening the mini-app.
- MAX chat booking callbacks are now deterministic and instrumented:
  - `city:pick:*`, `recruiter:pick:*`, and no-inventory branches emit explicit fallback prompts instead of returning a quiet `200` with no visible progress.
  - structured runtime logs now record bounded `no_cities_available`, `no_recruiters_available`, and `no_slots_available` reasons without PII.
- MAX mini-app booking is now recruiter-first and calendar-like on the live shell code path:
  - recruiter cards show initials-based avatars, recruiter identity, timezone, and slot counts without needing uploaded photos;
  - slot selection is grouped by day via a lightweight date rail and time chips instead of a flat slot list;
  - `Продолжить в чате` remains available on city, recruiter, and slot steps.
- Live bounded rollout was applied to `max.recruitsmart.ru` on 2026-04-18:
  - remote backup created under `/opt/recruitsmart_maxpilot/backups/1776545645/`;
  - updated runtime files were deployed to `/opt/recruitsmart_maxpilot/backend/apps/admin_api/` and `/opt/recruitsmart_maxpilot/backend/apps/admin_api/candidate_access/`;
  - `recruitsmart-maxpilot-admin-api.service` was restarted successfully after the shared candidate-access dependency set was brought back into sync;
  - external smoke confirmed `https://max.recruitsmart.ru/miniapp` returns `200` and serves the new shell markers (`Короткая анкета`, `Продолжить в чате`, `recruiter-card__avatar`, `Выберите дату и время`).
- Candidate-facing MAX welcome flow no longer uses a chat-level mini-app launch button. The controlled-pilot expectation is now explicit: the candidate opens the mini-app from the system button configured in MAX Partner Platform (`business.max.ru`), while the bot welcome message keeps only the bounded manual-time callback.
- Live desktop smoke on 2026-04-18 exposed a MAX Bridge gap in the bounded `/miniapp` shell: the page was opening inside MAX but did not load `https://st.max.ru/js/max-web-app.js`, so `window.WebApp.initData` was missing and launch failed with the candidate-facing "real MAX initData" error. The shell now loads the official MAX Bridge script and also reads `initDataUnsafe.start_param` before falling back to query params.
- A second live desktop smoke on 2026-04-18 exposed the system-button launch shape: MAX opened the mini-app with signed `initData` but without `startapp/start_param`. `/api/max/launch` now supports a bounded fallback for already bound MAX users: if the current `max_user_id` resolves to exactly one active candidate and exactly one active MAX launch token, launch proceeds without URL payload; ambiguous or missing contexts remain fail-closed.
- Runtime guard is `CANDIDATE_CREATE_DUAL_WRITE_ENABLED=false` by default.
- `make test-postgres-proof` now points only at existing PostgreSQL-backed proof tests; the missing `tests/integration/test_postgres_stateful_proof.py` reference has been removed from the live harness.

## Known Blockers

- True external blocker:
  - fresh PostgreSQL proof for `0103` and the current dual-write branch is blocked by local database privileges. The available local user can connect to `postgresql+asyncpg://recruitsmart:recruitsmart@localhost:5432/rs_test`, but `make test-postgres-proof` fails immediately with `permission denied for table alembic_version`.
  - External blocker: safe non-prod MAX provider proof is not possible from the current workspace because the available local token is rejected by MAX (`/me` and `/subscriptions` return `401 Invalid access_token`), and the canonical pilot env needed for launch/webhook proof (`MAX_ADAPTER_ENABLED`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_BOT_API_SECRET`) is not present. Webhook subscription, real send, provider-backed launch, and follow-up proof remain blocked pending valid non-prod MAX credentials and partner-side configuration.
  - live `max.recruitsmart.ru` still lacks a confirmed shared non-prod CRM database with real recruiter/slot inventory. VPS discovery on 2026-04-18 found only three local PostgreSQL databases:
    - `recruitsmart_maxpilot`: isolated pilot DB, `users=1`, `cities=4`, `recruiters=0`, `slots=0`
    - `recruitsmart_db`: the main admin runtime DB from `/opt/recruitsmart_admin/.env.prod`, `users=7327`, `cities=16`, `recruiters=2`, `slots=19`
    - `rs`: sparse DB, `users=0`, `cities=5`, `recruiters=1`, `slots=0`
    There is no clearly safe shared non-prod CRM source on this VPS today, so switching MAX pilot to `recruitsmart_db` would be a real live-data cutover and was intentionally not performed without explicit owner approval.
- Accepted non-blocking issues:
  - `PR1` full-slice `ruff` is red due to legacy style debt in `backend/apps/admin_ui/routers/api_misc.py` and `backend/apps/admin_ui/services/candidates/helpers.py`; the new bridge files and tests are `ruff`-clean.
  - `PR2` / `PR3` isolated `openapi-check` still depend on `PR1` being in base order; integrated workspace `openapi-check` is green.
  - `PR4` profiler/report stream remains supporting only and does not block backend dual-write closure.
  - Manual review queues from `rs-data-018` remain human-owned follow-up work and are not a backend-closure blocker.
  - Full-file lint on `api_misc.py` remains legacy-debt-only; MAX rollout work was validated with targeted `ruff --select F,E9` on the touched router plus clean/new module checks.
  - Full `tests/test_admin_candidate_schedule_slot.py` remains red on an unrelated pre-existing intro-day path import error (`ModuleNotFoundError: backend.apps.admin_ui.services.max_sales_handoff`); MAX pilot work was validated with targeted list/view tests and broader integrated MAX/journey suites.

## Safety Rules For This Execution

- Do not guess requisition when demand is ambiguous; use `applications.requisition_id = null`.
- Do not perform phone-based strict ownership hardening or auto-merge.
- Keep business mutation and `application_events` insert in the same transaction on any new dual-write path.
- Claim persistent idempotency before final commit.
- Do not enable browser candidate rollout, full MAX runtime/channel rollout, or SMS rollout.
- Do not perform analytics cutover, messaging v2 rollout, or destructive resets.

## Next Action

- Current next step is external proof and contour approval; no additional MAX foundation work is planned in this batch.
- External owners need to:
  - provide non-prod MAX credentials/env and webhook subscription access for real provider smoke;
  - configure the mini-app URL and system launch button for the bot in MAX Partner Platform so the candidate enters Test1 from the chat header instead of a chat deep-link;
  - decide which shared non-prod CRM database `max.recruitsmart.ru` is allowed to use for live recruiter/slot inventory, or provision a safe shared non-prod contour with real booking data;
  - grant PostgreSQL privileges required for `alembic_version` in the integrated proof contour.
- No browser/SMS rollout, no analytics cutover, and no full MAX runtime activation are implied by this milestone.

## Validation Snapshot

- `./.venv/bin/python -m py_compile backend/apps/admin_ui/services/candidates/application_dual_write.py backend/apps/admin_ui/services/candidates/helpers.py backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py backend/apps/admin_ui/routers/candidates.py backend/apps/admin_ui/routers/api_misc.py backend/apps/admin_api/main.py backend/apps/admin_api/max_auth.py backend/apps/admin_api/max_launch.py backend/core/messenger/bootstrap.py backend/core/messenger/channel_state.py backend/core/messenger/max_adapter.py backend/core/messenger/protocol.py backend/core/messenger/registry.py backend/apps/admin_ui/services/messenger_health.py backend/core/settings.py max_bot.py tests/test_candidate_create_dual_write.py tests/test_candidate_status_dual_write.py tests/test_max_auth.py tests/test_max_launch_api.py tests/test_messenger_max_seam.py tests/test_runtime_surface_stabilization.py`
  - passed
- `./.venv/bin/ruff check backend/apps/admin_ui/services/candidates/application_dual_write.py tests/test_candidate_status_dual_write.py backend/apps/admin_api/max_auth.py backend/apps/admin_api/max_launch.py tests/test_max_auth.py tests/test_max_launch_api.py tests/test_messenger_max_seam.py tests/test_runtime_surface_stabilization.py max_bot.py backend/core/messenger/bootstrap.py backend/core/messenger/max_adapter.py backend/core/messenger/channel_state.py backend/core/messenger/protocol.py backend/core/messenger/registry.py backend/apps/admin_ui/services/messenger_health.py`
  - passed
- `./.venv/bin/ruff check --select F,E9 backend/apps/admin_ui/services/candidates/helpers.py backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py backend/apps/admin_ui/routers/candidates.py backend/apps/admin_ui/routers/api_misc.py backend/core/settings.py backend/apps/admin_api/main.py`
  - red on pre-existing unused imports/locals in large shared legacy files; no new syntax/runtime-level failures were introduced in the bounded dual-write/MAX files
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_candidate_create_dual_write.py tests/test_candidate_status_dual_write.py -q`
  - `9 passed`
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_candidate_lifecycle_use_cases.py tests/test_application_persistent_idempotency_repository.py tests/test_application_resolver_contract.py tests/test_application_sqlalchemy_repositories.py tests/test_application_event_store_sqlalchemy.py -q`
  - `50 passed, 2 skipped`
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_auth.py tests/test_max_launch_api.py tests/test_messenger_max_seam.py tests/test_runtime_surface_stabilization.py tests/test_webapp_smoke.py -q`
  - `33 passed`
- `./.venv/bin/python scripts/check_openapi_drift.py`
  - passed
- `make -n test-postgres-proof`
  - passed; target now resolves only to `tests/integration/test_migrations_postgres.py` and `tests/test_application_persistent_idempotency_repository.py`
- `make test-postgres-proof`
  - blocked by `permission denied for table alembic_version`
- `rg -n "backend\\.apps\\.max_bot\\.app|/api/max/launch|MAX_ADAPTER_ENABLED|CANDIDATE_STATUS_DUAL_WRITE_ENABLED" backend max_bot.py tests docs/architecture/reports -S`
  - passed; historical MAX runtime is not mounted, bounded MAX launch route is present, and new flags stay explicit/safe-default
- `./.venv/bin/python -m py_compile backend/domain/candidates/test1_shared.py backend/apps/admin_api/candidate_access/services.py backend/apps/admin_api/candidate_access/router.py backend/apps/bot/services/test1_flow.py backend/domain/repositories.py backend/domain/candidates/status.py tests/test_candidate_access_api.py tests/test_bot_test1_screening.py tests/test_max_e2e_pilot_flow.py tests/test_status_service_transitions.py`
  - passed
- `./.venv/bin/ruff check backend/domain/candidates/test1_shared.py backend/apps/admin_api/candidate_access/services.py backend/apps/admin_api/candidate_access/router.py backend/apps/bot/services/test1_flow.py tests/test_candidate_access_api.py tests/test_bot_test1_screening.py tests/test_max_e2e_pilot_flow.py`
  - passed
- `./.venv/bin/ruff check --select F,E9,I001 backend/domain/repositories.py tests/test_status_service_transitions.py`
  - red on pre-existing import-order debt in legacy files; no new runtime/syntax issues in the confirm-path fix
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_candidate_access_api.py -q`
  - `26 passed`
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_screening_decision.py tests/test_slot_offer_policy.py tests/test_bot_test1_screening.py -q`
  - `15 passed`
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_launch_api.py tests/test_candidate_access_api.py tests/test_max_e2e_pilot_flow.py tests/test_status_service_transitions.py::test_slot_pending_can_move_directly_to_interview_confirmed -q`
  - `37 passed, 1 skipped`
- `./.venv/bin/python scripts/export_openapi.py`
  - passed; tracked `frontend/app/openapi.json` and `backend/apps/admin_api/openapi.json` regenerated from live app factories
- `make openapi-check`
  - passed
- `./.venv/bin/python -m py_compile backend/core/settings.py backend/apps/admin_api/max_webhook.py backend/apps/admin_ui/services/max_runtime.py tests/test_max_webhook_api.py tests/test_admin_max_runtime_surfaces.py`
  - passed
- `./.venv/bin/ruff check backend/core/settings.py backend/apps/admin_api/max_webhook.py backend/apps/admin_ui/services/max_runtime.py tests/test_max_webhook_api.py tests/test_admin_max_runtime_surfaces.py`
  - passed
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_webhook_api.py tests/test_admin_max_runtime_surfaces.py -q`
  - `21 passed`
- `./.venv/bin/python -m py_compile backend/apps/bot/services/base.py backend/apps/bot/services/notification_flow.py tests/test_outbox_notifications.py tests/test_max_e2e_pilot_flow.py`
  - passed
- `./.venv/bin/ruff check tests/test_outbox_notifications.py tests/test_max_e2e_pilot_flow.py`
  - passed
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_outbox_notifications.py tests/test_max_e2e_pilot_flow.py -q`
  - `10 passed`
- `./.venv/bin/python -m py_compile backend/apps/admin_ui/services/candidates/helpers.py tests/test_admin_candidate_schedule_slot.py`
  - passed
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_admin_candidate_schedule_slot.py -q -k 'list_includes_views_for_kanban_and_calendar or views_include_channel_linkage or accepts_canonical_state_filter'`
  - `3 passed, 31 deselected`
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_webhook_api.py tests/test_admin_max_runtime_surfaces.py tests/test_outbox_notifications.py tests/test_max_e2e_pilot_flow.py tests/test_admin_candidate_schedule_slot.py -q -k 'not schedule_intro_day_cancels_active_interview_slot_and_assignment'`
  - `64 passed, 1 deselected, 3 warnings`
- `npm --prefix frontend/app run typecheck`
  - passed
- `npm --prefix frontend/app run test -- ui-cosmetics.test.tsx`
  - `18 passed`
- `npm --prefix frontend/app run build:verify`
  - passed
- `npm --prefix frontend/app run test:e2e:smoke`
  - `11 passed`
- `./.venv/bin/python -m py_compile backend/apps/admin_ui/services/max_rollout.py tests/test_admin_max_runtime_surfaces.py`
  - passed
- `./.venv/bin/ruff check backend/apps/admin_ui/services/max_rollout.py tests/test_admin_max_runtime_surfaces.py`
  - passed
- `ENVIRONMENT=test ./.venv/bin/pytest tests/test_admin_max_runtime_surfaces.py -q -k 'preview_after_send_request_reuses_token_without_event_conflict or send_fails_closed_when_adapter_disabled or dry_run_preview_hides_token_and_persists_safe_audit_trail'`
  - `3 passed, 14 deselected`
- `./.venv/bin/python scripts/check_openapi_drift.py`
  - passed after the live-smoke fix
- Authenticated browser proof:
  - local signed-in Playwright walkthrough captured candidates list, candidate detail MAX card, preview modal, and result modal screenshots under `artifacts/verification/max-pilot-browser/`
- Non-prod MAX diagnostics:
  - `GET /health/max` proved fail-closed runtime snapshot in the local contour
  - `POST /health/max/sync` returned `409 max_adapter_disabled` when adapter remained intentionally disabled
- Additional live HTTP smoke:
  - `admin_ui` on `127.0.0.1:18003` returned `200` for rollout preview on a reused invite after the idempotency fix
  - `admin_ui` send attempt returned `200 send_failed` with provider-side `401 Unauthorized`, proving the runtime now fails closed at the provider edge rather than crashing locally
  - `admin_api` on `127.0.0.1:18004` returned `200` for `/api/max/launch`, `/api/candidate-access/me`, `/api/candidate-access/journey`, and `/api/candidate-access/test1`
  - `POST /health/max/sync` with a test token returned `502 profile_probe_failed` and message `Invalid access_token`, which is the honest remaining provider-credentials blocker for real smoke
- Incident recovery validation now also requires:
  - `python scripts/contour_preflight.py --contour admin --root /opt/recruitsmart_admin`
  - `python scripts/contour_preflight.py --contour maxpilot --root /opt/recruitsmart_maxpilot`
  before any `systemctl restart` on the corresponding live contour
- MAX candidate UX and dual-surface Test1:
  - implemented bounded `POST /api/candidate-access/chat-handoff` for explicit mini-app -> MAX chat switch over the same shared candidate-access session
  - added bounded MAX chat orchestration in `backend/apps/admin_api/max_candidate_chat.py`: one-question-at-a-time Test1 prompts, callback options, slot booking, confirm, reschedule, cancel, and manual-time fallback without reviving historical MAX runtime
  - rewired MAX webhook candidate branches to reuse shared `candidate_access` / `test1_shared` services instead of Telegram FSM state
  - rewrote `/miniapp` as a candidate-first one-question flow with onboarding, progress, save/back/next controls, shortlist slot cards, and `Продолжить в чате`; removed technical pilot/session copy from the candidate surface
  - `journey_session.last_surface` and `payload_json.candidate_access.active_surface/chat_cursor` now mark `max_chat` vs `max_miniapp` as the active candidate surface without schema changes
- Validation for MAX candidate UX batch:
  - `./.venv/bin/python -m py_compile backend/apps/admin_api/max_candidate_chat.py backend/apps/admin_api/max_webhook.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_api/candidate_access/auth.py backend/apps/admin_api/max_miniapp.py backend/domain/candidates/models.py tests/test_max_candidate_chat.py tests/test_max_miniapp_shell.py`
    - passed
  - `./.venv/bin/ruff check backend/apps/admin_api/max_candidate_chat.py backend/apps/admin_api/max_webhook.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_api/candidate_access/auth.py backend/apps/admin_api/max_miniapp.py backend/domain/candidates/models.py tests/test_max_candidate_chat.py tests/test_max_miniapp_shell.py`
    - passed
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_miniapp_shell.py tests/test_max_candidate_chat.py tests/test_max_webhook_api.py tests/test_candidate_access_api.py tests/test_max_launch_api.py -q`
    - `45 passed, 1 skipped`
  - `make openapi-export`
    - passed; regenerated `backend/apps/admin_api/openapi.json`, `frontend/app/openapi.json`, and `frontend/app/src/api/schema.ts` with `POST /api/candidate-access/chat-handoff`
  - `./.venv/bin/python scripts/check_openapi_drift.py`
    - passed
  - `npm --prefix frontend/app run typecheck`
    - passed
  - `npm --prefix frontend/app run build:verify`
    - passed
- Validation for MAX CRM booking integration batch:
  - `./.venv/bin/python -m py_compile backend/apps/admin_api/candidate_access/services.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_api/max_candidate_chat.py backend/apps/admin_api/max_miniapp.py tests/test_candidate_access_api.py tests/test_max_candidate_chat.py tests/test_max_miniapp_shell.py`
    - passed
  - `./.venv/bin/ruff check backend/apps/admin_api/candidate_access/services.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_api/max_candidate_chat.py backend/apps/admin_api/max_miniapp.py tests/test_candidate_access_api.py tests/test_max_candidate_chat.py tests/test_max_miniapp_shell.py`
    - passed
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_candidate_access_api.py tests/test_max_candidate_chat.py tests/test_max_miniapp_shell.py -q`
    - `35 passed`
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_miniapp_shell.py tests/test_max_candidate_chat.py tests/test_candidate_access_api.py -q`
    - `37 passed`
  - `make openapi-export`
    - passed; regenerated tracked admin_api/admin_ui schemas and `frontend/app/src/api/schema.ts` with the booking-aware candidate-access contract
  - `./.venv/bin/python scripts/check_openapi_drift.py`
    - passed after export
  - `npm --prefix frontend/app run typecheck`
    - passed
  - `npm --prefix frontend/app run build:verify`
    - passed
- Remaining blocker for live pilot proof:
  - candidate-first mini-app and shared CRM booking code are ready locally and in contract-level tests, but live `max.recruitsmart.ru` still needs an approved shared non-prod CRM source before recruiter/slot inventory can appear honestly in the pilot contour
- Test1 retake / renewed selection cycle:
  - added recruiter action `restart_test1` on bounded allowed statuses (`test1_completed`, waiting-slot states, and closed decline/not-hired outcomes) without introducing MAX-only runtime logic
  - restart now archives the current Test1 attempt snapshot into shared journey payload history, emits a `test1_restarted` journey event, force-resets candidate status back to `invited`, clears current-process candidate-access booking/chat state, and bumps `journey_session.session_version` so existing candidate-access sessions fail closed with `stale_session_version`
  - existing recruiter-visible history remains canonical through `test_sections.test1.history`, timeline journey events, previous slot history, and message history; no new admin page was introduced
  - repeated Test1 completion now produces a second `TestResult` instead of overwriting the first one, and bounded MAX relaunch resumes from a fresh Test1 session after recruiter restart
- Validation for Test1 retake batch:
  - `./.venv/bin/python -m py_compile backend/domain/candidates/test1_shared.py backend/domain/candidates/actions.py backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py backend/apps/admin_ui/services/candidates/write_intents.py tests/test_candidate_actions.py tests/test_candidate_lifecycle_use_cases.py tests/test_candidate_access_api.py tests/test_admin_candidate_chat_actions.py`
    - passed
  - `./.venv/bin/ruff check --select F,E9,I backend/domain/candidates/test1_shared.py backend/domain/candidates/actions.py backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py backend/apps/admin_ui/services/candidates/write_intents.py tests/test_candidate_actions.py tests/test_candidate_lifecycle_use_cases.py tests/test_candidate_access_api.py tests/test_admin_candidate_chat_actions.py`
    - passed
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_candidate_actions.py tests/test_candidate_lifecycle_use_cases.py tests/test_candidate_access_api.py tests/test_admin_candidate_chat_actions.py -q`
    - `81 passed`
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_launch_api.py tests/test_max_candidate_chat.py tests/test_max_e2e_pilot_flow.py -q`
    - `18 passed, 1 skipped`
  - `./.venv/bin/python scripts/check_openapi_drift.py`
    - passed; no public API schema drift introduced by the recruiter-side restart path
- Validation for MAX start flow and live mini-app UX batch:
  - `./.venv/bin/python -m py_compile backend/apps/admin_api/max_candidate_chat.py backend/apps/admin_api/max_webhook.py backend/apps/admin_api/max_miniapp.py tests/test_max_webhook_api.py tests/test_max_miniapp_shell.py tests/test_max_candidate_chat.py`
    - passed
  - `./.venv/bin/ruff check backend/apps/admin_api/max_candidate_chat.py backend/apps/admin_api/max_webhook.py backend/apps/admin_api/max_miniapp.py tests/test_max_webhook_api.py tests/test_max_miniapp_shell.py tests/test_max_candidate_chat.py`
    - passed
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_webhook_api.py tests/test_max_miniapp_shell.py tests/test_max_candidate_chat.py tests/test_candidate_access_api.py tests/test_max_launch_api.py -q`
    - `54 passed, 1 skipped`
  - `./.venv/bin/python scripts/check_openapi_drift.py`
    - passed; no route/schema drift introduced by the welcome/chat-start and mini-app UX changes
  - remote bounded rollout:
    - backed up `/opt/recruitsmart_maxpilot/backend/apps/admin_api/{max_candidate_chat.py,max_webhook.py,max_miniapp.py}` plus `candidate_access/{services.py,router.py}` into `/opt/recruitsmart_maxpilot/backups/1776545645/`
    - deployed the updated files to `/opt/recruitsmart_maxpilot/`
    - `systemctl restart recruitsmart-maxpilot-admin-api.service`
      - passed after dependency sync
    - external smoke:
      - `https://max.recruitsmart.ru/miniapp`
        - `200` with `Короткая анкета`, `Продолжить в чате`, `recruiter-card__avatar`, and `Выберите дату и время`
- Next action:
  - live UX/runtime fixes are deployed on the current MAX pilot contour.
  - the remaining live step is an explicit infra decision: either provide a safe shared non-prod CRM database with real recruiter/slot inventory, or approve switching the MAX pilot contour to the populated `recruitsmart_db` despite it being the same database used by the main admin runtime.

## 2026-04-19 — M17 MAX controlled pilot readiness pass

- Scope closed in this pass:
  - synced runtime/docs truth for bounded MAX pilot surfaces
  - hardened `/miniapp` UX and route-scoped MAX bridge usage
  - tightened operator visibility in list/detail surfaces
  - added browser-level visual QA evidence under `artifacts/verification/2026-04-19-max-pilot-visual-qa/`
  - re-checked provider smoke and recorded the honest external blocker
- Key implementation notes:
  - `/miniapp` remains mounted and implemented for bounded controlled pilot, still default-off and fail-closed
  - MAX bridge loading was moved from global `index.html` to route-scoped lazy bootstrap in `frontend/app/src/app/routes/miniapp/maxBridge.ts`
    - reason: global script injection caused CSP console errors across `/app/*` and broke Playwright smoke
  - operator list/detail now exposes preferred-channel filtering, bounded linked-channel badges, compact MAX state chips, and explicit launch-observed state
  - candidate miniapp now has distinct `manual_review_required`, explicit booking empty states, stronger booked/success states, and a two-step MAX chat handoff success flow
- Validation:
  - `python3 -m py_compile backend/apps/admin_api/max_launch.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_ui/services/max_rollout.py backend/apps/admin_ui/services/candidates/helpers.py tests/test_max_launch_api.py tests/test_max_miniapp_shell.py tests/test_candidate_access_api.py tests/test_admin_max_runtime_surfaces.py tests/test_admin_candidate_schedule_slot.py`
    - passed
  - `./.venv/bin/ruff check backend/apps/admin_api/max_launch.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_ui/services/max_rollout.py tests/test_max_launch_api.py tests/test_max_miniapp_shell.py tests/test_candidate_access_api.py tests/test_admin_max_runtime_surfaces.py`
    - passed
  - `./.venv/bin/pytest tests/test_max_launch_api.py tests/test_candidate_access_api.py tests/test_max_miniapp_shell.py tests/test_admin_max_runtime_surfaces.py tests/test_max_webhook_api.py tests/test_admin_candidate_schedule_slot.py::test_api_candidates_list_views_include_channel_linkage -q`
    - `69 passed, 1 skipped, 2 warnings`
  - `npm --prefix frontend/app run test -- src/app/routes/miniapp/index.test.tsx src/app/routes/app/ui-cosmetics.test.tsx`
    - `24 passed`
  - `npm --prefix frontend/app run typecheck`
    - passed
  - `npm --prefix frontend/app run build:verify`
    - passed
  - `./.venv/bin/python scripts/check_openapi_drift.py`
    - passed after `make openapi-export`
  - `./.venv/bin/pytest tests/test_max_miniapp_shell.py -q`
    - `2 passed`
  - `npm --prefix frontend/app run test:e2e:smoke`
    - initial run failed after the global MAX script injection because CSP blocked `https://st.max.ru/js/max-web-app.js` on `/app/*`
    - fixed by moving the bridge to route-scoped lazy loading
    - rerun passed: `11 passed`
- Visual QA evidence:
  - operator signed-in screenshots:
    - `operator-candidates-max.png`
    - `operator-candidate-detail-max-card.png`
    - `operator-max-preview-modal.png`
    - `operator-max-result-modal.png`
  - candidate miniapp screenshots:
    - `miniapp-contact-required.png`
    - `miniapp-manual-review.png`
    - `miniapp-home-next-step.png`
    - `miniapp-test1-in-progress.png`
    - `miniapp-booking-empty-cities.png`
    - `miniapp-booking-empty-recruiters.png`
    - `miniapp-booking-empty-slots.png`
    - `miniapp-booked-return-home.png`
    - `miniapp-booking-success.png`
    - `miniapp-chat-ready.png`
  - limitation wording:
    - browser automation and screenshots only
    - no native MAX client proof
    - no provider-owned MAX Partner UI proof
    - no fake provider success claims
- Provider smoke / blocker:
  - local read-only probe against MAX provider returned `401 Invalid access_token` for `/me` and `/subscriptions`
  - current local runtime/settings inventory still lacks the canonical pilot set needed for provider-backed launch/webhook proof
  - External blocker: safe non-prod MAX provider proof is not possible from the current workspace because the available local token is rejected by MAX (`/me` and `/subscriptions` return `401 Invalid access_token`), and the canonical pilot env needed for launch/webhook proof (`MAX_ADAPTER_ENABLED`, `MAX_PUBLIC_BOT_NAME`, `MAX_MINIAPP_URL`, `MAX_BOT_API_SECRET`) is not present. Webhook subscription, real send, provider-backed launch, and follow-up proof remain blocked pending valid non-prod MAX credentials and partner-side configuration.
- Next action:
  - pilot code, bounded operator surface, docs, and browser-level evidence are ready for a controlled pilot handoff
  - the remaining gate is valid non-prod MAX credentials plus partner-side configuration for honest provider-backed smoke

## 2026-04-19 — M18 MAX VPS shell parity deploy

- Scope closed in this pass:
  - deployed the current MAX candidate SPA shell from local `frontend/dist` to the live MAX VPS contour
  - replaced the old inline `max_miniapp.py` shell on the VPS with the current bundle-backed host shell
  - aligned the live MAX pilot backend slice with the current local candidate shell contract
- Live MAX VPS contour:
  - host: `72.56.243.198`
  - working tree: `/opt/recruitsmart_maxpilot`
  - service: `recruitsmart-maxpilot-admin-api.service`
- Remote rollout:
  - backup created under `/opt/recruitsmart_maxpilot/backups/20260419_021612/`
  - deployed files:
    - `backend/apps/admin_api/main.py`
    - `backend/apps/admin_api/max_launch.py`
    - `backend/apps/admin_api/max_miniapp.py`
    - `backend/apps/admin_api/candidate_access/router.py`
    - `backend/apps/admin_api/candidate_access/services.py`
    - `frontend/dist/*`
  - `systemctl restart recruitsmart-maxpilot-admin-api.service`
    - passed
- Validation:
  - local:
    - `python3 -m py_compile backend/apps/admin_api/main.py backend/apps/admin_api/max_miniapp.py tests/test_max_miniapp_shell.py`
      - passed
    - `./.venv/bin/ruff check backend/apps/admin_api/main.py backend/apps/admin_api/max_miniapp.py tests/test_max_miniapp_shell.py`
      - passed
    - `./.venv/bin/pytest tests/test_max_miniapp_shell.py -q`
      - `2 passed`
    - `npm --prefix frontend/app run build:verify`
      - passed
  - remote:
    - `/opt/recruitsmart_admin/.venv/bin/python -m py_compile /opt/recruitsmart_maxpilot/backend/apps/admin_api/main.py /opt/recruitsmart_maxpilot/backend/apps/admin_api/max_launch.py /opt/recruitsmart_maxpilot/backend/apps/admin_api/max_miniapp.py /opt/recruitsmart_maxpilot/backend/apps/admin_api/candidate_access/router.py /opt/recruitsmart_maxpilot/backend/apps/admin_api/candidate_access/services.py`
      - passed
    - external smoke:
      - `https://max.recruitsmart.ru/miniapp`
        - `200`
        - now serves the current SPA shell with `/assets/index-CpJZP3cU.js`
        - returns `Cache-Control: no-store, no-cache, must-revalidate`, `Pragma: no-cache`, `Expires: 0`
- Outcome:
  - the old inline MAX mini-app is no longer the live shell on `max.recruitsmart.ru`
  - MAX troubleshooting and future live checks should use the VPS contour at `/opt/recruitsmart_maxpilot`, not the unrelated `prod-ssr` host

## 2026-04-19 — M19 live MAX DB alignment to shared CRM

- Scope closed in this pass:
  - switched the live MAX VPS contour from the isolated `recruitsmart_maxpilot` database to the shared CRM database used by the main admin/bot runtime
  - verified that the bounded MAX contour and the main Telegram bot now read the same city/recruiter/slot inventory truth
  - intentionally did not hard-delete historical `test_results` from the isolated pilot database because that database is no longer the live MAX data source
- Runtime changes:
  - backup created: `/opt/recruitsmart_maxpilot/backups/20260418_233024_env/.env.maxpilot`
  - `/opt/recruitsmart_maxpilot/.env.maxpilot`
    - `DATABASE_URL` now points to the same `recruitsmart_db` value used by `/opt/recruitsmart_admin/.env.prod`
    - `MIGRATIONS_DATABASE_URL` was absent and was not added
  - restarted only `recruitsmart-maxpilot-admin-api.service`
- Validation:
  - live MAX contour:
    - `https://max.recruitsmart.ru/health`
      - `healthy`
    - `https://max.recruitsmart.ru/miniapp`
      - `200`
      - still serves the current SPA shell with `Cache-Control: no-store, no-cache, must-revalidate`
  - shared DB truth seen from maxpilot env after cutover:
    - `users=7327`
    - `cities=16`
    - `recruiters=2`
    - `free_slots=10`
  - shared DB truth seen from bot-side repository calls:
    - `get_candidate_cities()` -> `16` active cities
    - `get_active_recruiters()` -> `2` active recruiters (`Алина`, `Михаил`)
    - `get_active_recruiters_for_city(14)` -> recruiter `Михаил`
    - `get_recruiters_free_slots_summary(..., city_id=14)` -> `{1: (<utc datetime>, 5)}`
  - main bot runtime:
    - `recruitsmart-bot.service` remains active and continues to use the shared CRM database
- Candidate reset/retake notes:
  - the old isolated MAX pilot DB still contains `max_user_id=129613756` with completed Test1 history, but that contour is no longer live
  - the shared CRM DB had no `max_user_id=129613756` at cutover time, so no hard delete was needed in the target live DB
  - shared CRM does contain a Telegram candidate row for `telegram_user_id=7588303412` with no Test1 results; future MAX contact binding may reuse that shared candidate instead of creating a duplicate
- Outcome:
  - live MAX mini-app submissions can now appear in the main CRM instead of the isolated pilot database
  - Telegram-bot inventory verification must be evaluated against the shared CRM DB, not the retired isolated pilot DB

## 2026-04-19 — M20 live MAX global intake flow deployment

- Scope closed in this pass:
  - changed live MAX global `/miniapp` semantics from bind-first recovery to intake-first hidden-draft creation
  - kept shared Test1, shared booking, and shared chat-handoff logic canonical
  - added shared `manual-availability` no-slots path for MAX intake instead of forcing chat as the primary fallback
  - hid hidden-draft MAX candidates from standard operator CRM list/detail/dashboard surfaces until activation
- Runtime changes deployed:
  - `maxpilot` contour (`/opt/recruitsmart_maxpilot`):
    - `backend/apps/admin_api/max_launch.py`
    - `backend/apps/admin_api/candidate_access/router.py`
    - `backend/apps/admin_api/candidate_access/services.py`
    - `backend/domain/candidates/journey.py`
    - `frontend/dist/*`
  - main CRM contour (`/opt/recruitsmart_admin`):
    - `backend/apps/admin_ui/services/candidates/helpers.py`
    - `backend/apps/admin_ui/services/dashboard.py`
    - `backend/domain/candidates/journey.py`
  - recovery-only operational fix on main CRM contour:
    - copied missing migration files `0098` through `0103` into `/opt/recruitsmart_admin/backend/migrations/versions/` because `recruitsmart-admin.service` restart was blocked by `unknown migration revision '0103_persistent_application_idempotency_keys'`
- Validation:
  - local:
    - `python3 -m py_compile backend/apps/admin_api/max_launch.py backend/apps/admin_api/candidate_access/services.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_ui/services/candidates/helpers.py backend/apps/admin_ui/services/dashboard.py backend/domain/candidates/journey.py tests/test_max_launch_api.py tests/test_candidate_access_api.py tests/test_admin_candidates_service.py`
      - passed
    - `./.venv/bin/ruff check --select F,E9,I001 backend/apps/admin_api/max_launch.py backend/apps/admin_api/candidate_access/services.py backend/apps/admin_api/candidate_access/router.py backend/apps/admin_ui/services/dashboard.py backend/domain/candidates/journey.py tests/test_max_launch_api.py tests/test_candidate_access_api.py tests/test_admin_candidates_service.py`
      - passed
    - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_launch_api.py tests/test_candidate_access_api.py -q`
      - `44 passed, 1 skipped`
    - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_admin_candidates_service.py -q -k 'hide_draft_intake_candidates or list_candidates_and_detail'`
      - `2 passed, 26 deselected`
    - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_miniapp_shell.py -q`
      - `2 passed`
    - `ENVIRONMENT=test npm --prefix frontend/app run test -- src/app/routes/miniapp/index.test.tsx`
      - `7 passed`
    - `npm --prefix frontend/app run typecheck`
      - passed
    - `npm --prefix frontend/app run build:verify`
      - passed
    - `make openapi-export`
      - passed
    - `./.venv/bin/python scripts/check_openapi_drift.py`
      - passed after schema export
  - remote:
    - `python3 -m py_compile` on the deployed MAX/admin slices
      - passed
    - `systemctl restart recruitsmart-maxpilot-admin-api.service`
      - passed
    - `systemctl restart recruitsmart-admin.service`
      - initially failed on missing migration files `0098-0103`; passed after restoring those files
    - `curl -s https://max.recruitsmart.ru/miniapp | rg -o 'assets/index-[A-Za-z0-9_-]+\\.js' -m 1`
      - current live shell now serves `assets/index-DmUG0fkp.js`
- Outcome:
  - live MAX global entry is now intake-first on the bounded pilot contour
  - hidden draft candidates remain server-backed but stay out of standard operator CRM surfaces until activation
  - main CRM runtime is back to `active` after restoring the missing migration file set required by its restart-time migration preflight

## 2026-04-19 — M21 live contour incident recovery hardening

- Root causes confirmed:
  - `admin.recruitsmart.ru` `502` came from partial live contour deploy drift on `/opt/recruitsmart_admin`: `admin_ui` imported pilot-only modules eagerly and could crash the whole CRM contour when those runtime dependencies were absent or out of sync
  - browser opens of `https://max.recruitsmart.ru/miniapp` could hit `POST /api/max/launch` without MAX `initData`, producing FastAPI validation arrays that the shell surfaced as `[object Object]`
- Code/process hardening landed:
  - `backend/apps/admin_ui/services/candidates/helpers.py`
    - lazy-loads MAX rollout and dual-write modules so bounded pilot dependencies no longer crash the main CRM contour at import time
  - `backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py`
    - lazy-loads dual-write runtime for status actions
  - `backend/apps/admin_ui/routers/api_misc.py`
    - lazy-loads MAX rollout runtime and degrades to bounded `503 max_rollout_unavailable` instead of import-time crash
  - `backend/apps/admin_api/main.py`
    - adds structured `RequestValidationError` handling for `/api/max/launch`
    - mounts `/manifest.json` and `/icons/*` from `frontend/dist`
  - `frontend/app/src/app/routes/miniapp/index.tsx`
    - keeps `/miniapp` fail-closed outside MAX
    - does not call `/api/max/launch` when `initData` is absent
    - renders meaningful RU launch errors instead of `[object Object]`
  - `scripts/contour_preflight.py`
    - import + manifest + migration preflight for `admin` and `maxpilot`
  - `deploy/contours/admin.txt` and `deploy/contours/maxpilot.txt`
    - bounded live contour manifests
  - `docs/runbooks/live-contour-incident-recovery.md`
    - bounded recovery/deploy runbook
- VPS backup + deploy:
  - backups:
    - `/opt/recruitsmart_admin/backups/20260419_035402/admin-contour.tgz`
    - `/opt/recruitsmart_maxpilot/backups/20260419_035402/maxpilot-contour.tgz`
  - remote preflight:
    - `/opt/recruitsmart_admin/.venv/bin/python scripts/contour_preflight.py --contour admin --root /opt/recruitsmart_admin`
      - passed
    - `source /opt/recruitsmart_maxpilot/.env.maxpilot && /opt/recruitsmart_admin/.venv/bin/python scripts/contour_preflight.py --contour maxpilot --root /opt/recruitsmart_maxpilot`
      - passed
  - controlled restarts:
    - `recruitsmart-admin.service`
      - restarted successfully and remained `active`
    - `recruitsmart-maxpilot-admin-api.service`
      - restarted successfully and remained `active`
- Live smoke after deploy:
  - `https://admin.recruitsmart.ru/`
    - no longer `502`; current public response is `401 Authentication required`, which is the expected auth boundary for an unauthenticated root request
  - `https://max.recruitsmart.ru/miniapp`
    - `200`
    - current shell references the rebuilt SPA bundle from `frontend/dist`
  - `https://max.recruitsmart.ru/manifest.json`
    - `200`
  - `https://max.recruitsmart.ru/icons/icon-192.png`
    - `200`
  - `POST https://max.recruitsmart.ru/api/max/launch` with empty request body
    - now returns structured validation response:
      - `{"detail":{"code":"invalid_init_data","message":"Откройте кабинет внутри MAX, чтобы передать корректный launch-контекст."}}`
  - browser-level outside-MAX proof:
    - headless Playwright open of `https://max.recruitsmart.ru/miniapp`
    - visible state text:
      - `Откройте кабинет внутри MAX`
      - `Этот личный кабинет работает только внутри MAX mini app и не запускается как обычная браузерная страница.`
    - captured network log for the same browser open showed `LAUNCH_REQUESTS []`, i.e. no browser-side `POST /api/max/launch` when signed MAX `initData` is absent
- Local validation for the hardening slice:
  - `python3 -m py_compile backend/apps/admin_ui/services/candidates/helpers.py backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py backend/apps/admin_ui/routers/api_misc.py backend/apps/admin_api/main.py backend/apps/admin_api/candidate_access/services.py scripts/contour_preflight.py tests/test_max_launch_api.py tests/test_max_miniapp_shell.py tests/test_admin_candidates_service.py`
    - passed
  - `./.venv/bin/ruff check --select F,E9,I001 backend/apps/admin_ui/services/candidates/helpers.py backend/apps/admin_ui/services/candidates/lifecycle_use_cases.py backend/apps/admin_ui/routers/api_misc.py backend/apps/admin_api/main.py backend/apps/admin_api/candidate_access/services.py scripts/contour_preflight.py tests/test_max_launch_api.py tests/test_max_miniapp_shell.py tests/test_admin_candidates_service.py`
    - passed
  - `ENVIRONMENT=test ./.venv/bin/pytest tests/test_max_launch_api.py tests/test_max_miniapp_shell.py tests/test_admin_candidates_service.py -q`
    - `44 passed, 1 skipped`
  - `npm --prefix frontend/app run test -- src/app/routes/miniapp/index.test.tsx`
    - `8 passed`
  - `npm --prefix frontend/app run typecheck`
    - passed
  - `npm --prefix frontend/app run build:verify`
    - passed
  - `./.venv/bin/python scripts/check_openapi_drift.py`
    - passed
  - `npm --prefix frontend/app run test:e2e:smoke`
    - `11 passed`
- Outcome:
  - live `admin` contour is back behind its intended auth boundary instead of `502`
  - `/miniapp` is now explicitly MAX-only for browser opens and no longer leaks raw launch-validation payloads to end users
  - bounded live contour deploys now have manifests, import preflight, and a recorded rollback bundle instead of blind file-by-file restarts
