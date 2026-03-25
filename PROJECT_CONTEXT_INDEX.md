# Project Context Index

Compact navigation for current Attila Recruiting work.

## Canonical docs

Read in this order:

1. [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
4. [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
5. [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
6. [`.codex/config.toml`](/Users/mikhail/Projects/recruitsmart_admin/.codex/config.toml)
7. [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/)

## Current system map

- Backend admin app: `backend/apps/admin_ui/app.py`
- Admin API: `backend/apps/admin_api/main.py`
- Telegram bot: `backend/apps/bot/app.py`
- MAX bot: `backend/apps/max_bot/app.py`
- Candidate domain: `backend/domain/candidates/*`
- Slot/schedule domain: `backend/domain/slot_service.py`, `backend/domain/slot_assignment_service.py`
- Frontend SPA: `frontend/app/src/app/main.tsx`
- Candidate portal: `frontend/app/src/app/routes/candidate/*`
- Recruiter dashboard/chat: `frontend/app/src/app/routes/app/*`

## Business-critical flows

- candidate lifecycle and status transitions
- slot booking, reschedule, and confirmation
- recruiter chat and dashboard actions
- candidate portal and MAX mini app
- bot/webhook delivery and idempotency
- analytics and KPI reporting

## High-risk surfaces

- auth/session handling
- candidate portal token exchange
- webhooks and retries
- scheduling and slot assignment
- migrations
- analytics calculations
- PII in logs and traces

## Local Codex layer

- `.codex/config.toml` holds project defaults for safe agent operation.
- `.agents/skills/` holds reusable workflow gates for recurring tasks.
- `.codexrc` remains only as a compatibility shim until runtime precedence is confirmed.
