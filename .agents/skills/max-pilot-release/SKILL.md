---
name: max-pilot-release
description: Use when preparing or validating RecruitSmart's bounded MAX controlled pilot. Covers flags, env/secrets, preflight, enable order, smoke, rollback, support notes, and explicit external blocker handling.
---

# MAX Pilot Release

Use this skill for:

- MAX pilot enablement checklists
- env/secret inventory for MAX
- controlled rollout and rollback sequencing
- provider smoke readiness and blocker capture
- final pilot pack and handoff

Do not use for:

- broad architecture redesign
- production rollout
- unrelated Telegram/browser/SMS runtime work

## Workflow

1. Verify the live code path first: `settings`, `/health/max`, `/api/max/launch`, webhook auth, operator rollout surface.
2. Treat `MAX_INVITE_ROLLOUT_ENABLED=false` and `MAX_ADAPTER_ENABLED=false` as the safe baseline.
3. Document the canonical env contract:
   - `MAX_INVITE_ROLLOUT_ENABLED`
   - `MAX_ADAPTER_ENABLED`
   - `MAX_BOT_ENABLED` only as compatibility alias if still supported
   - `MAX_BOT_TOKEN`
   - `MAX_PUBLIC_BOT_NAME`
   - `MAX_MINIAPP_URL`
   - `MAX_BOT_API_SECRET` with legacy fallback if the code still supports older naming
   - `MAX_WEBHOOK_URL`
   - `MAX_INIT_DATA_MAX_AGE_SECONDS`
4. Write runbooks in operator/ops language, not architecture prose.
5. If real provider creds/env are absent, record an explicit external blocker. Never simulate a successful provider smoke.
6. Rollback must disable new operator actions first, then disable runtime send/launch, then turn off provider subscription if one exists.

## Required Output

- preflight checklist
- exact enable order
- smoke steps
- rollback order
- owner actions
- support notes and known failure codes
- explicit statement of what is and is not proven
