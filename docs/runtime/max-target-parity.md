# MAX Target Parity

Last Verified: 2026-04-19

## Scope
- Target shipping shape for MAX as candidate channel parity relative to Telegram.
- Product/runtime target only. Not a statement of current MAX completeness.

## Purpose
- Define the MAX parity target so future implementation stays on shared semantics and does not drift into MAX-only product logic or redesign-first work.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Runtime Status
- MAX parity target: `Target`

## Mandatory Candidate Journey
- Source application from HH or another source.
- Recruiter pre-screen before channel invite.
- Global link dispatch.
- Entry/bootstrap and identity binding.
- Test 1.
- Resume / vacancy / HH link capture.
- Interview slot booking.
- No-slot fallback with preferred date/time window.
- Incoming/operator handoff.
- Recruiter chat.
- Reminders / trigger notifications.
- Post-interview Test 2.
- Orientation-day agreement.
- Meeting-details delivery.
- Re-entry/resume behavior.
- Continuous candidate/operator clarity.

## Parity Rules
- Telegram is canonical runtime truth.
- MAX is parity target, not a separate business workflow.
- Parity means channel-equivalent candidate journey semantics, not pixel-identical UI.
- Shared backend contracts and shared lifecycle semantics remain canonical.
- Any required step that is not proven in current MAX code remains `Target`, not current truth.

## Allowed UX Differences
- MAX may use miniapp where it improves speed, comprehension, or form entry.
- MAX may use chat where it improves continuity, fallback, and recruiter handoff.
- Shell-specific copy, control grouping, and presentation can differ if the meaning and next step stay aligned with shared semantics.

## Mandatory Chat-Compatible Path
- MAX is not a miniapp-only product shape.
- A chat-compatible path is mandatory for continuity, fallback, handoff, reminders, and non-happy-path resilience.
- The candidate must not be trapped in a miniapp-only path for recovery, manual follow-up, or edge-case states.

## MAX Miniapp Usage Rules
- Miniapp usage is allowed where it improves UX.
- Miniapp usage must not fork product logic.
- Test 1, booking, no-slot fallback, handoff, and status semantics must continue to use shared backend contracts rather than MAX-only branches.

## Non-Negotiable Shared Semantics
- Candidate identity and binding must map into shared candidate/application context.
- Candidate state and next action must remain shared.
- Booking and no-slot semantics must remain shared.
- Recruiter visibility must remain coherent with shared lifecycle and scheduling summaries.
- Reminder eligibility must not diverge into separate MAX-only business rules unless explicitly redesigned at shared-contract level.

## Deferrable Work
- Broad redesign.
- Deep scheduling refactor.
- Reminder-system rewrite.
- Standalone candidate web runtime.
- SMS/voice fallback rollout.
- Anything outside parity-critical journey stages.

## Unknowns / Needs Validation
- Exact shared contract for resume / vacancy / HH link capture remains `Unknown / Not proven`.
- The current repo does not prove which MAX shells should own Test 2, orientation-day, and meeting-details interactions; those remain `Needs validation` for implementation design, not for target necessity.

## Evidence / Source Inputs
- `docs/runtime/telegram-runtime-truth.md`
- `docs/runtime/max-current-state.md`
- `docs/runtime/shared-semantic-contract.md`
- `docs/architecture/supported_channels.md`
- `docs/frontend/state-flows.md`
- `backend/domain/candidates/test1_shared.py`
- `backend/domain/candidates/state_contract.py`
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/apps/admin_api/max_candidate_chat.py`
