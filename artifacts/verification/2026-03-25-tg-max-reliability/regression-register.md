# Regression Register

## Purpose
Record the reliability risks surfaced during the Telegram/MAX sprint tranche, their blast radius, required regression layer, and final resolution.

## Owner
Platform Engineering / QA

## Status
Active

## Last Reviewed
2026-03-25

## Source Paths
- `backend/apps/admin_ui/routers/api_misc.py`
- `backend/apps/admin_ui/services/messenger_health.py`
- `backend/apps/admin_ui/services/notifications_ops.py`
- `backend/domain/candidates/models.py`
- `backend/domain/candidates/services.py`
- `backend/migrations/versions/0098_tg_max_reliability_foundation.py`

## Related Diagrams
- `docs/architecture/core-workflows.md`
- `docs/security/auth-and-token-model.md`
- `docs/runbooks/broker-degradation.md`

## Change Policy
Update when a new Telegram/MAX reliability regression appears, changes severity, or is resolved.

| ID | Severity | Owner | Affected flow | Reproduction | Required test layer | Status | Resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RS-TGMAX-001 | P0 | Security / Platform | MAX invite issuance, audit trail, recruiter ops payloads | Raw invite tokens were visible in audit log entries and recruiter-facing channel-health payloads | pytest + API regression | Resolved | Redacted token-bearing surfaces in [`backend/apps/admin_ui/routers/api_misc.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py) and [`backend/apps/admin_ui/services/messenger_health.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/services/messenger_health.py); added assertions in [`tests/test_admin_candidate_chat_actions.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_admin_candidate_chat_actions.py) |
| RS-TGMAX-002 | P1 | Platform Runtime | Channel degradation / operator retry | Explicit retry requeued dead-letter notifications and cleared degraded state before operator recovery was explicit | pytest + admin API regression | Resolved | Retry now only requeues; degraded state is recovered explicitly through [`/api/system/messenger-health/{channel}/recover`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/api_misc.py); covered in [`tests/test_outbox_notifications.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_outbox_notifications.py) and [`tests/test_admin_notifications_feed_api.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_admin_notifications_feed_api.py) |
| RS-TGMAX-003 | P1 | Platform / Data | MAX invite rotation under concurrency | “One active MAX invite per candidate” existed only in application flow, not in DB invariant | pytest + schema regression | Resolved | Added candidate row locking in [`backend/domain/candidates/services.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/services.py) plus partial unique index/backfill in [`backend/domain/candidates/models.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/models.py) and [`backend/migrations/versions/0098_tg_max_reliability_foundation.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0098_tg_max_reliability_foundation.py); enforced by [`tests/test_candidate_lead_and_invite.py`](/Users/mikhail/Projects/recruitsmart_admin/tests/test_candidate_lead_and_invite.py) |
| RS-TGMAX-004 | P1 | Platform / Portal | Portal header recovery after invite rotation / relink | Session recovery could become stale after ownership-changing actions unless versioned session payload remained authoritative | pytest + e2e | Resolved | `journey_session_id + session_version` validation stayed in force via [`backend/domain/candidates/portal_service.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/domain/candidates/portal_service.py) and [`backend/apps/admin_ui/routers/candidate_portal.py`](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/routers/candidate_portal.py); covered by backend suite and full e2e |
