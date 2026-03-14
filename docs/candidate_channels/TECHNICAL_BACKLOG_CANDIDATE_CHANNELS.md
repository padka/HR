# Technical Backlog: Candidate Channels

## Prioritization Logic

- `P0`: required to remove hard Telegram dependency
- `P1`: strong leverage, needed for resilient omnichannel ops
- `P2`: optimization or secondary expansion

## MVP Backlog Slice

### P0 first slice

1. Candidate identity and channel account model
2. Journey session persistence
3. Candidate portal auth
4. Web screening flow
5. Web slot booking flow
6. Status / next-action API
7. SMS/email deep-link fallback
8. Channel-aware analytics

## Backend

### Identity and profile

- `P0` Create `candidate_channel_accounts` table and domain service.
- `P0` Create `candidate_access_tokens` table/service for one-time links and resume tokens.
- `P0` Add dedup rules by phone/email/channel account.
- `P0` Refactor candidate lookup helpers to accept `candidate_id` first, not `telegram_id` first.
- `P1` Add admin merge service for ambiguous duplicate candidates.
- `P1` Add source attribution fields for campaign/channel entry.

### Journey engine

- `P0` Create `candidate_journey_sessions` and `candidate_journey_step_states`.
- `P0` Implement `CandidateJourneyEngine` service with start/get/save/complete/resume methods.
- `P0` Introduce step registry for `profile_intake`, `test1`, `slot_selection`, `status_center`.
- `P0` Move Test1 persistence from bot-only finalizer into shared journey service.
- `P1` Add journey versioning and migration rules between versions.
- `P2` Add admin tooling for configurable journey definitions.

### Screening/form engine

- `P0` Extract current Test1 config into reusable screening schema.
- `P0` Reuse existing partial validation in channel-neutral service.
- `P0` Add autosave answer API.
- `P1` Normalize screening runs in new tables instead of relying only on `TestResult`.
- `P1` Support richer question types and branching metadata for web renderer.

### Scheduling

- `P0` Create candidate-neutral scheduling facade over `reserve_slot`, `SlotAssignment`, `RescheduleRequest`.
- `P0` Add portal endpoints for reserve/confirm/cancel/reschedule.
- `P0` Change reminder scheduling to resolve candidate by `candidate_id` + preferred channel.
- `P1` Move more flows from legacy slot callbacks to `SlotAssignment` action tokens.
- `P1` Add manual scheduling request API for “no suitable slots”.

### Statuses and projections

- `P0` Introduce external candidate-facing status projection.
- `P0` Refactor status transition service to accept `candidate_id`.
- `P0` Keep legacy `CandidateStatus` as projection for CRM compatibility.
- `P1` Add status timeline table or event projection for audit/history.

### Notifications

- `P0` Add notification orchestration service with preferred channel + fallback chain.
- `P0` Add SMS adapter.
- `P0` Add email adapter.
- `P0` Ensure each critical notification includes deep link token.
- `P1` Add delivery-attempt lineage table for per-channel observability.
- `P1` Add circuit breaker / unreachable-candidate state surfaced to CRM.
- `P2` Add push notifications for installed PWA.

### Communication layer

- `P1` Refactor CRM outbound chat sender to route through channel adapters, not Telegram-only bot service.
- `P1` Add portal-visible candidate updates API.
- `P1` Add candidate reply endpoint from portal thread.
- `P2` Add omnichannel thread stitching rules across portal/messenger/SMS/email.

## Frontend

### Candidate portal app

- `P0` Create new route group for `/candidate/*`.
- `P0` Build mobile-first entry/auth screens.
- `P0` Build step renderer shell with autosave and progress indicator.
- `P0` Build Test1 web experience.
- `P0` Build slot selection screen.
- `P0` Build booking confirmation and status center.
- `P0` Build interrupted-session resume flow.
- `P1` Build candidate message center.
- `P1` Build document upload screen.
- `P2` Add PWA install prompt and offline-friendly shell.

### Shared frontend infrastructure

- `P0` Add candidate API client layer.
- `P0` Add auth/session refresh handling.
- `P0` Add route guards for candidate sessions.
- `P1` Add analytics instrumentation for step completion and abandon.
- `P2` Add experiment hooks for screen/order/copy testing.

## Admin / Recruiter UX

- `P0` Show candidate preferred channel and linked accounts in CRM.
- `P0` Show last delivery status and fallback reason in candidate detail.
- `P1` Show journey progress and current portal step.
- `P1` Show “resume link sent” / “channel unreachable” states in incoming queue.
- `P1` Add recruiter action to issue portal invite link manually.
- `P2` Add unified omnichannel thread panel.

## Infra / Platform

- `P0` Choose SMS provider suitable for RF operations.
- `P0` Choose email delivery provider and DKIM/SPF setup.
- `P0` Add secure secret management for token signing and providers.
- `P0` Add portal base URL and environment config.
- `P1` Add dedicated storage for candidate uploads if document flow is included.
- `P1` Add observability dashboards for delivery chain and funnel.
- `P2` Add feature flag system for channel rollout by city/campaign/source.

## Analytics / Data

- `P0` Expand event taxonomy from bot-centric to channel/journey-centric.
- `P0` Add `entry_channel`, `current_channel`, `resume_channel`, `fallback_triggered` metadata.
- `P0` Track step-level drop-off in portal.
- `P1` Track channel switch reasons and save-rate after fallback.
- `P1` Add dashboards: web vs Telegram completion, abandoned step heatmap, reminder conversion.
- `P2` Add A/B experiment attribution for candidate journey variants.

## Integrations

### Telegram

- `P0` Wrap bot start/continue actions around shared journey APIs.
- `P0` Replace direct bot-only resume logic with portal deep links where appropriate.
- `P1` Migrate confirm/cancel/reschedule buttons to shared action endpoints.

### MAX

- `P1` Fix webhook-to-chat logging path and candidate resolution.
- `P1` Add account linking / identity binding.
- `P1` Add deep-link handoff to portal.
- `P2` Add richer mini-app or embedded continuation if platform adoption validates.

### VK

- `P1` Design VK Mini Apps entry and auth mapping.
- `P1` Implement entry attribution and link-to-portal handoff.
- `P2` Evaluate whether to support embedded screening runtime inside VK or keep it link-out only.

## Database Changes

### New migrations

- `P0` `candidate_channel_accounts`
- `P0` `candidate_access_tokens`
- `P0` `candidate_journey_sessions`
- `P0` `candidate_journey_step_states`
- `P1` `candidate_screening_runs`
- `P1` `candidate_screening_answers`
- `P1` `notification_deliveries`

### Existing schema refactors

- `P0` add indexes on `users.phone`, `users.email` if/when email column is introduced or normalized
- `P0` add foreign-key-friendly relation from outbox/logs to canonical candidate identifiers where feasible
- `P1` add delivery/fallback metadata to existing logs

## API Endpoints Backlog

### Candidate auth

- `P0` `POST /api/candidate/auth/request-code`
- `P0` `POST /api/candidate/auth/verify-code`
- `P0` `POST /api/candidate/auth/token/exchange`

### Candidate journey

- `P0` `GET /api/candidate/me`
- `P0` `GET /api/candidate/journey/current`
- `P0` `POST /api/candidate/journey/steps/{stepKey}/save`
- `P0` `POST /api/candidate/journey/steps/{stepKey}/complete`
- `P0` `GET /api/candidate/status`

### Scheduling

- `P0` `GET /api/candidate/slots`
- `P0` `POST /api/candidate/slots/{slotId}/reserve`
- `P0` `POST /api/candidate/bookings/{bookingId}/confirm`
- `P0` `POST /api/candidate/bookings/{bookingId}/cancel`
- `P0` `POST /api/candidate/bookings/{bookingId}/reschedule`

### Communication

- `P1` `GET /api/candidate/thread`
- `P1` `POST /api/candidate/thread/messages`

## QA / Testing

### Backend tests

- `P0` identity resolution and dedup tests across phone + channel ids
- `P0` portal auth token and OTP tests
- `P0` journey save/resume tests
- `P0` web screening validation tests
- `P0` booking + confirm + cancel + reschedule tests through new APIs
- `P0` fallback notification chain tests
- `P1` channel switch audit tests

### Frontend tests

- `P0` portal auth flow
- `P0` questionnaire autosave/resume
- `P0` slot booking happy path
- `P0` interrupted session recovery
- `P1` candidate status center states
- `P1` portal messaging states

### E2E / smoke

- `P0` messenger entry -> portal continuation
- `P0` web-only start -> booking
- `P0` failed Telegram delivery -> SMS/email fallback -> resume
- `P1` recruiter sees fallback history and delivery state

## Suggested Task Ownership Streams

### Stream A. Core backend

- identity
- journey engine
- scheduling facade
- notifications

### Stream B. Candidate frontend

- portal shell
- auth
- screening
- slots
- status center

### Stream C. CRM/admin

- recruiter visibility
- delivery state
- manual invite actions

### Stream D. Analytics/platform

- events
- dashboards
- provider integration
- rollout flags

## Dependency Notes

- Portal screens should not start before auth + journey contracts are stable enough.
- SMS/email fallback should start with transactional deep links, not freeform messaging.
- MAX/VK work should start only after shared journey and identity services exist.
- Candidate-facing status taxonomy must be agreed before frontend implementation to avoid rework.

## Final Engineering Recommendation

Do not open parallel epics on Telegram replacement bot, candidate portal, and second messenger at the same time. The dependency order in this codebase is:

1. identity + journey core
2. portal MVP
3. fallback delivery
4. second adapter
5. communication refinements

Любой другой порядок увеличит объем временных adapters и регрессионный риск.
