# Current Program State

## Snapshot

- Repository: Attila Recruiting
- Mode: local development only by default
- Production/VPS: do not touch unless the user explicitly asks
- Root markdown cleanup: completed on `2026-03-08`

## What Is Already Landed In Code

- React SPA is the active frontend in [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- shared theme/token system lives in [frontend/app/src/theme](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme)
- recruiter/incoming/test-preview/light-theme work has already been implemented in code
- backend reschedule/status fixes have already been implemented in code
- candidate portal web flow is available as a Telegram-independent fallback path
- candidate portal journey now surfaces vacancy summary, company context, current step, and next-step time; the start screen also tolerates missing/stale tokens by reusing an active portal session when one exists, public candidate bootstrap no longer depends on a CSRF preflight before session exchange, and candidate API requests can recover via a signed portal-token header when browser cookies are unavailable
- candidate portal has been reframed into a web-first candidate cabinet: `/candidate/journey` now acts as a persistent cabinet with dashboard, workflow, tests, schedule, inbox, company materials, and candidate-visible feedback instead of a narrow stepper-only flow
- HH entry gateway is now landed for the candidate cabinet: `/candidate/start?entry=<signed_hh_entry_token>` resolves a chooser with `Web / MAX / Telegram`, records the selected entry channel in the active journey payload, and launches the same cabinet/session instead of branching into separate channel-specific business flows
- HH entry has been hardened into a durable recovery anchor: the chooser link no longer breaks just because the active portal session version changed, and the browser keeps the last good entry token so stale direct cabinet links can fall back to the chooser on the same device without asking the recruiter for a new link
- candidate entry chooser is now resilient to browser/webview body quirks: `/api/candidate/entry/select` accepts the channel choice via JSON, query string, or form-encoded payload, so public `Web / MAX / Telegram` launcher selection no longer depends on one fragile request format
- bare public `/candidate/start` is now a neutral candidate landing instead of an eager restore path: without an explicit personal token it no longer hits `/api/candidate/journey`, so new candidates do not see false “session expired” errors and the hot path avoids unnecessary 401 noise under high public traffic
- shared candidate onboarding is now available for mass HH outreach: recruiters can distribute one public portal URL, candidates identify themselves by phone, receive a one-time code through an already linked HH/Telegram/MAX channel, and then enter the same web-first cabinet without per-candidate invite links as the primary UX
- shared public portal delivery is now hardened for scale: candidate phone lookup uses indexed normalized storage, OTP challenge/verify stays anti-enumeration-safe, production health explicitly requires Redis-backed challenge/rate-limit storage, and recruiters can bulk-send the same shared portal link to explicitly selected HH candidates
- candidate cabinet launcher switching is now persistent: when the candidate opens Web/MAX/Telegram from inside `/candidate/journey`, the system records the new `last_entry_channel` in the active journey before redirecting, so recruiters and future entry packages keep the same unified context
- recruiter-to-candidate communication can now fall back to the web inbox even without Telegram/MAX binding; CRM messages are stored with channel-agnostic metadata and appear in the same candidate conversation stream
- MAX webhook bot now supports public candidate onboarding plus CRM linking: candidates can start profile + screening in MAX from the bot link directly, admin can still issue a MAX deep link to bind an existing CRM candidate, recruiter chat can route through MAX, and the candidate portal now also opens as a MAX mini app with a `startapp` invite link for the personal cabinet
- live MAX readiness is now explicit instead of implicit: admin health and candidate channel health expose `token_valid`, bot profile resolution, MAX link-base source, webhook public readiness, subscription readiness, and deterministic delivery block reasons; local public bootstrap is standardized via `make dev-max-live`
- delivery/MAX hardening tranche is now landed for invite/deep-link/session-recovery boundaries: MAX payload resolution rejects stale signed portal/MAX launch tokens against the active `journey_session_id` + `session_version`, candidate portal session ensure/restart serialize on the candidate row to reduce duplicate-active-journey drift, active invite reuse is deterministic for helper-driven paths, and admin MAX delivery outcome now records invite/journey/session metadata for audit and health diagnostics
- delivery/MAX reliability ownership is now documented in [docs/architecture/delivery-max-reliability-map.md](/Users/mikhail/Projects/recruitsmart_admin_delivery_max_hardening/docs/architecture/delivery-max-reliability-map.md), including explicit rotation vs reuse rules, re-entry semantics, retry/idempotency boundaries, and residual risks
- candidate messenger now runs as a focused two-pane recruiter workspace: compact inbox rail on the left, chat workspace on the right, sticky composer, quick templates, local unread/read notifications, and direct link-out to the candidate card without inline candidate-details rail
- candidate messenger second-pass redesign is landed locally: hero block removed, left rail simplified for faster triage, chat header/composer rebuilt for operational clarity, and the previous inline candidate-details drawer has been removed from the route
- interview reminder flow now includes a candidate-facing readiness message 10 minutes before the meeting, delivered through the existing reminder scheduler/outbox pipeline
- local auth resolution now prefers an active recruiter browser session over conflicting stale bearer auth on localhost, preventing recruiter sessions from snapping back to admin locally
- intro day preview/send now resolves from the city-aware `intro_day_invitation` message template, with city profile spotlight for that override in the city editor
- interview script generation now uses a v2 AI pipeline: stage-aware context, regulation-first prompt, recruiter-readable `conversation_script`, and a reading-first modal in candidate detail while preserving internal script blocks for QA/feedback

## What Was Cleaned Up

- Closed task-specific root markdown files were removed.
- Temporary task/session/verification files were removed.
- The permanent root doc set is now intentionally small and anchored by [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md).

## Durable Root Docs

- [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
- [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
- [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
- [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
- [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
- [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)

## What Future Agents Should Not Re-Do

- Do not regenerate large root-level planning packages for already-closed tasks.
- Do not leave temporary markdown files in repo root after the task is finished.
- Do not treat `codex/` or `docs/archive/` as canonical without checking live code.

## Likely Next Work Modes

- small feature batches in backend or frontend
- regression fixes with targeted tests
- subsystem documentation updates under [docs](/Users/mikhail/Projects/recruitsmart_admin/docs), not new root markdown piles

## Open Risks

- The worktree may often be dirty; always check `git status --short` first.
- [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css) and [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx) remain high-blast-radius files.
- Historical docs still exist under [docs/archive](/Users/mikhail/Projects/recruitsmart_admin/docs/archive) and [codex](/Users/mikhail/Projects/recruitsmart_admin/codex); they are reference material, not current source of truth.
- Shared public portal is product-correct and no longer depends on per-candidate links, but 10k+ production still needs a later tranche for provider-backed OTP delivery metrics, bulk-send backgrounding/outbox fan-out, and manual load testing under burst traffic.
- Delivery/MAX is more predictable after the hardening tranche, but `backend/apps/max_bot/candidate_flow.py` and `backend/apps/bot/services/notification_flow.py` remain oversized orchestration surfaces, and `users.max_user_id` still lacks a DB-level uniqueness guarantee for true cross-candidate concurrent-link races.
