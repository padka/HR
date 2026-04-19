# Verification Snapshot

## Operator UX

What looks good:
- Candidates list now shows bounded channel visibility cleanly: linked badges, preferred-channel filter, and compact MAX state chips are visible together without dashboard redesign.
- Candidate detail MAX card reads as an operator control surface instead of a technical debug block: `Запущено`, launch-observed state, flow statuses, and action rail are visible in one card.
- Preview and result modals are readable and keep sensitive launch/chat links redacted from the visible operator flow.

What was fixed:
- MAX rollout copy is localized to recruiter-grade Russian wording.
- Launch-observed state is explicit, so operators can distinguish `Приглашение выдано` from `Кандидат открыл mini-приложение MAX`.
- Global MAX bridge loading no longer pollutes `/app/*` routes with CSP console noise; the bridge is now route-scoped to `/miniapp`.

What remains:
- MAX operator modals are usable, but still visually denser than the candidate surface.
- There is still no broader MAX analytics/dashboard cutover; this pass intentionally keeps visibility bounded to list/detail surfaces.

## Candidate UX

What looks good:
- The dark glass shell reads as a coherent bounded pilot surface and keeps cards readable; blur is restrained and content remains legible.
- `manual_review_required` now renders as a safe dedicated state instead of a generic phone-bind form.
- `chat-ready`, booked, and booking-success states clearly explain the next step and expose a direct MAX chat CTA.
- Empty states for cities, recruiters, and slots are explicit and no longer collapse into blank panels.

What was fixed:
- `manual_review_required` is visually and behaviorally distinct.
- Chat handoff now has a success state before opening MAX chat.
- Home/status screen now carries an explicit next-step card instead of forcing client-side interpretation from raw timeline data.
- Booking success now highlights recruiter, time, prep memo, and follow-up actions in one screen.

What remains:
- Candidate proof here is browser-only with mocked MAX bridge and mocked `candidate_access` API responses; it is not a native MAX client proof.
- We did not prove provider-owned `requestContact()` behavior inside a real MAX client.

## Proof Boundary

- Operator screenshots were captured against a local signed-in runtime with seeded data.
- Candidate screenshots were captured against the real `/miniapp` shell with mocked bridge/initData and mocked API responses.
- This is sufficient for controlled pilot UX review, but not a substitute for provider-backed MAX smoke.
