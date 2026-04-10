# Delivery / MAX Reliability Map

## Purpose

This document maps the current delivery / invite / deep-link / session-recovery boundaries without changing product semantics. It is the working contract for the hardening tranche landed after the initial MAX + shared portal rollout.

## Current hardening contract

- Admin MAX reissue is intentionally rotational: `/api/candidates/{id}/channels/max-link` supersedes the previous active MAX invite and bumps the active portal `session_version`.
- Reuse flows are intentionally non-rotational: internal builders such as `ensure_candidate_invite_token(...)` reuse the current active invite for the same candidate/channel instead of minting another one.
- MAX payload resolution now honors the same session boundary as the web portal: signed portal/MAX launch tokens with stale `journey_session_id` or `session_version` are rejected before linking a MAX identity.
- Candidate portal session creation/restart now serializes on the candidate row to reduce duplicate-active-journey drift under repeated or concurrent requests.
- Successful MAX invite consumption may still mint a fresh active MAX invite afterwards when the journey payload needs a future re-entry launcher. That is deliberate and should not be treated as duplicate delivery.
- Delivery outcome observability for admin-issued MAX access packages now records `invite_id`, `journey_id`, `session_version`, `restarted`, and `correlation_id` in audit/log/message metadata.

## Reliability map

### 1. Candidate invite generation

- Entry point: `backend/domain/candidates/services.py`
  `issue_candidate_invite_token(...)`, `ensure_candidate_invite_token(...)`, legacy `create_candidate_invite_token(...)`
- Downstream dependencies: `users`, `candidate_invite_tokens`
- Stateful artifacts: `CandidateInviteToken.status`, `used_at`, `superseded_at`, `used_by_external_id`
- Idempotency boundary: per `candidate_id + channel`; `ensure_...` reuses active invite, `issue_... rotate_active=True` intentionally supersedes and creates a new active invite
- Retry boundary: DB transaction only; no external side effect
- Sensitive side effects: invalidating previously issued MAX deep links
- Isolation risk: concurrent invite creation without row-level serialization could create drift around active-token ownership
- Current observability quality: medium
  Audit rows exist for `invite_issued` / `invite_superseded`; the hardening tranche adds deterministic locking for `ensure_candidate_invite_token`

### 2. MAX link generation / reissue

- Entry point: `backend/apps/admin_ui/routers/api_misc.py`
  `POST /api/candidates/{id}/channels/max-link`
- Downstream dependencies: `issue_candidate_invite_token(...)`, `ensure_candidate_portal_session(...)`, `bump_candidate_portal_session_version(...)`, MAX adapter delivery
- Stateful artifacts: active MAX invite, active portal journey, `candidate_journey_sessions.session_version`, portal access message/audit metadata
- Idempotency boundary: operator action is rotational by design; each successful reissue invalidates the previous MAX invite and stale portal session tokens
- Retry boundary: DB transaction ends before outbound MAX delivery; delivery outcome is logged/audited separately
- Sensitive side effects: old deep links stop working, candidate can be forced onto a fresher recovery boundary
- Isolation risk: repeated double-submit is still semantically a second reissue, not a transparent retry
- Current observability quality: medium-high
  Delivery outcome now logs/audits `invite_id`, `journey_id`, `session_version`, `restarted`, and `correlation_id`

### 3. Deep-link resolution inside MAX

- Entry point: `backend/apps/max_bot/candidate_flow.py`
  `_resolve_max_candidate(...)`, `process_bot_started(...)`
- Downstream dependencies: portal token parser, invite-token lookup, candidate linking, analytics, audit log
- Stateful artifacts: `users.max_user_id`, `candidate_invite_tokens.used_*`, portal `session_version`
- Idempotency boundary: same MAX user + same invite is idempotent; different MAX user + already-used invite is a conflict
- Retry boundary: webhook transaction; duplicate webhook bodies are separately deduped in `backend/apps/max_bot/app.py`
- Sensitive side effects: binding MAX identity to CRM candidate, session invalidation via `bump_candidate_portal_session_version(...)`
- Isolation risk: same invite/session used by competing identities; stale signed launch token reused after restart/reissue
- Current observability quality: medium-high
  Hardening now emits structured rejection reasons and rejects stale portal/MAX launch tokens before ownership changes

### 4. MAX mini-app entry

- Entry point: `backend/domain/candidates/portal_service.py`
  `build_candidate_public_max_mini_app_url_async(...)`
- Downstream dependencies: MAX profile status probe, portal public URL settings, signed MAX launch token builder
- Stateful artifacts: signed `mx1...` launch token, active journey/session version
- Idempotency boundary: launcher is valid only for the signed journey/session pair; after session bump it is intentionally stale
- Retry boundary: pure link generation, no external side effect until candidate opens the launcher
- Sensitive side effects: none at generation time; actual side effect begins when MAX resolves the token
- Isolation risk: stale launchers being accepted after restart/reissue
- Current observability quality: medium
  Hardening closes the stale-launcher acceptance gap in MAX payload resolution

### 5. Web/browser portal entry and recovery

- Entry point: `backend/apps/admin_ui/routers/candidate_portal.py`
  `/api/candidate/session/exchange`, `/api/candidate/journey`, resume-cookie/header-token recovery
- Downstream dependencies: signed portal token parser, `ensure_candidate_portal_session(...)`, active journey validation
- Stateful artifacts: server session cookie, resume cookie, `candidate_journey_sessions.session_version`
- Idempotency boundary: same valid session payload is refreshed in place; stale version requires a fresh link
- Retry boundary: request-local; no outbound messaging
- Sensitive side effects: establishing candidate browser session, clearing stale resume cookies
- Isolation risk: concurrent session creation/restart could create duplicate active journeys without serialization
- Current observability quality: high
  Version mismatch already audited; candidate-row locking now reduces active-journey split-brain risk

### 6. Telegram entry / invite binding

- Entry point: `backend/domain/candidates/portal_service.py`
  `build_candidate_public_telegram_entry_url_async(...)`
  and `backend/domain/candidates/services.py`
  `bind_telegram_to_candidate(...)`
- Downstream dependencies: Telegram profile probe, invite-token lookup, user identity binding
- Stateful artifacts: Telegram-linked user identity, invite token status/used timestamp
- Idempotency boundary: bind is invite-token based; reuse with the same identity is safe, conflicting reuse is rejected
- Retry boundary: DB transaction
- Sensitive side effects: setting Telegram identity on candidate
- Isolation risk: legacy invite paths remain token-centric and do not share MAX session-version semantics
- Current observability quality: medium

### 7. Outbox / retry / dispatch

- Entry point: `backend/apps/bot/services/notification_flow.py`
- Downstream dependencies: outbox repository, notification logs, messenger adapters, channel degraded-state store, broker/DLQ
- Stateful artifacts: `outbox_notifications`, `notification_logs`, degraded channel state
- Idempotency boundary: repository dedup at `notification_type + booking_id + candidate_tg_id`; sent/failed rows are reused instead of re-enqueued
- Retry boundary: `transient` failures are scheduled, `permanent` / `misconfiguration` go to dead-letter, broker messages can go to DLQ
- Sensitive side effects: candidate/recruiter notifications on Telegram/MAX
- Isolation risk: cross-channel dedup is intentionally coarse; delivery fan-out still depends on existing outbox keys
- Current observability quality: high
  Failure class, code, retry timing, degraded channel reason, and DLQ routing are already surfaced

### 8. Duplicate request / idempotency scenarios

- Entry points:
  `backend/apps/max_bot/app.py` webhook dedupe,
  invite issuance helpers,
  portal session validation,
  outbox deduplication
- Downstream dependencies: Redis or in-memory dedupe cache, DB row locks, audit log
- Stateful artifacts: webhook dedupe keys, invite rows, active journey row, outbox rows
- Idempotency boundary:
  duplicate webhook callbacks short-circuit,
  stale portal/MAX tokens reject,
  same invite + same MAX user stays idempotent,
  outbox `sent` / `pending` rows are reused
- Retry boundary: webhook dedupe TTL for MAX, DB transaction for invite/session state, outbox retry scheduler for delivery
- Sensitive side effects: identity linking, stale-link invalidation, outbound messages
- Isolation risk: there is still no DB-level uniqueness on `users.max_user_id`, so a cross-candidate same-`max_user_id` race remains a residual risk outside this tranche
- Current observability quality: medium-high

## Practical operator rules

- If a recruiter explicitly reissues a MAX link, assume the previous MAX invite and previous signed portal/MAX launch tokens are stale.
- If a candidate reports that a MAX launch link suddenly stopped working after reissue/restart, inspect the latest `candidate_portal_access_delivery_*` audit rows and compare `journey_id` / `session_version`.
- If the same candidate re-enters via journey payloads after successful MAX link, expect one `used` invite plus a newer `active` MAX invite for future re-entry launchers.
- If the candidate is not yet linked to MAX, admin reissue can still return the deep link, but direct MAX delivery will remain `skipped_by_preflight` with `max_not_linked`.

## Residual risks

- `users.max_user_id` still has no DB-level uniqueness guarantee, so a true concurrent same-user cross-candidate race is only reduced by application checks, not eliminated.
- `notification_flow.py` and `candidate_flow.py` remain large orchestration modules; behavior is now better bounded, but further extraction would still pay down surprise cost in a later tranche.
- Legacy generic invite paths still coexist with signed portal/MAX launch tokens; they are intentionally not unified in this tranche to avoid a broader product rewrite.
