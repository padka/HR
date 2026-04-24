# AI Copilot Advisory MVP

Current batch adds a bounded recruiter-facing AI copilot surface on top of the existing shared candidate journey.

## Scope

The implementation is intentionally **advisory-only**:

- AI does not change candidate status
- AI does not assign or approve slots
- AI does not send messages automatically
- shared `Test1 -> booking -> interview -> Test2 -> intro day` logic remains canonical

## New Candidate AI Kinds

- `candidate_facts_v1`
- `recruiter_next_best_action_v1`
- `candidate_contact_draft_v1`

These kinds reuse the existing `AIService`, `ai_outputs`, `ai_request_logs`, cache invalidation, and recruiter/admin auth boundaries.

## Admin UI Surface

New internal routes under `backend/apps/admin_ui/routers/ai.py`:

- `GET /api/ai/candidates/{candidate_id}/facts`
- `POST /api/ai/candidates/{candidate_id}/facts/refresh`
- `GET /api/ai/candidates/{candidate_id}/next-best-action`
- `POST /api/ai/candidates/{candidate_id}/next-best-action/refresh`
- `POST /api/ai/candidates/{candidate_id}/next-best-action/feedback`
- `POST /api/ai/candidates/{candidate_id}/contact/drafts`

Recruiter UI entrypoint:

- insights drawer in candidate detail (`CandidateDrawer`)

The drawer now shows:

- structured reusable facts from Test 1 / HH context
- recruiter next-best-action
- recruiter playbook
- explicit actions `accept`, `dismiss`, `edit_and_send`

`edit_and_send` only inserts a draft into recruiter chat. It does not auto-send.

## Fallback Model

For `candidate_facts_v1` and `recruiter_next_best_action_v1`:

- cache hit returns the stored payload
- cache miss returns a deterministic local fallback
- refresh tries the configured provider and falls back to local synthesis on failure

For `candidate_contact_draft_v1`:

- cache hit returns the stored payload
- cache miss or explicit generation tries the provider
- provider failure falls back to deterministic stage-aware drafts

This keeps the recruiter surface usable without permitting silent business mutations.

## Feedback Logging

Recruiter feedback for next-best-action is logged as analytics events:

- `ai_recruiter_next_best_action_feedback`

Current feedback states:

- `accepted`
- `dismissed`
- `edited`

The feedback is operational telemetry, not a business-state transition.

## No-Go Areas For This MVP

- no auto-decline
- no auto-send to candidate
- no slot/status mutation from AI output
- no MAX-only or TG-only fork of candidate journey
- no dashboard/incoming contract expansion in this batch
