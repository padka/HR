# MAX Bot Readiness Audit

Дата аудита: `2026-04-09`

Scope:
- live code в `backend/*`, `frontend/app/*`, `tests/*`, `docs/*`
- Telegram bot flow
- candidate portal / journey layer
- slot assignment / scheduling layer
- messenger abstraction / delivery layer

Important discrepancy:
- В репозитории уже существует MAX runtime и значительная MAX-логика: [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py), [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py), [`backend/core/messenger/*`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger).
- Поэтому выводы ниже относятся не к "пустой системе перед стартом MAX", а к текущему состоянию codebase, где MAX уже частично и местами глубоко реализован.

## 1. Executive Summary

Система построена как monorepo CRM/ATS с одним основным backend на FastAPI, SPA на React и несколькими candidate-facing transport layers: Telegram bot, candidate portal, Telegram WebApp и MAX webhook runtime. Telegram-бот исторически был primary candidate channel, но текущая архитектура уже частично сместила доменную логику в provider-agnostic слой candidate portal / journey / slot assignment.

Ключевой вывод: MAX нельзя честно назвать "новым пустым transport layer поверх Telegram-only ядра", потому что в коде уже есть channel-agnostic core для profile/screening/journey и уже есть отдельный MAX transport. Одновременно нельзя сказать, что система полностью готова к чистой multi-channel архитектуре: Telegram legacy по-прежнему течёт в identity, state store, recruiter tooling, slot callbacks и части scheduling write-paths.

Главный практический вывод для будущего ТЗ:
- fastest safe path: не "быстрый адаптер поверх Telegram handlers";
- recommended path: частичный рефакторинг + усиление channel-agnostic core вокруг candidate identity, candidate journey, assignment-owned scheduling и messaging contracts.

Ключевые преимущества текущей архитектуры:
- уже есть messenger abstraction: [`backend/core/messenger/protocol.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/protocol.py), [`backend/core/messenger/registry.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/registry.py)
- candidate journey и portal уже channel-agnostic по замыслу и частично по факту: [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- scheduling hardening уже опирается на `SlotAssignment` и integrity/reporting layer: [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py), [`backend/domain/candidates/scheduling_integrity.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py)
- тесты по MAX/portal/scheduling уже есть

Ключевые риски:
- `users` и legacy bot flows всё ещё Telegram-centric
- in-memory/Redis bot state остаётся Telegram chat-id centric: [`backend/apps/bot/state_store.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/state_store.py)
- slot scheduling write-paths переходные: coexistence `Slot` и `SlotAssignment`
- recruiter/admin APIs и health surfaces ещё местами мыслят Telegram как default primary channel

## 2. System Architecture

### 2.1 Service map

| Service / module | Where | Role | Main dependencies | Entry points | Bot relation |
| --- | --- | --- | --- | --- | --- |
| Admin UI app | [`backend/apps/admin_ui/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py) | основной FastAPI app, SPA host, admin APIs, candidate portal APIs | PostgreSQL, Redis, frontend dist | web routes, `/api/*`, `/candidate/*` | выдаёт invite/deeplink, recruiter actions, portal APIs |
| Admin API | [`backend/apps/admin_api/main.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/main.py) | отдельные API surfaces для webapp / slot assignments / HH | FastAPI, DB | `/api/webapp/*`, `/api/slot-assignments/*` | candidate-facing booking/confirm/reschedule APIs |
| Telegram bot runtime | [`backend/apps/bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/app.py) | aiogram polling runtime, notification/outbox processing, candidate + recruiter chat UX | aiogram, Redis state, DB, messenger registry | `main()`, dispatcher routers | primary Telegram transport |
| MAX bot runtime | [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | FastAPI webhook receiver for MAX | MAX adapter, DB, Redis dedupe | `/webhook`, `/health` | MAX transport |
| Candidate portal / journey domain | [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) | channel-agnostic candidate profile/screening/journey/session contracts | DB, settings, analytics, slot service | portal APIs + MAX flow + Telegram cabinet links | core reusable domain layer |
| Candidate status / workflow | [`backend/domain/candidates/status.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py), [`backend/domain/candidates/status_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status_service.py), [`backend/domain/candidates/workflow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/workflow.py) | pipeline state model | DB models | called from bot/admin/portal/service flows | shared domain |
| Scheduling core | [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py), [`backend/domain/slot_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_service.py), [`backend/domain/repositories.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py) | booking, offer, confirm, reschedule, outbox enqueue | DB, outbox, action tokens | admin UI routers, admin API, bot flows, portal flows | shared but transitional |
| Messenger abstraction | [`backend/core/messenger/*`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger) | adapter registry for Telegram/MAX delivery | bot instance, MAX HTTP adapter | bootstrap during runtime startup | delivery abstraction |
| Notification / outbox runtime | [`backend/apps/bot/services/notification_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/notification_flow.py) | outbox poller, rendering, retry, delivery classification | DB, Redis or in-memory broker, messenger registry | bot runtime startup | shared delivery path for Telegram and MAX |
| Frontend SPA | [`frontend/app/src/app/main.tsx`](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx) | recruiter UI and candidate portal UI | admin APIs | `/app/*`, `/candidate/*` | candidate portal and recruiter control surfaces |

### 2.2 Architecture layers

Transport-specific:
- Telegram runtime and handlers: [`backend/apps/bot/handlers/*`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers)
- MAX webhook runtime and event parsing: [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- Telegram WebApp auth surface: [`backend/apps/admin_api/webapp/auth.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py)

Domain logic:
- candidate lifecycle/status/workflow: [`backend/domain/candidates/status.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py), [`backend/domain/candidates/status_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status_service.py)
- portal/journey/profile/screening: [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- scheduling: [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)

Orchestration logic:
- Telegram flow composition: [`backend/apps/bot/services/onboarding_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/onboarding_flow.py), [`backend/apps/bot/services/test1_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/slot_flow.py)
- MAX flow composition: [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- recruiter/admin orchestration: [`backend/apps/admin_ui/routers/slot_assignments.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments.py), [`backend/apps/admin_ui/services/dashboard.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/dashboard.py)

Persistence logic:
- SQLAlchemy models: [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py), [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py)
- repository helpers and outbox persistence: [`backend/domain/repositories.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py)
- bot ephemeral state: [`backend/apps/bot/state_store.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/state_store.py)

### 2.3 Full candidate flow participants

ASCII map:

```text
Candidate
  -> Telegram bot / MAX bot / browser portal / Telegram WebApp / HH entry chooser
  -> transport handler/runtime
  -> candidate portal / journey / status / scheduling domain
  -> DB models (users, journey, slot_assignments, slots, chat_messages, invite_tokens, outbox)
  -> outbox notification runtime
  -> Telegram or MAX adapter delivery
  -> recruiter/admin UI surfaces consume projected state contract
```

## 3. Telegram Bot Audit

### 3.1 Code locations and entry points

Primary entrypoint:
- [`backend/apps/bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/app.py)
  - `create_bot()`
  - `create_dispatcher()`
  - `create_application()`
  - `main()`

Dispatcher/router registration:
- [`backend/apps/bot/handlers/__init__.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/__init__.py)
  - routers: `common`, `test1`, `test2`, `slots`, `recruiter`, `recruiter_actions`, `attendance`, `interview`, `slot_assignments`

Polling/webhook mode:
- Telegram bot runtime in this module is polling-oriented in practice: `main()` calls `bot.delete_webhook(drop_pending_updates=True)` before polling.
- Separate admin runtime config/health for bot exists in [`backend/apps/admin_ui/state.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/state.py).
- Explicit Telegram webhook handler in candidate flow was not found in `backend/apps/bot/*`; current transport is aiogram runtime rather than FastAPI webhook receiver.

### 3.2 Middleware

Telegram-specific middleware:
- [`backend/apps/bot/middleware.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/middleware.py)
  - `TelegramIdentityMiddleware`: extracts `from_user` from aiogram updates and calls `link_telegram_identity()`
  - `InboundChatLoggingMiddleware`: persists inbound private messages to `chat_messages`

Observation:
- middleware is thin and correctly delegates persistence to candidate services
- identity persistence is Telegram-specific because it extracts aiogram event structure and writes `telegram_*` fields

### 3.3 Handler structure

Commands:
- `/start`, `/admin`, `/invite`, `/intro`, `/test2`: [`backend/apps/bot/handlers/common.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/common.py)
- `/iam`: [`backend/apps/bot/handlers/recruiter.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/recruiter.py)
- `/inbox`, `/find`: [`backend/apps/bot/handlers/recruiter_actions.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/recruiter_actions.py)

Callback handlers:
- Test1 answers: `t1opt:*` -> [`backend/apps/bot/handlers/test1.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/test1.py)
- recruiter/slot pickers: `pick_rec:*`, `refresh_slots:*`, `pick_slot:*` -> [`backend/apps/bot/handlers/slots.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/slots.py)
- recruiter approvals/reschedule/reject: [`backend/apps/bot/handlers/recruiter.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/recruiter.py)
- recruiter candidate actions `rc:*`: [`backend/apps/bot/handlers/recruiter_actions.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/recruiter_actions.py)
- slot assignment callbacks including legacy prefixes and compact JSON payloads: [`backend/apps/bot/handlers/slot_assignments.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/slot_assignments.py)

Free-text fallback:
- [`backend/apps/bot/handlers/common.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/common.py)
  - first checks recruiter chat mode
  - then loads bot state
  - routes candidate free text into current flow

### 3.4 State machine / FSM

There is no aiogram FSMContext/scenes layer found.

Actual state model:
- custom `StateStore` abstraction: [`backend/apps/bot/state_store.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/state_store.py)
- state payload type: `State` in [`backend/apps/bot/config.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/config.py)
- transport state keys include:
  - `flow`
  - `t1_idx`, `t1_sequence`, `test1_answers`
  - `picked_recruiter_id`, `picked_slot_id`
  - `manual_contact_prompt_sent`, `manual_availability_expected`
  - `slot_assignment_state`, `slot_assignment_id`, `slot_assignment_action_token`

Storage backends:
- in-memory
- Redis

Assessment:
- this is custom FSM/orchestration state, not domain state
- it is explicitly Telegram chat-id keyed and therefore not reusable as-is for MAX

### 3.5 Error handling / retry / deduplication / idempotency

Confirmed:
- outbound notification retry/backoff/dead-letter sits in [`backend/apps/bot/services/notification_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/notification_flow.py)
- callback signatures are signed/verified via [`backend/apps/bot/security.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/security.py)
- callback idempotency/audit exists via `telegram_callback_logs` and tests such as [`tests/test_bot_confirmation_flows.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_bot_confirmation_flows.py)
- slot assignment confirm/reschedule APIs rely on `ActionToken` one-time tokens and conflict returns

Partially confirmed / not fully generalized:
- anti-spam/rate limiting for candidate messages at Telegram bot handler level was not found as an explicit generic middleware
- no general inbound duplicate-update guard for Telegram updates was found analogous to MAX webhook dedupe

### 3.6 Logging / tracing / audit

Confirmed:
- inbound chat logging to `chat_messages`
- bot message logs and notification logs: see data dictionary and tests
- audit events in MAX flow, scheduling repair, portal session/version handling
- analytics funnel events on `/start`, screening start, etc.

Not confirmed:
- distributed tracing layer was not found
- explicit end-to-end trace/span correlation between transport, domain and outbox was not found

### 3.7 What is Telegram-specific vs reusable

Strictly Telegram-specific:
- aiogram runtime and update schema
- middleware extracting `from_user`
- `telegram_id`, `telegram_user_id`, `telegram_username`, `telegram_linked_at`
- Telegram WebApp auth: [`backend/apps/admin_api/webapp/auth.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py)
- inline keyboard / callback prefixes and `tg://`/`https://t.me` UX assumptions
- bot state keyed by Telegram user id

Already abstracted / reusable:
- delivery adapter interface
- candidate portal session + profile/screening save logic
- status transitions
- assignment-owned scheduling service
- outbox retry classification partially abstracted by channel

Mixed transport + business logic:
- Test1 orchestration in [`backend/apps/bot/services/test1_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/test1_flow.py)
  - transport prompting + validation + status updates + side effects are interwoven
- slot selection in [`backend/apps/bot/services/slot_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/slot_flow.py)
  - Telegram UX and domain mutations live together
- onboarding start in [`backend/apps/bot/services/onboarding_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/onboarding_flow.py)

Transport already separated from domain:
- MAX flow calls portal service functions directly
- public slot assignment APIs expose domain services
- messenger delivery adapters are separate from outbox orchestration

## 4. Candidate Journey Audit

### 4.1 Actual candidate entry surfaces

Confirmed entry paths:
1. Telegram `/start` with or without invite payload: [`backend/apps/bot/handlers/common.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/handlers/common.py)
2. Candidate portal signed token exchange: [`backend/apps/admin_ui/routers/candidate_portal.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py), [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
3. MAX `bot_started` webhook with optional payload/invite/token: [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py), [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
4. HH chooser / public portal entry is documented and supported in portal token model

### 4.2 Reconstructed candidate journey

Current canonical flow is hybrid:
- older Telegram-native Test1/Test2/slot flow still exists
- newer channel-agnostic journey lives in candidate portal / MAX flow

#### Text flow

```text
Entry
  -> identify/link candidate
  -> ensure active journey session
  -> profile step
  -> screening step
  -> slot selection / waiting state
  -> interview scheduled / confirmed / reschedule / decline
  -> recruiter outcome sends Test2 or moves to intro day
  -> intro day scheduling / confirmation
  -> final outcome hired / not_hired
```

### 4.3 Step list

Portal/journey step keys confirmed:
- `profile`
- `screening`
- `slot_selection`
- `status`

Telegram Test1 sequence:
- dynamic list from DB/default bank: [`backend/apps/bot/config.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/config.py)
- known fields include `fio`, `age`, `status`, `format`, `sales_exp`, `about`, `skills`, `expectations`
- conditional follow-ups:
  - `notice_period`
  - `study_mode`
  - `study_schedule`
  - `study_flex`

### 4.4 Branches and transition rules

Confirmed branches:
- invalid FIO / age / city / option format -> validation error and repeat question
- `format == "Пока не готов"` -> reject branch
- `study_schedule` hard conflict -> reject branch
- `study_flex` negative -> reject branch
- no available slots -> manual availability prompt + waiting slot path
- existing active candidate progress -> Telegram `/start` does not restart Test1, sends candidate to cabinet
- candidate reschedule -> `SlotAssignment` reschedule path or manual window prompt

### 4.5 Statuses observed in flow

Candidate pipeline statuses from [`backend/domain/candidates/status.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py):
- `lead`
- `contacted`
- `invited`
- `test1_completed`
- `waiting_slot`
- `stalled_waiting_slot`
- `slot_pending`
- `interview_scheduled`
- `interview_confirmed`
- `interview_declined`
- `test2_sent`
- `test2_completed`
- `test2_failed`
- `intro_day_scheduled`
- `intro_day_confirmed_preliminary`
- `intro_day_declined_invitation`
- `intro_day_confirmed_day_of`
- `intro_day_declined_day_of`
- `hired`
- `not_hired`

Journey statuses:
- session: `active`, `completed`, `abandoned`, `blocked`
- step: `pending`, `in_progress`, `completed`, `skipped`

### 4.6 Side effects by stage

Entry/link:
- create/update `users`
- link Telegram or MAX identity
- create/validate portal journey session
- audit events / analytics funnel events

Profile:
- persist `fio`, `phone`, `city`
- update journey step state

Screening:
- save draft answers
- on completion call `complete_screening(...)`
- may produce `TestResult` and journey events

Scheduling:
- create `SlotAssignment` or reserve legacy `Slot`
- create `ActionToken`
- enqueue outbox notifications
- update candidate status

Reschedule/cancel:
- create `RescheduleRequest`
- update assignment/slot status
- possibly save manual availability on candidate record
- enqueue recruiter/candidate notifications

### 4.7 Resume after interruption

Confirmed resume mechanisms:
- Telegram `/start` checks `resolve_candidate_activity_guard()` and redirects progressed candidate to cabinet
- portal session resume via signed token + resume cookie + session version
- MAX flow calls `ensure_candidate_portal_session()` and renders current step

Conclusion:
- recovery logic is already more journey-centric than Telegram-centric

## 5. Data Model Audit

### 5.1 Core entities

#### Candidate
- Declared in: [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py) `User`
- Purpose: central candidate aggregate
- Important fields:
  - `id`, `candidate_id`
  - `fio`, `phone`, `phone_normalized`, `city`
  - `candidate_status`, `workflow_status`
  - `responsible_recruiter_id`
  - `telegram_id`, `telegram_user_id`, `telegram_username`, `telegram_linked_at`
  - `messenger_platform`, `max_user_id`
  - `manual_slot_*`
- Writers:
  - Telegram middleware/services
  - MAX candidate flow
  - portal service
  - admin UI services
- Reads:
  - all transport layers
  - recruiter UI
  - scheduling/domain services

Telegram-bound fields:
- `telegram_id`
- `telegram_user_id`
- `telegram_username`
- `telegram_linked_at`

Multi-channel relevant fields:
- `messenger_platform`
- `max_user_id`
- `candidate_id`

Potential abstraction gap:
- no generic `messenger_identities` table; identity remains denormalized on `users`

#### CandidateInviteToken
- Declared in: [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py) `CandidateInviteToken`
- Purpose: track invite/deeplink lifecycle
- Key fields:
  - `candidate_id`
  - `token`
  - `channel`
  - `status`
  - `used_by_telegram_id`
  - `used_by_external_id`
- Role: binding Telegram/MAX entry to an existing CRM candidate

#### CandidateJourneySession / CandidateJourneyStepState / CandidateJourneyEvent
- Declared in: [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py)
- Purpose:
  - sessionized candidate journey
  - per-step progress
  - candidate-facing audit/history
- Key fields:
  - `journey_key`
  - `status`
  - `session_version`
  - `entry_channel`
  - step `step_key`, `status`, `payload_json`
- This is the strongest candidate for channel-agnostic core

#### Slot
- Declared in: [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)
- Purpose: physical/logical recruiter slot
- Important fields:
  - `recruiter_id`, `city_id`
  - `start_utc`, `duration_min`, `tz_name`, `purpose`, `status`
  - legacy candidate binding fields on slot itself
- Role: still carries candidate-held state, so scheduling core is transitional

#### SlotAssignment
- Declared in: [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)
- Purpose: candidate-to-slot assignment offer/confirm/reschedule lifecycle
- Important fields:
  - `slot_id`, `candidate_id`, `candidate_tg_id`, `candidate_tz`, `status`
  - timestamps for offer/confirm/reschedule/cancel
- Writers:
  - admin UI assignment endpoints
  - slot assignment service
  - candidate confirm/reschedule flows
- Role: intended authoritative scheduling owner

Telegram-specific leak:
- `candidate_tg_id` remains directly embedded

#### RescheduleRequest
- Declared in: [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)
- Purpose: explicit reschedule negotiation record
- Fields:
  - `slot_assignment_id`
  - `requested_start_utc`, `requested_end_utc`, `requested_tz`
  - `comment`, `status`, `alternative_slot_id`

#### ChatMessage / CandidateChatRead
- Declared in: [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py)
- Purpose: shared conversation history
- Channel support:
  - `channel`
  - `direction`
  - `status`
  - `telegram_message_id` still present for Telegram correlation
- Reusable for multi-channel messaging, but schema still has Telegram-specific columns

#### OutboxNotification / NotificationLog / MessageLog / ActionToken
- Declared in: [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)
- Purpose:
  - idempotent notification queue
  - delivery/audit logs
  - one-time action security
- These are reusable across channels and are already used that way

### 5.2 Entity relationships

Key graph:
- `User` 1:N `CandidateJourneySession`
- `CandidateJourneySession` 1:N `CandidateJourneyStepState`
- `User` 1:N `CandidateJourneyEvent`
- `User` 1:N `ChatMessage`
- `User` 1:N `TestResult`
- `User` 1:N `CandidateInviteToken` by `candidate_id`
- `SlotAssignment` N:1 `Slot`
- `RescheduleRequest` N:1 `SlotAssignment`

### 5.3 Fields needing generalization for multi-channel

High priority:
- `users.telegram_*`
- `slot_assignments.candidate_tg_id`
- `slots.candidate_tg_id`
- `chat_messages.telegram_user_id`
- any API payloads named `candidate_tg_id`

Likely MAX identity contract already used:
- `users.max_user_id`
- `users.messenger_platform`
- `candidate_invite_tokens.channel`
- `outbox_notifications.messenger_channel`

## 6. Scheduling / Interview Assignment Audit

### 6.1 Current architecture

Current scheduling model is dual:
- legacy slot-only model: `Slot` can still hold candidate ownership directly
- newer assignment-owned model: `SlotAssignment` is intended authoritative flow

Canonical docs explicitly confirm the transition:
- [`docs/architecture/candidate-state-contract.md`](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/candidate-state-contract.md)

### 6.2 Candidate scheduling sequence

```text
Recruiter/admin creates or proposes assignment
  -> create_slot_assignment() / propose_alternative()
  -> slot bound to candidate in pending state
  -> action tokens issued
  -> outbox notification queued
Candidate confirms or requests reschedule
  -> public slot assignment API or bot callback
  -> confirm_slot_assignment() / request_reschedule()
  -> assignment + slot synchronized
  -> status updates and further notifications
Recruiter approves/declines reschedule
  -> approve_reschedule() / decline_reschedule()
  -> slot replacement or release
```

### 6.3 Services and methods

Core methods in [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py):
- `create_slot_assignment`
- `confirm_slot_assignment`
- `request_reschedule`
- `begin_reschedule_request`
- `approve_reschedule`
- `propose_alternative`

Legacy slot-only helpers in [`backend/domain/slot_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_service.py):
- `reserve_slot`
- `approve_slot`
- `reject_slot`
- `confirm_slot_by_candidate`

### 6.4 Double-booking / race prevention

Confirmed protections:
- service-level integrity evaluation and conflict blocking
- action tokens for candidate actions
- row locking patterns in assignment service
- repair workflow for split-brain subset
- tests for reschedule/slot sync/manual repair

Remaining risk:
- coexistence of slot-only and assignment-owned writes means mental model is still complex
- docs explicitly say some paths remain surfaced-and-blocked, not fully repairable

### 6.5 Timezone handling

Confirmed:
- slot timezone validation in [`backend/domain/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/models.py)
- candidate timezone captured in bot state and assignments
- manual availability parsing is timezone-aware

### 6.6 MAX-specific migration risks

High:
- any MAX flow that bypasses `SlotAssignment` and touches legacy slot-only mutation paths
- any reuse of Telegram-specific `candidate_tg_id` as mandatory scheduling identity

Medium:
- candidate UX for reschedule currently assumes Telegram callback/button affordances in some branches

## 7. Integration Points

### 7.1 Internal APIs used by bot flows

Telegram / MAX / portal relevant:
- candidate portal session exchange and journey endpoints in [`backend/apps/admin_ui/routers/candidate_portal.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- public slot assignment endpoints in [`backend/apps/admin_api/slot_assignments.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/slot_assignments.py)
- recruiter/admin assignment endpoints in [`backend/apps/admin_ui/routers/slot_assignments.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments.py)
- Telegram WebApp booking APIs in [`backend/apps/admin_api/webapp/routers.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/routers.py)

### 7.2 External integrations

Confirmed:
- Telegram Bot API via aiogram
- MAX Bot API via adapter/webhook/subscription reconciliation
- HH integration and webhooks
- Redis for state store, channel health, notifications, webhook dedupe

### 7.3 Retry/fallback patterns

Confirmed:
- notification outbox retry with failure classification
- MAX webhook dedupe with Redis fallback to in-memory
- candidate portal recovery via signed token + cookie + header token

Not confirmed:
- general provider-agnostic inbound retry abstraction beyond MAX webhook dedupe

## 8. Security / Identity Audit

### 8.1 Candidate identity model

Current identity anchors:
- `candidate_id` UUID-like business id
- Telegram identity on `users.telegram_*`
- MAX identity on `users.max_user_id`
- portal token/session version
- invite token status table

### 8.2 Telegram linking

Confirmed:
- `bind_telegram_to_candidate()` validates invite token, rejects reused token by another Telegram id, merges placeholder rows if needed
- `TelegramIdentityMiddleware` may create placeholder candidate rows before Test1

Risk:
- Telegram identity is still deeply first-class in schema and services

### 8.3 MAX linking

Confirmed in [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py):
- resolves signed portal access token or invite token
- validates session version mismatch and rejects/audits
- detects duplicate MAX owner ambiguity via `max_owner_preflight`
- supports public entry when feature-flag/setting allows

This is stronger than Telegram linking in one respect: MAX linking already includes explicit ownership ambiguity checks and session-version checks.

### 8.4 Replay / duplicate / race protections

Confirmed:
- `ActionToken` one-time tokens
- invite token status and conflict states
- MAX webhook secret validation
- MAX webhook dedupe
- portal session version invalidation
- scheduling conflict blocking / repair

Not found / not confirmed:
- generic per-candidate rate limit on conversational answers
- uniform replay model shared across Telegram updates and MAX webhooks

### 8.5 What transfers to MAX vs what must be redesigned

Transferable:
- portal token/session version model
- invite token lifecycle
- action tokens for scheduling decisions
- outbox failure classification
- assignment-owned scheduling invariants

Needs redesign/generalization:
- Telegram-specific identity fields
- chat-mode switching keyed only by Telegram id
- callback data semantics and inline keyboard UX
- any service API taking `candidate_tg_id` as required actor identity

## 9. UX / Conversational Layer Audit

### 9.1 Telegram UX patterns found

- inline keyboards for single-choice answers
- callback-based recruiter/slot/meeting actions
- ForceReply for manual availability
- `/start` as recovery entry
- recruiter commands `/inbox`, `/find`, `/iam`
- WebApp buttons for cabinet opening

### 9.2 MAX UX patterns found

- button callbacks with provider payloads
- direct text entry for profile and screening
- mini-app and browser fallback buttons
- onboarding copy explicitly positions MAX as primary place for first-step questionnaire

### 9.3 Telegram-specific UX mechanisms

- aiogram callback query model
- inline keyboard formats/signatures
- Telegram WebApp auth and open-in-web-app buttons
- deep links with `/start <payload>`

### 9.4 UX risks for MAX

High:
- Telegram assumes compact inline keyboard decisioning across most short answers; MAX may differ in callback constraints and layout
- recruiter-side Telegram command UX is separate from candidate MAX UX and not generalized

Medium:
- manual availability and reschedule flows rely on text parsing; transport-independent but fragile
- some copy/templates remain explicitly Telegram-labelled in comments/docs/tests

### 9.5 What should stay 1:1 vs be adapted

Preserve 1:1:
- profile -> screening -> slot/status conceptual progression
- strict validation and non-silent recovery
- cabinet-first recovery when candidate already progressed
- action token semantics for scheduling decisions

Adapt:
- button layouts and callback payload size constraints
- entry copy and browser/mini-app fallback wording
- channel-specific re-entry instructions

## 10. Infrastructure / Config Audit

### 10.1 Relevant env/config

From [`backend/core/settings.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py) and env examples:
- Telegram:
  - `BOT_ENABLED`
  - `BOT_TOKEN`
  - `BOT_BACKEND_URL`
  - `BOT_CALLBACK_SECRET`
  - `BOT_USE_WEBHOOK`
  - `BOT_WEBHOOK_URL`
- MAX:
  - `MAX_BOT_ENABLED`
  - `MAX_BOT_TOKEN`
  - `MAX_WEBHOOK_URL`
  - `MAX_WEBHOOK_SECRET`
  - `MAX_BOT_LINK_BASE`
  - `MAX_BOT_ALLOW_PUBLIC_ENTRY`
- shared:
  - `CRM_PUBLIC_URL`
  - `CANDIDATE_PORTAL_PUBLIC_URL`
  - `REDIS_URL`
  - `SESSION_SECRET`

### 10.2 Runtime/deploy hooks

Make targets:
- `make dev-bot`
- `make dev-max-bot`
- `make dev-max-live`

MAX runtime specifics:
- FastAPI webhook app on default `8010`
- public HTTPS webhook required for real delivery
- subscription reconciliation on startup

Infra dependencies:
- PostgreSQL
- Redis strongly preferred/required for some reliability flows
- cloudflared for local live bootstrap

### 10.3 Observability

Confirmed:
- health endpoint for MAX bot
- messenger health surfaces mentioned in frontend/system code
- outbox logs, notification logs, bot message logs

Not fully confirmed:
- complete channel dashboards for all flows in one place
- end-to-end transport/domain trace IDs

## 11. Test Coverage / Gaps

### 11.1 Confirmed test coverage

Telegram bot / validation:
- [`tests/test_bot_test1_validation.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_bot_test1_validation.py)
- [`tests/test_bot_confirmation_flows.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_bot_confirmation_flows.py)
- [`tests/test_telegram_identity.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_telegram_identity.py)

MAX:
- [`tests/test_max_bot.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_bot.py)
- [`tests/test_max_candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_candidate_flow.py)
- [`tests/test_max_owner_preflight.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_max_owner_preflight.py)

Portal:
- [`tests/test_candidate_portal_api.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_candidate_portal_api.py)

Scheduling:
- [`tests/test_slot_assignment_slot_sync.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_slot_assignment_slot_sync.py)
- [`tests/test_slot_assignment_reschedule_replace.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_slot_assignment_reschedule_replace.py)
- [`tests/services/test_dashboard_and_slots.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/services/test_dashboard_and_slots.py)

Outbox / retry / channel health:
- [`tests/test_notification_retry.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_notification_retry.py)
- [`tests/test_outbox_notifications.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_outbox_notifications.py)

### 11.2 Maturity assessment

Overall maturity: medium to high for core invariants, medium for clean multi-channel boundaries.

What is well covered:
- MAX webhook secret and routing
- portal token exchange and MAX-safe launch tokens
- assignment-slot synchronization
- retry/dead-letter behavior
- Test1 validation branches

Critical gaps still visible:
- no single end-to-end contract suite that proves all candidate paths behave identically across Telegram, MAX and portal
- limited evidence of stress/concurrency tests for simultaneous slot contention across channels
- no confirmed broad property-style tests for multi-channel identity merge/relink edge cases
- recruiter-side operational flows across MAX + Telegram + portal are covered unevenly

## 12. Reuse Matrix for MAX

| Component | Where | Reuse | Why | Risk |
| --- | --- | --- | --- | --- |
| Candidate journey core | [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) | With minimal adaptation | already channel-agnostic by design | Low |
| Candidate statuses/workflow | [`backend/domain/candidates/status.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py) | Reuse as-is | domain pipeline independent of transport | Low |
| Messenger adapter contract | [`backend/core/messenger/protocol.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/protocol.py) | Reuse as-is | clean abstraction already exists | Low |
| Outbox retry/failure classification | [`backend/apps/bot/services/notification_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/notification_flow.py) | With adaptation | shared already, but implementation still bot package-centric | Medium |
| SlotAssignment scheduling service | [`backend/domain/slot_assignment_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py) | Reuse as-is | transport-independent core | Low |
| Invite token lifecycle | [`backend/domain/candidates/services.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py) | Reuse with channel-specific policy | already supports `telegram/max/generic` | Low |
| MAX webhook runtime | [`backend/apps/max_bot/app.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | Already implemented | no need to write from scratch | Low |
| MAX candidate flow | [`backend/apps/max_bot/candidate_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py) | Already implemented but needs audit hardening | current logic is substantial, but not the final abstraction boundary | Medium |
| Telegram Test1 orchestration | [`backend/apps/bot/services/test1_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/test1_flow.py) | Adapt or retire into core | mixed transport + business logic | High |
| Telegram state store | [`backend/apps/bot/state_store.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/state_store.py) | Do not reuse as-is | keyed by Telegram user id and bot flow assumptions | High |
| Telegram slot flow | [`backend/apps/bot/services/slot_flow.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/services/slot_flow.py) | Partial reuse only | contains useful validation/manual availability logic, but transport and domain are interwoven | High |
| Telegram identity model | [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py) | Needs redesign/generalization | denormalized Telegram-first schema | High |

## 13. Technical Risks for MAX Implementation

### High

- Dual scheduling model (`Slot` + `SlotAssignment`) still exists; any new MAX path can accidentally choose the wrong write owner.
- Identity model is not fully multi-channel; Telegram-specific columns and `candidate_tg_id` still leak into APIs and scheduling records.
- Telegram flow state is ephemeral and transport-bound; trying to mirror it for MAX would create a second legacy state machine instead of reusing journey core.
- Worktree state already shows MAX-related code in active modification, so repo-local truth is currently moving.

### Medium

- Messenger abstraction exists, but notification runtime still lives under `backend/apps/bot/services`, which keeps conceptual ownership Telegram-biased.
- Candidate chat schema is channel-aware, but still contains Telegram-specific fields.
- MAX public entry and relink rules are stronger than Telegram rules; behavior parity between channels is not yet obviously unified.

### Low

- Adapter bootstrap/registry pattern is clean enough.
- Health/config surfaces for MAX already exist.
- Canonical docs for candidate state and auth/token model already describe part of MAX flow.

## 14. Open Questions / Unknowns

Только то, что не удалось закрыть доказательно по live code:

- Не найден единый canonical transport-agnostic questionnaire service, который одновременно обслуживает Telegram Test1 flow и MAX/portal screening без дублирования логики.
- Не подтвержден единый anti-spam/rate-limit слой для conversational inbound updates across Telegram and MAX.
- Не подтвержден production deployment manifest/ingress for MAX webhook beyond env/config + Make targets.
- Не доказано, что все recruiter-side candidate messaging actions уже одинаково корректно маршрутизируются в Telegram и MAX во всех ветках UI.

## 15. Actionable Recommendations Before MAX Development

1. Зафиксировать один owner для candidate screening core.
   Сейчас screening split между Telegram Test1 orchestration и portal/MAX journey.

2. Выделить messenger identity abstraction.
   Нужен нормализованный multi-channel identity layer вместо разрастания `users.telegram_*` + `users.max_user_id`.

3. Добить assignment-owned scheduling migration.
   Новый MAX scope не должен писать через legacy slot-only flows.

4. Убрать transport-bound bot state из бизнес-критичных решений.
   Candidate progress должен жить в journey/session/DB, а не в Telegram-specific state store.

5. Добавить cross-channel parity tests.
   Один и тот же кандидатский сценарий должен быть доказан для `Telegram`, `MAX`, `portal`.

6. Привести API contracts к channel-agnostic naming.
   Минимизировать новые и старые поля типа `candidate_tg_id` в публичных и внутренних сервисных интерфейсах.

7. Разделить candidate transport UX и recruiter transport UX.
   Candidate MAX delivery и recruiter Telegram command UX сейчас живут в одном историческом bot-контуре.

## FINAL IMPLEMENTATION READINESS VERDICT

1. Можно ли реализовать MAX-бота как новый канал поверх существующей доменной логики?
   Да, частично. Для profile/screening/journey/status и assignment-owned scheduling ядро уже существует. Но это не "чистый новый адаптер поверх полностью готового core", потому что существенная часть candidate flow всё ещё живёт в Telegram-era orchestration.

2. Какие части уже готовы для переиспользования?
   - candidate portal / journey core
   - candidate statuses and state contract
   - messenger adapter registry/protocol
   - outbox and delivery classification
   - invite token lifecycle
   - slot assignment service
   - MAX runtime itself уже написан

3. Какие части сильнее всего завязаны на Telegram?
   - `users.telegram_*`
   - bot state store and `State`
   - Telegram handler/callback UX
   - parts of Test1 orchestration
   - some scheduling/public APIs still using `candidate_tg_id`

4. Что нужно сделать до старта разработки MAX, чтобы не строить костыли?
   - определить canonical screening core
   - запретить новые MAX writes через legacy slot-only path
   - нормализовать identity model
   - добавить cross-channel regression suite
   - убрать обязательность Telegram ids из domain/service contracts

5. Насколько проект готов к multi-channel architecture по шкале от 1 до 10?
   `6/10`

   Обоснование:
   - `+` есть reusable core и уже есть MAX implementation
   - `+` есть channel-aware outbox and journey
   - `-` identity и часть orchestration всё ещё Telegram-first
   - `-` scheduling migration не завершена

6. Какой рекомендуемый путь реализации?
   Рекомендуемый путь: `частичный рефакторинг + адаптер`.

   Детализация:
   - не нужен почти полный rewrite bot layer
   - не нужен naive быстрый адаптер "по аналогии с Telegram handlers"
   - нужен bounded refactor вокруг channel-agnostic screening/identity/scheduling contracts, затем развитие MAX поверх этого контура
