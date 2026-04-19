# MAX Pilot Visual QA

Date: 2026-04-19

Scope:
- operator MAX rollout surface in `/app`
- candidate MAX mini app in `/miniapp`

Evidence model:
- operator review used a local signed-in `admin_ui` runtime with seeded MAX rollout data
- candidate review used the live `/miniapp` shell from `admin_api` with mocked MAX bridge/initData and mocked `candidate_access` API responses

Limitations:
- browser automation and screenshots only
- no native MAX client proof
- no provider-owned MAX Partner UI proof
- no fake provider success claims

Key screenshots:
- `screenshots/operator-candidates-max.png`
- `screenshots/operator-candidate-detail-max-card.png`
- `screenshots/operator-max-preview-modal.png`
- `screenshots/operator-max-result-modal.png`
- `screenshots/miniapp-contact-required.png`
- `screenshots/miniapp-manual-review.png`
- `screenshots/miniapp-home-next-step.png`
- `screenshots/miniapp-test1-in-progress.png`
- `screenshots/miniapp-booking-empty-cities.png`
- `screenshots/miniapp-booking-empty-recruiters.png`
- `screenshots/miniapp-booking-empty-slots.png`
- `screenshots/miniapp-booked-return-home.png`
- `screenshots/miniapp-booking-success.png`
- `screenshots/miniapp-chat-ready.png`

Related notes:
- [verification-snapshot.md](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/verification-snapshot.md)
- [release-blockers.md](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification/2026-04-19-max-pilot-visual-qa/release-blockers.md)
