# Shared Semantic Contract

Last Verified: 2026-04-19

## Scope
- Shared lifecycle and operator semantics that parity work must preserve across Telegram and MAX.

## Purpose
- Freeze the current shared meaning layer before MAX parity work changes shells, routing, or candidate-facing presentation.

## Status Legend
- `Live / Full`
- `Live / Bounded`
- `Partial`
- `Target`
- `Unknown / Not proven`

## Runtime Status
- Shared operator-facing state contract: `Live / Full`
- Shared candidate-facing semantic contract: `Partial`

## Shared Today
- Candidate state is `Live / Full`.
  - `backend/domain/candidates/state_contract.py` is the strongest current shared operator-facing lifecycle contract.
  - It defines lifecycle stages, scheduling stages, queue state labels, kanban mappings, and candidate next-action normalization.
- Candidate next action is `Live / Full`.
  - Shared outputs include `candidate_next_action`, `operational_summary`, `scheduling_summary`, and `reconciliation`.
- Urgency / operational priority is `Live / Full` on operator surfaces.
  - Admin incoming and candidate detail payloads already embed shared state contract outputs.
- Handoff semantics are `Partial`.
  - Operator handoff is shared at the read-model level.
  - Candidate-to-chat handoff exists in MAX candidate-access and in Telegram runtime behavior, but one explicit cross-channel contract file does not exist.
- Reminder eligibility is `Partial`.
  - Shared statuses and scheduling states exist.
  - Actual reminder execution still contains Telegram-leaning implementation assumptions downstream.
- Channel identity is `Partial`.
  - Shared candidate record can carry Telegram and MAX identity fields.
  - Binding, access-session, and continuity semantics still differ by channel.
- Operator visibility is `Live / Full`.
  - Shared state-contract outputs are consumed by dashboard/incoming/detail surfaces.
- Delivery routing assumptions are `Partial`.
  - `backend/core/messenger/registry.py` resolves adapter preference by explicit platform, then MAX identity, then Telegram identity.
  - `backend/apps/admin_ui/services/chat.py` also uses recent inbound channel and linked identities.
  - Downstream reminder/outbox flows remain Telegram-leaning in many places.
- Re-entry rules are `Partial`.
  - MAX has explicit session/start-param/surface/version checks.
  - Telegram re-entry is simpler and less formalized.

## Candidate-Facing Translations
### Internal state / operator semantics
- Shared internal semantics are expressed through lifecycle stage, scheduling stage, queue state, next action, and reconciliation outputs.
- Operator surfaces already consume these canonical summaries.

### Candidate-facing wording
- Candidate-facing wording is not yet frozen in one shared contract.
- Telegram text, MAX miniapp cards, and MAX chat prompts can differ in wording.
- The next-step meaning must stay aligned even when copy differs.

### Channel-neutral meaning vs shell-specific rendering
- Channel-neutral meaning should stay shared:
  - who the candidate is
  - what step they are on
  - what next action is available
  - whether they are waiting on recruiter, candidate, slot, or reminder
- Shell-specific rendering may differ:
  - Telegram chat prompts
  - MAX chat prompts
  - MAX miniapp cards and flows
- Shell-specific rendering must not fork business logic or lifecycle meaning.

## Proposed / Needs Validation
- Resume / vacancy / HH link capture as a required shared semantic step is `Proposed / Needs validation`.
- A shared reminder-eligibility contract that is channel-neutral at execution time is `Proposed / Needs validation`.
- A single explicit re-entry contract across Telegram and MAX is `Proposed / Needs validation`.
- A fully shared candidate-facing wording map by semantic state is `Proposed / Needs validation`.

## Channel-Specific Rendering Only
- Telegram bot keyboards and chat copy.
- MAX chat prompt copy and callback wiring.
- MAX miniapp layout, cards, and navigation sequence.
- Recruiter miniapp `/tg-app/*` rendering.

## Evidence
- `backend/domain/candidates/state_contract.py`
- `backend/domain/candidates/actions.py`
- `backend/domain/candidates/write_contract.py`
- `backend/core/messenger/registry.py`
- `backend/apps/admin_ui/services/chat.py`
- `backend/apps/admin_ui/services/dashboard.py`
- `backend/apps/admin_ui/services/candidates/helpers.py`
- `backend/apps/admin_api/candidate_access/services.py`
- `backend/apps/admin_api/candidate_access/router.py`
- `backend/apps/admin_api/max_candidate_chat.py`

## Unknowns
- The repo does not currently provide one explicit shared candidate-facing wording contract.
- Full cross-channel reminder eligibility and delivery semantics are not yet frozen.
- Some lifecycle stages after interview remain shared at operator level but not fully re-proven as channel-neutral candidate-facing contracts.
