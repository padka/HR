# MAX RecruitSmart Architecture and Roadmap

Дата: `2026-04-09`

Source documents:
- [MAX_BOT_READINESS_AUDIT_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_BOT_READINESS_AUDIT_2026-04-09.md)
- [MAX_IMPLEMENTATION_SPEC_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_IMPLEMENTATION_SPEC_2026-04-09.md)
- [MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md](/Users/mikhail/Projects/recruitsmart_admin/docs/candidate_channels/MAX_COMPLEX_SOLUTION_PLAN_2026-04-09.md)

Primary platform sources:
- [MAX docs overview](https://dev.max.ru/docs)
- [MAX Bot API docs](https://dev.max.ru/docs-api)
- [MAX events FAQ](https://dev.max.ru/help/events)
- [MAX chatbot docs](https://dev.max.ru/docs/chatbots/bots-coding/library/js)
- [MAX mini apps docs](https://dev.max.ru/docs/webapps)
- [MAX bridge docs](https://dev.max.ru/docs/webapps/bridge)
- [MAX validation docs](https://dev.max.ru/docs/webapps/validation)
- [MAX channels docs/help](https://dev.max.ru/help/channels)

Important scope note:
- this document is a target architecture and roadmap
- it is not a re-audit and not a replacement for the delivery spec
- it translates the audited codebase and official MAX capabilities into a practical RecruitSmart solution model

## 1. Executive Summary

The recommended target model for RecruitSmart in MAX is:
- `MAX Bot` for entry, attribution, contact capture, reminders, notifications, and re-entry
- `MAX Mini App` for screening, scheduling, rescheduling, candidate dashboard, and onboarding artifacts
- `MAX Channels` as a supporting broadcast layer for employer brand, onboarding content, and internal or semi-internal communication
- one shared `RecruitSmart backend/domain core` as the system of record

This model fits both the current codebase and the current MAX platform shape:
- the audited codebase already has a shared candidate journey and portal core in [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- MAX runtime already exists as a webhook transport in [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- MAX candidate flow already delegates into journey/profile/screening contracts in [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- scheduling target path is already `SlotAssignment`-owned in [backend/domain/slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)

Architectural principle:
- MAX must not create a second isolated backend or a second business workflow
- MAX-specific logic should remain in adapter/transport/auth layers
- candidate workflow, scheduling rules, reminders, audit, and notifications must stay in shared backend services

Product principle:
- keep short-form, high-frequency interactions in chat
- move long-form and stateful interactions into the mini app
- use channels only where one-to-many communication is actually the right product surface

High-level target:
- Phase 1: stable `bot + mini app` production path
- Phase 2: richer dashboard, onboarding, and selective channel use
- Phase 3: strategic ecosystem features and stronger operational scale

## 2. Target Product Architecture for RecruitSmart in MAX

### 2.1 High-level architecture diagram

```text
               Acquisition / Ads / Vacancy Links / Recruiter Invites
                                      |
                                      v
                             MAX Deep Link Entry
                                      |
                                      v
     +----------------+      webhook/update      +----------------------------+
     |   MAX Bot API  | -----------------------> | backend/apps/max_bot/app.py|
     +----------------+                          +----------------------------+
                                                          |
                                                          v
                                           +-------------------------------+
                                           | backend/apps/max_bot/         |
                                           | candidate_flow.py             |
                                           +-------------------------------+
                                                          |
                              +---------------------------+----------------------------+
                              |                                                            |
                              v                                                            v
             +------------------------------------+                     +----------------------------------+
             | Shared journey / portal core       |                     | Shared messaging / outbox        |
             | backend/domain/candidates/         |                     | backend/apps/bot/services/       |
             | portal_service.py                  |                     | notification_flow.py             |
             +------------------------------------+                     +----------------------------------+
                              |                                                            |
                              v                                                            v
                 +-----------------------------+                              +--------------------------+
                 | Scheduling / SlotAssignment |                              | MAX adapter / MAX API   |
                 | backend/domain/             |                              | backend/core/messenger/ |
                 | slot_assignment_service.py  |                              | max_adapter.py          |
                 +-----------------------------+                              +--------------------------+
                              |
                              v
                 +---------------------------------------+
                 | Candidate portal APIs / session model |
                 | backend/apps/admin_ui/routers/        |
                 | candidate_portal.py                   |
                 +---------------------------------------+
                              ^
                              |
                     MAX Mini App + MAX Bridge
                              |
                              v
                      Candidate self-service UX

        Supporting surface only:
        Public/Private MAX Channels -> employer brand / onboarding / internal comms
```

### 2.2 MAX Bot

Architectural role:
- acquisition and conversational orchestration shell
- source-aware entry point
- lightweight qualification surface
- service notification surface
- re-entry and reminder surface

Current live-code anchor:
- runtime: [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- flow orchestration: [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)

Events and entry points it should handle:
- `bot_started`
- `message_created`
- `message_callback`
- signed deep-link or invite-based starts
- controlled public entry only when explicitly enabled

What remains in bot permanently:
- vacancy/source/city-aware entry
- basic orientation and trust-building copy
- `requestContact` prompt or equivalent contact CTA
- a short qualification step only where chat UX is superior
- reminders to resume profile, screening, or scheduling
- confirmations and outcome notifications
- deep-link handoff into the mini app

What bot should not take on:
- long forms
- complex scheduling calendars
- dense dashboard state
- document-heavy onboarding
- any candidate progress model that bypasses shared journey/session state
- channel-specific business rules duplicating portal or scheduling core

How bot integrates with backend:
- receives webhook updates in [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- verifies webhook secret and deduplicates inbound updates
- delegates to [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)
- `candidate_flow` resolves candidate identity, persists inbound chat messages, and calls portal/journey helpers in [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- outbound delivery goes through the MAX messenger adapter in [backend/core/messenger/max_adapter.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/max_adapter.py)

### 2.3 MAX Mini App

Architectural role:
- stateful candidate self-service surface inside MAX
- primary transactional UI for profile, screening, scheduling, and dashboard

Recommended candidate flows that should live there:
- full profile capture
- long-form screening/questionnaire
- slot selection
- booking confirmation
- reschedule and cancel
- current interview card and status
- office instructions, checklist, and onboarding artifacts

Recommended screen/state model:
- `Start / Resume`
- `Profile`
- `Screening`
- `Scheduling`
- `Interview Confirmed`
- `Reschedule / Cancel`
- `Candidate Dashboard`
- `Visit Preparation / Onboarding`
- `Support / Contact / FAQ`

How mini app should launch:
- from bot CTA with `open_app`
- via signed `startapp` payload built by shared portal service:
  - [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
  - `sign_candidate_portal_max_launch_token(...)`
  - `build_candidate_public_max_mini_app_url_async(...)`

How mini app should connect to backend:
- do not use legacy Telegram mini app routes under `/api/webapp/*` as the long-term MAX path
- do use shared candidate portal APIs under `/api/candidate/*` in [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- add a MAX-specific auth/validation facade around `WebAppData`, but keep candidate session exchange and journey logic in the existing candidate portal/session model

How mini app returns user into bot-led flow:
- it does not transfer ownership of the candidate to the bot; backend remains authoritative
- the bot remains subscribed to reminders and service notifications
- bot messages should deep-link the candidate back to the exact mini app state
- the mini app itself should expose “back to chat” and “continue later” flows, but without moving business logic into the chat layer

### 2.4 Channels

Architectural role:
- one-to-many supporting surface
- not the transactional surface for candidate actions

Good channel use cases:
- employer brand and vacancy campaigns
- public recruiting content and office news
- onboarding reminders or general cohort content
- private office or cohort announcements
- internal coordinator or branch communication

Poor channel use cases:
- per-candidate scheduling state
- confidential or mutable candidate actions
- identity-sensitive workflow steps
- anything requiring strong authz, replay safety, or exact idempotent writes

Recommended channel model:
- `Public channel`: employer brand, recruiting campaigns, public office content
- `Private channel(s)`: onboarding cohorts, internal office/city coordination, semi-internal communications

### 2.5 Backend / Domain Layer

What must remain shared and channel-agnostic:
- candidate identity binding rules
- candidate journey/session and step state
- candidate status/workflow progression
- scheduling rules and write-path ownership
- action tokens, reminder rules, outbox, and delivery classification
- audit, analytics, and observability

Current live-code anchors:
- journey/session core: [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)
- status/workflow: [backend/domain/candidates/status.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/status.py), [backend/domain/candidate_status_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidate_status_service.py)
- scheduling core: [backend/domain/slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py)
- delivery abstraction: [backend/core/messenger/protocol.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/protocol.py), [backend/core/messenger/registry.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/registry.py)

Required anti-corruption / adapter layers for MAX:
- `MAX webhook adapter`
  - inbound update verification, dedupe, normalization
- `MAX mini app auth adapter`
  - validate `WebAppData`
  - convert MAX launch context into a trusted backend session exchange
- `MAX messenger delivery adapter`
  - outbound send, callback answer, subscription management
- `MAX deep-link launcher`
  - generate signed `startapp` and invite-aware entry links without embedding domain logic in the client

## 3. Surface Map: Bot vs Mini App vs Channels

### Table 1. Surface Fit Matrix

| Scenario | Best Surface | Why | UX Risk | Tech Risk |
| --- | --- | --- | --- | --- |
| Entry via deep link | Bot | Best first-touch conversational surface, source-aware and low friction | Low | Low |
| Source attribution | Bot + Backend | Deep-link payload is native; backend stores attribution | Low | Medium if payload design is sloppy |
| Candidate identification | Bot + Backend, then Mini App + Backend | Bot can bind candidate early; mini app needs validated context | Medium | High if identity paths diverge |
| Contact capture | Bot first, Mini App fallback | Native share/contact prompt reduces typing | Low | Medium due to client support validation |
| Short qualification questions | Bot | Best for yes/no or short answers | Medium if too many steps | Low |
| Long-form screening | Mini App | Better validation, progress, review, and recovery | Low-Medium | Medium |
| Scheduling | Mini App | Better for many slots, conflicts, and confirmation states | Low | Medium-High due to scheduling integrity |
| Rescheduling | Mini App | Better for clarity and conflict handling | Low | High if write-path is duplicated |
| Cancellation | Mini App | Better confirmation semantics and state explanation | Low | Medium |
| Candidate dashboard | Mini App | Persistent self-service and re-entry surface | Medium if overloaded | Medium |
| Reminders | Bot | Best async prompt channel | Low | Low |
| Office instructions | Mini App, optional Channel support | Needs structure, maps, checklist, maybe documents | Low | Low-Medium |
| Onboarding artifacts | Mini App, optional Channels | Candidate-specific state in app; cohort content in channel | Medium | Medium |
| Employer brand / recruiting content | Public Channel | Broadcast-native | Medium if overused for transactions | Low |
| Internal communication | Private Channel | Good for controlled one-to-many comms | Medium | Low |
| Scheduling repair / integrity handling | Backend-only + Admin surfaces | Not a candidate-facing action | Low | High |

Additional guidance:
- if the action is personalized, mutable, and stateful, default to `Mini App`
- if the action is short, interruptive, and time-sensitive, default to `Bot`
- if the action is broadcast, low-precision, and one-to-many, default to `Channel`
- if the action is integrity-sensitive and invisible to the candidate, keep it `Backend-only`

## 4. End-to-End Candidate Journey Architecture

### 4.1 Candidate journey flow

```text
Deep link / source attribution
  -> MAX Bot entry
  -> contact capture
  -> quick qualification
  -> handoff to MAX Mini App
  -> profile + screening
  -> scheduling
  -> confirmation
  -> reminders / re-entry
  -> visit prep / onboarding
  -> post-interview follow-up
```

### 4.2 Stage-by-stage journey architecture

| Stage | Surface | Backend action | Entity updates | User-visible output | Failure modes | Recovery path |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Entry | Bot | Resolve start payload, source attribution, candidate preflight | `User`, audit, analytics | Personalized welcome | Invalid or stale invite | Service message + fresh link path |
| 2. Primary identification | Bot | Link MAX owner to existing candidate or create controlled public draft | `User.max_user_id`, `messenger_platform`, audit | “You are linked / continue” | Owner conflict, invite conflict | Deterministic rejection + support/retry path |
| 3. Contact capture | Bot | Save phone/contact to profile draft | `CandidateJourneyStepState(profile)` or direct `User.phone` via shared service | Contact saved confirmation | Unsupported capability, candidate refusal | Manual input fallback |
| 4. Quick qualification | Bot | Save short answers, decide whether to continue | journey step state, analytics | short-form next step | invalid answer, interruption | prompt again or handoff to mini app |
| 5. Mini app session exchange | Mini App | Validate `WebAppData`, exchange signed launch token, create/resume portal session | `CandidateJourneySession`, session payload, audit | Dashboard / profile screen opens | invalid launch data, stale token | relaunch from bot / fresh link |
| 6. Profile completion | Mini App | Validate and save profile | `User`, `CandidateJourneyStepState(profile)` | progress and next CTA | validation errors | field-level retry |
| 7. Screening | Mini App | save draft, complete screening, update next step | `QuestionAnswer`, `TestResult`, step state, analytics | completion + scheduling CTA | invalid payload or stale session | resume from dashboard |
| 8. Scheduling | Mini App | load availability, reserve/confirm through canonical backend path | `SlotAssignment` and/or guarded slot state | interview time selected | slot conflict, integrity conflict | refresh slots or manual review message |
| 9. Confirmation | Bot + Mini App | enqueue/send confirmation and render current booking card | outbox, `ChatMessage`, journey status | bot confirmation + dashboard card | delivery failure | outbox retry + fallback browser path |
| 10. Reschedule / cancel | Mini App | request reschedule or cancel via shared path | `RescheduleRequest`, `SlotAssignment`, journey events | new state or updated dashboard | duplicate write, stale token, conflict | idempotent retry or support message |
| 11. Reminders and re-entry | Bot | schedule and send reminder with exact CTA back to app | outbox, audit, analytics | reminder message | message delivery failure | retry / fallback browser URL |
| 12. Visit preparation | Mini App, optional Channels | show address, checklist, FAQ, instructions | dashboard payload, optional content refs | preparation screen | missing content | fallback to bot/browser link |
| 13. Post-interview | Bot + Mini App | status updates, next-step nudges | candidate status, messages, analytics | outcome and next step | stale status or no next action | dashboard refresh / recruiter action |

### 4.3 Bot-to-mini-app handoff flow

```text
Candidate taps CTA in bot
  -> bot message includes signed MAX launch URL (startapp=mx1...)
  -> MAX opens mini app
  -> mini app receives WebAppData + start params
  -> backend validates WebAppData
  -> backend parses signed mx1 launch token
  -> backend exchanges into candidate portal session
  -> mini app loads exact current journey state
  -> bot remains async reminder surface
```

### 4.4 Scheduling confirmation / reschedule flow

```text
Mini App -> /api/candidate/slots/reserve
  -> shared portal/journey guard
  -> scheduling integrity check
  -> SlotAssignment-owned mutation where available
  -> booking response
  -> dashboard refresh
  -> bot notification queued

Reschedule:
Mini App -> /api/candidate/slots/reschedule
  -> session/token validation
  -> integrity guard
  -> request reschedule / confirm alternative
  -> recruiter/admin path if required
  -> bot and dashboard reflect updated state
```

## 5. API and Integration Map

### 5.1 API boundaries

The target architecture has five critical API boundaries:
- `MAX Bot API -> RecruitSmart webhook`
- `MAX Mini App client -> Candidate portal APIs`
- `MAX Bridge/WebAppData -> MAX auth validation facade`
- `Candidate portal / journey -> Scheduling core`
- `RecruitSmart outbox -> MAX Bot API`

### Table 2. API Boundary Map

| Boundary | Producer | Consumer | Data / Event | Auth Model | Notes |
| --- | --- | --- | --- | --- | --- |
| MAX webhook | MAX Bot API | [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | `bot_started`, `message_created`, `message_callback` | webhook secret header | Deduped by callback/message/body hash |
| MAX runtime to flow core | [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py) | [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py) | normalized event payloads | internal call | Transport-only shell |
| MAX flow to shared journey | [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py) | [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) | profile/screening/session progression | internal call | Shared business layer |
| MAX mini app auth | Mini App + MAX Bridge | target MAX auth facade | `WebAppData`, platform, version, start params | HMAC validation against bot token | Required before privileged session exchange |
| Session exchange | Mini App | [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py) | signed `mx1...` launch token | signed token + validated MAX context | Prefer reuse of `/api/candidate/session/exchange` model |
| Candidate journey read | Mini App | [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py) | `/journey` | candidate portal session | Source of dashboard state |
| Profile/screening mutations | Mini App | [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py) | `/profile`, `/screening/save`, `/screening/complete` | candidate portal session | Shared path for MAX and web portal |
| Scheduling mutations | Mini App | [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py) | `/slots/reserve`, `/slots/confirm`, `/slots/cancel`, `/slots/reschedule` | candidate portal session + business guards | Preferred path for MAX |
| Legacy Telegram webapp API | Telegram mini app | [backend/apps/admin_api/webapp/routers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/routers.py) | `/api/webapp/*` | Telegram initData auth | Legacy boundary; not target core for MAX |
| Slot assignment callbacks | Bot/Admin/portal | [backend/apps/admin_api/slot_assignments.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/slot_assignments.py) | confirm / request-reschedule | action token | Shared assignment path |
| Outbox delivery | Notification worker | [backend/core/messenger/max_adapter.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/messenger/max_adapter.py) | send message / answer callback | bot token in Authorization | Shared delivery path |

### 5.2 Integration map

Backend integrations participating in MAX target architecture:
- MAX Bot API and subscription management
- candidate portal session and journey APIs
- scheduling / slot assignment services
- analytics funnel events
- outbox notification worker
- admin/recruiter surfaces for scheduling, manual repair, and status progression

### 5.3 Webhook + backend + mini app auth flow

```text
MAX Bot API
  -> POST /webhook
  -> webhook secret verified
  -> dedupe check
  -> candidate_flow resolves candidate / invite / owner preflight
  -> candidate_flow emits message with signed mini app URL

Candidate opens mini app
  -> MAX client passes WebAppData + startapp payload
  -> frontend sends WebAppData + signed launch token to backend
  -> backend validates WebAppData freshness and signature
  -> backend parses signed mx1 launch token
  -> backend creates/resumes candidate portal session
  -> frontend uses session to call /api/candidate/*
```

### 5.4 Implementation implications

Required API posture for the target model:
- keep MAX bot runtime extremely thin
- keep candidate mutations under the shared candidate portal/session APIs
- do not route MAX mini app traffic through `/api/webapp/*` beyond temporary compatibility needs
- add a dedicated MAX auth dependency/facade instead of embedding MAX bridge validation logic into unrelated handlers

## 6. Data / Identity / State Model for MAX

### 6.1 Target data model posture

The target model extends the existing shared candidate model. It does not introduce a separate MAX-only candidate schema.

Shared entities already suitable for MAX:
- `User` as candidate record
- `CandidateInviteToken`
- `CandidateJourneySession`
- `CandidateJourneyStepState`
- `CandidateJourneyEvent`
- `SlotAssignment`
- `RescheduleRequest`
- `ChatMessage`
- `OutboxNotification`, `NotificationLog`, `ActionToken`

Current live-code anchors:
- candidate entities: [backend/domain/candidates/models.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py)
- shared portal/journey helpers: [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py)

### 6.2 Identity model

Recommended identity model for MAX:
- canonical candidate identity remains RecruitSmart-side: `User.id` and `User.candidate_id`
- MAX-specific owner identity is a channel binding, currently represented by `User.max_user_id`
- channel preference / last reliable surface is currently represented via `User.messenger_platform`
- invite and launch tokens provide controlled linkage and continuation

Recommended conceptual abstraction:
- `MessengerIdentity` should be treated as a logical concept spanning:
  - platform
  - external owner id
  - linkage timestamp
  - source of binding
- current physical schema can remain transitional, but new MAX work should behave as if this abstraction already exists

### 6.3 State model

State that belongs in shared backend:
- candidate status
- journey current step
- profile/screening draft state
- scheduling state
- reschedule or cancellation intent
- reminder eligibility and notification history
- audit and analytics trail

State that may be channel-specific:
- `max_user_id`
- source channel values such as `max_bot` or `max_app`
- MAX launch tokens and webhook dedupe keys
- client-only UI hints in device storage if later adopted

State that must not become MAX-only business truth:
- candidate qualification progression
- scheduling ownership
- booking confirmation state
- onboarding completion state
- recruiter-visible status transitions

### 6.4 Deep-link and attribution context

Recommended storage model:
- keep deep-link payload compact and signed
- resolve full attribution context server-side
- store normalized fields like:
  - `entry_channel`
  - `source_channel`
  - `campaign`
  - `vacancy_id`
  - `city_id`
  - `invite_token_id` where applicable

These belong in shared journey/session or analytics context, not in MAX-only ad hoc tables.

### 6.5 Session and resume model

Current reusable pieces:
- signed candidate portal tokens
- signed MAX launch tokens with prefix `mx1`
- portal session payload and versioning
- resume cookie/session flow in [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)

Target model:
- mini app entry should always map into the existing journey/session model
- stale launch or stale session version must reject cleanly and force a fresh launch
- bot reminders should link back to the latest valid session entry

### 6.6 Scheduling state

Target model:
- scheduling remains owned by shared scheduling services
- `SlotAssignment` is the target long-term write authority
- legacy slot-only paths remain transitional and guarded, not the architectural goal for MAX

### 6.7 Candidate dashboard and notification state

Candidate dashboard state should be assembled from shared backend facts:
- candidate status
- current journey step
- active interview slot / assignment
- reschedule status
- checklist and preparation content
- message/contact history where appropriate

Notification state should remain in shared outbox/logging tables, not in MAX client storage.

## 7. Security Architecture

### 7.1 Security model overview

The target security model for MAX has four layers:
- `Webhook trust`
- `Mini app launch trust`
- `Business authorization`
- `Idempotent and auditable mutation control`

### 7.2 Webhook security model

Current live-code anchor:
- [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)

Required controls:
- verify `X-Max-Bot-Api-Secret`
- reject webhook processing if production secret is missing
- dedupe inbound events by callback id, message id, or body digest
- log audit events for critical rejects
- keep the webhook runtime transport-thin

Production posture:
- use HTTPS
- use the stricter official guidance for webhook infra readiness
- do not rely on loosely documented certificate behaviors

### 7.3 Mini app auth and validation

Official MAX posture:
- validate `WebAppData` on the server
- check signature/HMAC
- enforce `auth_date` freshness

Target backend design:
- create a MAX-specific auth dependency/facade analogous in role to [backend/apps/admin_api/webapp/auth.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/auth.py), but for MAX
- this layer should:
  - extract `WebAppData`
  - validate signature with current MAX bot token
  - check freshness window
  - expose normalized MAX user/chat context to the application layer

Important rule:
- validated MAX client context establishes trust in the client launch context
- it does not replace business authorization for candidate actions

### 7.4 Identity binding safeguards

Current live-code anchor:
- [backend/apps/max_bot/candidate_flow.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/candidate_flow.py)

Required safeguards:
- invite-based or signed-launch linkage remains the preferred path
- public entry stays feature-flagged
- duplicate MAX owner conflicts reject deterministically
- session version mismatches invalidate stale launches
- binding changes are auditable

### 7.5 Replay / duplicate / idempotency strategy

Controls already aligned with target:
- webhook dedupe in MAX runtime
- signed `mx1` launch token with TTL
- portal session version checks
- one-time or TTL-bound action tokens in slot assignment flows
- outbox-based delivery with retries

Required architectural rule:
- every candidate-facing mutation must either be idempotent or guarded by conflict-safe domain logic

### 7.6 Token model for mini app backend access

Recommended token stack:
- `WebAppData` proves launch context
- signed MAX launch token (`mx1...`) proves intended candidate/journey session handoff
- portal session or equivalent session token proves subsequent candidate API access
- action tokens prove sensitive scheduling or callback actions where required

Do not do:
- do not use raw `WebAppData` as the only authorization primitive for slot mutations
- do not let the frontend synthesize candidate identity from local client state

### 7.7 Privacy model for a public/discoverable bot

Given official MAX bot discoverability:
- the bot must be assumed publicly reachable
- all private business actions must be gated by backend authorization
- public entry must be controlled and observable
- candidate-specific content should open only after identity and session checks

### 7.8 Audit and incident visibility

Target requirements:
- audit linkage events
- audit session-version rejects
- audit scheduling conflicts and integrity blocks
- log outbound delivery failures with platform classification
- expose readiness via health and messenger health surfaces

### 7.9 Security assumptions

- RecruitSmart controls the MAX bot token securely
- MAX `WebAppData` validation matches reviewed official docs
- shared backend remains the only source of truth
- public candidate portal and mini app URLs are HTTPS

### 7.10 Known open points

- exact support matrix for some advanced bridge capabilities remains a hands-on validation item
- a dedicated MAX mini app auth dependency was not confirmed as already implemented in live code
- rollout requires business/platform verification and moderation beyond engineering readiness

### 7.11 Required smoke validations before production

- webhook secret reject path
- duplicate webhook delivery path
- stale `WebAppData` rejection
- stale `mx1` launch token rejection
- session version mismatch rejection
- invite conflict / owner conflict path
- slot mutation conflict path
- outbox retry on temporary MAX delivery failure

## 8. Client Capability Validation Plan

### Table 3. Client Capability Validation Matrix

| Capability | Client Types | Expected Behavior | Test Method | Blocking? | Fallback |
| --- | --- | --- | --- | --- | --- |
| `requestContact` | iOS, Android, Desktop, Web | user can share contact or decline cleanly | manual smoke with candidate test accounts | Yes for UX, no for launch | manual phone entry |
| `open_app` / `startapp` handoff | iOS, Android, Desktop, Web | bot CTA opens exact mini app state | end-to-end bot -> app smoke | Yes | browser portal link |
| Deep-link entry | iOS, Android, Desktop, Web | vacancy/source link lands in right bot/app context | signed link matrix test by source | Yes | generic start + server-side source fallback |
| BackButton | iOS, Android, Desktop, Web | returns within app flow without data loss | manual navigation test | Yes for polish, no for launch | in-app nav controls |
| Closing confirmation | iOS, Android, Desktop, Web | warns before losing unfinished progress | interrupt-flow smoke | Yes for long-form UX | server draft autosave + reopen |
| Notification continuity bot -> app | iOS, Android, Desktop, Web | bot reminder opens exact next step in app | end-to-end reminder smoke | Yes | browser portal link |
| Share / openLink / openMaxLink | iOS, Android, Desktop, Web | opens supported target or share sheet | manual smoke | No | copy link CTA |
| DeviceStorage | iOS, Android, Desktop, Web | stores non-critical UI hints only | targeted client smoke | No | backend session state |
| SecureStorage | iOS, Android, Desktop, Web | stores local convenience data if supported | targeted client smoke | No | backend session state |
| QR / code reader | iOS, Android, Desktop, Web | scanner opens and returns payload | capability-specific smoke | No | manual code entry |
| Geolocation / office link | iOS, Android, Desktop, Web | opens map/location assistance | manual smoke | No | external map link |
| Bot callback confirmation | iOS, Android, Desktop, Web | callback press acknowledged, no double-fire confusion | duplicate press smoke | Yes | send plain text confirmation |

Validation rules:
- Phase 1 blockers are only the capabilities needed for the core funnel
- non-blocking capabilities can ship later or degrade gracefully
- unsupported or inconsistent advanced client APIs must never become hard dependencies for the funnel

## 9. Product Roadmap: Wave 1 / Wave 2 / Wave 3

### 9.1 Roadmap principles

- Wave 1 optimizes for safe production value
- Wave 2 optimizes for reduced friction and stronger self-service
- Wave 3 optimizes for ecosystem depth and operational leverage

### Table 4. Roadmap Matrix

| Wave | Feature Set | Value | Complexity | Dependency | Launch Readiness Criteria |
| --- | --- | --- | --- | --- | --- |
| Wave 1 | bot entry, attribution, contact capture, mini app screening, mini app scheduling, candidate dashboard lite, reminders | High | Medium | webhook readiness, MAX auth facade, shared candidate APIs, scheduling integrity guards | verified bot/app handoff, stable session exchange, critical smoke tests pass, moderation/account ready |
| Wave 2 | richer dashboard, office instructions, onboarding checklist, selective channels, share/maps, lower-friction resume UX | High | Medium | Wave 1 stability, content ownership, client capability validation | drop-off reduction visible, support load stable, channels owned operationally |
| Wave 3 | QR/check-in, document flows, advanced internal workflows, ecosystem scale features | Medium-High | Medium-High | validated operational need, legal/policy alignment, mature observability | proven use-case fit, non-core capabilities validated, ops ready |

### 9.2 Wave 1

Goal:
- deliver the minimal safe and valuable MAX solution

Feature set:
- bot deep-link entry and source attribution
- candidate binding and contact capture
- mini app screening/profile completion
- mini app scheduling, reschedule, cancel
- candidate dashboard lite
- bot reminders and notifications

Dependencies:
- shared candidate portal APIs
- MAX launch token flow
- MAX mini app auth/validation layer
- MAX webhook subscription and health readiness
- assignment-owned scheduling path where required

Blockers:
- business/platform verification
- webhook secret and public HTTPS readiness
- unresolved scheduling integrity conflicts
- missing MAX client smoke validation for core handoff capabilities

Success criteria:
- candidate can go from MAX entry to booked interview without leaving MAX
- parity with Telegram/portal core outcomes
- no duplicate side effects on duplicate updates
- re-entry works after interruption

### 9.3 Wave 2

Goal:
- reduce friction and improve candidate self-service

Feature set:
- richer dashboard
- office instructions and preparation surfaces
- selective public/private channel use
- optional share/maps helpers
- stronger reminder and re-entry precision

Dependencies:
- stable Wave 1 metrics
- content governance
- validated client support for selected capabilities

Risks:
- dashboard bloat
- channels without clear ownership
- too many optional surfaces confusing the candidate

Success criteria:
- improved screening completion
- improved scheduling completion
- higher reminder-to-return conversion
- stable support load

### 9.4 Wave 3

Goal:
- strategic ecosystem expansion and operational leverage

Feature set:
- QR or code-based office check-in
- optional document intake
- internal coordinator flows
- advanced client capabilities where justified

Dependencies:
- demonstrated operational value
- policy/legal sign-off
- better observability and support procedures

Risks:
- overcomplicating the candidate experience
- building features without strong funnel impact

Success criteria:
- measurable operational efficiency gain
- no regression in core conversion metrics

## 10. Conversion-Oriented Recommendations

### 10.1 Where MAX can reduce candidate friction

Highest-value friction reducers:
- deep-link entry with source-aware welcome
- `requestContact` instead of manual phone typing
- mini app for long forms instead of callback-heavy chat
- exact re-entry links back into the current journey step
- bot reminders that point to the precise next action

### 10.2 How bot and mini app should work together

Recommended collaboration model:
- bot gets the candidate started quickly
- bot avoids asking for too much in chat
- mini app takes over as soon as the flow becomes stateful or form-heavy
- bot remains the interrupt/resume surface

This prevents two common funnel failures:
- the chat becomes too long and brittle
- the mini app loses the candidate because it has no async recovery surface

### 10.3 Short-form vs long-form UX rule

Use `Bot` for:
- yes/no questions
- one-tap decisions
- reminders
- notifications
- “continue now” nudges

Use `Mini App` for:
- more than a few fields
- any step requiring review or editing
- slot selection
- multi-state journey visibility
- reschedule/cancel explanations

### 10.4 Re-entry recommendations

Required re-entry patterns:
- inactivity reminders
- stale-session friendly messaging
- exact-state relaunch into mini app
- dashboard as persistent “where am I now?” surface

### 10.5 Reminder and confirmation guidance

Use reminders when:
- screening is started but incomplete
- scheduling is available but incomplete
- interview is approaching
- reschedule is pending response

Use confirmations when:
- contact is saved
- screening is completed
- interview is booked
- reschedule or cancel is accepted

### 10.6 Fallback paths

Every critical step should have a fallback:
- contact share unavailable -> manual entry
- open_app unavailable -> browser portal URL
- mini app resume fails -> fresh bot CTA
- scheduling conflict -> refreshed slots or human review message

## 11. Rollout, Governance, and Ownership

### 11.1 Rollout plan

Feature flags:
- MAX bot public entry
- MAX mini app screening
- MAX mini app scheduling
- MAX dashboard
- channel invitations or channel-linked onboarding

Rollout stages:
- internal testing
- hidden pilot cohort
- controlled production pilot
- broader rollout by vacancy/city/source

### 11.2 Governance and ownership

Recommended ownership map:
- Backend/platform owner: candidate APIs, scheduling contracts, auth, audit, observability
- Bot/channel owner: bot copy, reminders, channel operations, deep-link taxonomy
- Mini app/frontend owner: UX, screen flows, MAX Bridge integration
- Product owner: funnel priorities, phase decisions, success metrics
- Operations/recruiting owner: content, onboarding materials, cohort/channel governance

### 11.3 Observability before launch

Must be ready before rollout:
- MAX bot health and subscription visibility
- candidate session exchange errors
- webhook duplicate/reject metrics
- scheduling conflict metrics
- outbox delivery failure metrics
- funnel analytics from entry through booking

### 11.4 Rollback plan

If MAX mini app flow degrades:
- keep bot alive
- disable mini app scheduling flag
- fall back to browser portal where supported
- keep Telegram/web portal flows unaffected

If MAX webhook flow degrades:
- disable public entry
- preserve existing candidate portal/browser fallback
- do not mutate shared workflow via half-working alternate paths

### 11.5 Change management for future MAX iterations

Rules:
- all new MAX features must declare surface ownership first
- no MAX-only business rules without shared backend justification
- validate advanced client capabilities before product commitment
- keep channel usage optional and content-owned

## 12. Risks, Constraints, and Open Questions

### 12.1 Core risks

- dual scheduling model remains a transitional complexity until fully retired
- mini app auth layer for MAX needs to be explicit and clean, not bolted onto Telegram auth
- public bot discoverability increases the importance of backend authorization
- advanced bridge support is not fully proven across all client types

### 12.2 Platform constraints that shape the architecture

- production webhook expectation
- organization verification and moderation
- deep-link payload limits
- bot discoverability
- no guarantee that every advanced capability behaves identically on every client

### 12.3 Open questions

- what exact MAX client coverage RecruitSmart needs for pilot geography and devices
- whether channels will have clear operational ownership in Wave 2
- whether any post-interview or onboarding flows require document capture inside MAX

### 12.4 No-go areas

- no second business workflow just for MAX
- no MAX mini app routing through legacy Telegram-only APIs as the target architecture
- no channel-driven transactional logic
- no client-side source of truth for candidate or scheduling state

## 13. Final Recommendation

RecruitSmart should target a durable multi-surface MAX solution, but not a platform rewrite.

Recommended architecture:
- `Bot` as entry and asynchronous orchestration surface
- `Mini App` as transactional self-service surface
- `Channels` as optional support/distribution surface
- one shared backend/domain core as the single source of truth

The most important architectural call is this:
- MAX mini app should sit on top of the shared candidate portal/journey/session model in [backend/domain/candidates/portal_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) and [backend/apps/admin_ui/routers/candidate_portal.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py)
- it should not become a second, MAX-only business backend

This gives the best balance of:
- speed
- UX quality
- multi-channel consistency
- operational safety

## FINAL TARGET MODEL FOR RECRUITSMART IN MAX

1. What target solution model is recommended?

`MAX Bot + MAX Mini App + optional MAX Channels`, backed by one shared RecruitSmart domain core.

2. What should remain in the bot permanently?

- deep-link entry
- source attribution
- contact capture prompt
- lightweight qualification
- reminders
- service notifications
- exact re-entry CTAs

3. What should live in the mini app?

- profile completion
- screening
- slot selection
- reschedule and cancel
- dashboard and current stage
- office instructions, checklist, and onboarding artifacts

4. Which channel functions are actually useful, and which are not?

Useful:
- employer brand
- campaigns
- cohort or office announcements
- internal or semi-internal distribution

Not useful as core flow:
- secure candidate actions
- scheduling ownership
- confidential candidate-specific workflow

5. Which platform constraints shape the architecture the most?

- production webhook model
- public/discoverable bot
- moderation and partner verification
- deep-link payload limits
- incomplete certainty around advanced client capability support

6. Which roadmap gives the best balance of speed, UX, and robustness?

- Wave 1: `bot + mini app` core funnel
- Wave 2: richer self-service and selective channels
- Wave 3: strategic ecosystem features only where operational value is proven

7. What must be manually validated before full rollout?

- `requestContact`
- bot-to-mini-app handoff
- deep-link entry and resume
- `WebAppData` validation path
- stale launch token and stale session rejection
- reminder-to-app continuity
- duplicate webhook handling
- scheduling conflict behavior
