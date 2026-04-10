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
- candidate portal and candidate-facing bot now enforce an activity guard after completed `Test 1` and later stages: repeated screening is blocked with a structured `409 candidate_screening_locked` payload, the candidate sees explicit “already active stage” guidance instead of a silent restart, and `candidate_journey_events` now acts as the canonical candidate-facing audit trail for portal entry, shared-access verification, screening milestones, blocked re-entry attempts, and portal restart
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
- MAX duplicate-owner preflight is now explicit and reproducible before schema hardening: read-only audit/classification lives in [backend/domain/candidates/max_owner_preflight.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/max_owner_preflight.py) with CLI entrypoint [scripts/max_owner_preflight.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/max_owner_preflight.py), the cleanup runbook lives in [docs/runbooks/max-ownership-guard-plan.md](/Users/mikhail/Projects/recruitsmart_admin/docs/runbooks/max-ownership-guard-plan.md), and MAX runtime now fails closed on normalized duplicate-owner ambiguity instead of silently picking one candidate row
- delivery/MAX hardening tranche is now landed for invite/deep-link/session-recovery boundaries: MAX payload resolution rejects stale signed portal/MAX launch tokens against the active `journey_session_id` + `session_version`, candidate portal session ensure/restart serialize on the candidate row to reduce duplicate-active-journey drift, active invite reuse is deterministic for helper-driven paths, and admin MAX delivery outcome now records invite/journey/session metadata for audit and health diagnostics
- delivery/MAX reliability ownership is now documented in [docs/architecture/delivery-max-reliability-map.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/delivery-max-reliability-map.md), including explicit rotation vs reuse rules, re-entry semantics, retry/idempotency boundaries, and residual risks
- MAX ownership guard is now stronger at application level: claim paths serialize on `max_user_id` in Postgres, cross-candidate reuse becomes explicit conflict instead of silent reuse, duplicate owner rows surface as `ownership_ambiguous` in candidate channel health, and the migration-safe audit plan lives in [docs/architecture/max-ownership-guard-plan.md](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture/max-ownership-guard-plan.md)
- candidate messenger now runs as a focused two-pane recruiter workspace: compact inbox rail on the left, chat workspace on the right, sticky composer, quick templates, local unread/read notifications, and direct link-out to the candidate card without inline candidate-details rail
- candidate messenger second-pass redesign is landed locally: hero block removed, left rail simplified for faster triage, chat header/composer rebuilt for operational clarity, and the previous inline candidate-details drawer has been removed from the route
- Telegram `/start` now resumes an existing progressed candidate instead of relaunching `Test 1`: if the candidate already has active CRM progress, the bot sends a short current-stage summary plus a deep-link back into the active portal journey
- interview reminder flow now includes a candidate-facing readiness message 10 minutes before the meeting, delivered through the existing reminder scheduler/outbox pipeline
- Telegram candidate scheduling flow is now more interactive after confirmation: assignment-backed meeting notifications can surface persistent `Детали встречи / Компания и этап / Перенести / Отменить` controls for future meetings, legacy `slot_proposal` callbacks are bridged onto the current assignment contract, and cancellation now prompts for a short candidate reason that is forwarded back to the recruiter chat
- local auth resolution now prefers an active recruiter browser session over conflicting stale bearer auth on localhost, preventing recruiter sessions from snapping back to admin locally
- intro day preview/send now resolves from the city-aware `intro_day_invitation` message template, with city profile spotlight for that override in the city editor
- interview script generation now uses a v2 AI pipeline: stage-aware context, regulation-first prompt, recruiter-readable `conversation_script`, and a reading-first modal in candidate detail while preserving internal script blocks for QA/feedback
- recruiter read-models now expose an additive candidate state contract: `lifecycle_summary`, `scheduling_summary`, `candidate_next_action`, and `state_reconciliation` are projected from current legacy fields so list/detail/dashboard can start reading one backend-owned contract without a big-bang rewrite
- candidate detail no longer performs hidden write-on-read autofix for passed Test2; drift is now surfaced through reconciliation issues instead of mutating `candidate_status` during reads
- recruiter-facing read surfaces now use that contract as the primary UI model: incoming queue, admin dashboard incoming widgets, candidates list, and kanban render lifecycle/scheduling/next-action/reconciliation through one shared frontend adapter, while legacy status fields remain only as transitional fallback and query compatibility
- dashboard waiting queue now enriches the compatibility contract with batch-loaded `Slot` and `SlotAssignment` data, so incoming cards can display backend-owned scheduling state instead of a pure legacy status heuristic
- recruiter-facing server-side list semantics have moved another step toward the canonical contract: `/api/candidates` now supports backend-owned `state=` filters, backend emits pipeline-aware `filters.state_options`, and kanban/worklist grouping is projected from `operational_summary` instead of raw legacy status columns
- recruiter write semantics have also moved one safe step toward the canonical contract: kanban drag/drop now sends backend-owned `target_column`, recruiter action endpoints resolve domain intent server-side, and successful recruiter writes return refreshed canonical recruiter-facing state instead of only a raw target status
- four high-value recruiter lifecycle actions now execute through dedicated backend lifecycle use-cases instead of the generic legacy helper core: `send_to_test2`, `mark_test2_completed`, `mark_hired`, and `mark_not_hired`
- recruiter write blockers are now formalized as an additive backend contract: blocked kanban moves and recruiter actions return `blocking_state` alongside `error`, `message`, and `candidate_state`, and the current design boundary explicitly separates canonical-use-case-owned recruiter writes from legacy-owned flows
- scheduling integrity stabilization tranche is now landed for the most dangerous write-side paths: shared integrity evaluation lives in [backend/domain/candidates/scheduling_integrity.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py), recruiter read payloads expose additive scheduling ownership fields (`integrity_state`, `write_behavior`, `write_owner`, `assignment_owned`, `slot_only_writes_allowed`), and write-side no longer ignores persisted `Slot`/`SlotAssignment` conflicts on confirm, reschedule approval, recruiter alternative offer, kanban-sensitive recruiter actions, or portal slot-only mutations
- assignment-owned scheduling execution is now narrower and more predictable without a schema rewrite: [backend/domain/slot_assignment_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/slot_assignment_service.py) now synchronizes `Slot` bindings during confirm / exact reschedule approval, blocks manual-repair conflicts instead of silently proceeding, and the legacy compatibility confirm endpoint in [backend/apps/admin_ui/routers/slot_assignments_api.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments_api.py) delegates to the same service semantics
- scheduling repair and legacy slot-only retirement tranche is now operator-facing instead of surface-only: [backend/domain/scheduling_repair_service.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/scheduling_repair_service.py) now supports the safe automated `assignment_authoritative` path plus a bounded manual subset (`resolve_to_active_assignment`, `cancel_active_assignment`, `rebind_assignment_slot`), [backend/domain/candidates/scheduling_integrity.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/scheduling_integrity.py) emits structured `repair_workflow` taxonomy/confirmations/selection options for future UI, [backend/apps/admin_ui/routers/slot_assignments.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/slot_assignments.py) exposes the same explicit repair control layer with structured success/deny payloads and audit metadata, webapp slot-only booking/reschedule/cancel in [backend/apps/admin_api/webapp/routers.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/webapp/routers.py) stay assignment-aware guarded, and legacy [backend/domain/repositories.py](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/repositories.py) candidate confirm still synchronizes the matching active `SlotAssignment` instead of leaving it stale behind `Slot`
- isolated production-like PostgreSQL proof is now broader than the initial critical subset: [Makefile](/Users/mikhail/Projects/recruitsmart_admin/Makefile) target `make test-postgres-proof` exercises clean migrations plus persisted scheduling propose/confirm/manual-repair/conflict paths, MAX duplicate-owner runtime and preflight cleanup classification, portal restart/re-entry/recovery boundaries, and single-consumer outbox claim semantics on PostgreSQL-backed `rs_test`
- recruiter-facing SPA surfaces now share one decision-first recruiter grammar: list, incoming, kanban cards, and candidate detail top area render a common `next action -> operational context -> risk/blocker -> lifecycle` hierarchy through reusable recruiter-state primitives
- recruiter list/incoming/dashboard attention order now follows backend contract semantics instead of status badge noise: `candidate_next_action` is primary, `operational_summary` drives context/triage lanes, and `state_reconciliation` / `blocking_state` are surfaced through one unified risk language
- kanban is now visually guided by backend `droppable` hints rather than implied freeform drag-and-drop, and list-side bulk triage is intentionally limited to selection-only helpers in this tranche
- admin dashboard now opens with a recruiter control tower before KPI blocks: three triage lanes (`action_now`, `waiting`, `review`) reuse the same recruiter-state grammar as incoming instead of a separate metrics-first card language
- candidate detail is now explicitly split into `Lifecycle`, `Scheduling`, `Risks & blockers`, and `Context & history` beneath the action center, so tests/AI/tools stay secondary and the top of the page answers what to do next first

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
- Scheduling is still transitional outside the hardened tranche: manual repair is now operable for the minimal safe subset, but cross-owner/cross-purpose conflicts, stale-slot-with-own-active-assignment cases, unsupported status classes, and `propose_alternative(...)` transitional split-brain still remain surfaced-and-blocked rather than generally repairable, and legacy slot-only repository/webapp contours still exist beside `SlotAssignment` flows.
- Production-like confidence is now stronger for the targeted PostgreSQL tranche, but the broad backend suite still mostly runs through the fast default harness; recruiter-facing repair UI and MAX cleanup execution remain separate next tranches rather than proven productized surfaces.
- Delivery/MAX is more predictable after the hardening tranche, but `backend/apps/max_bot/candidate_flow.py` and `backend/apps/bot/services/notification_flow.py` remain oversized orchestration surfaces, and `users.max_user_id` still lacks a DB-level uniqueness guarantee for true cross-candidate concurrent-link races.
