# Current Program State

## Snapshot

- Repository: RecruitSmart Admin
- Mode: local development only by default
- Production/VPS: do not touch unless the user explicitly asks
- Root markdown cleanup: completed on `2026-03-08`

## What Is Already Landed In Code

- React SPA is the active frontend in [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- shared theme/token system lives in [frontend/app/src/theme](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme)
- recruiter/incoming/test-preview/light-theme work has already been implemented in code
- backend reschedule/status fixes have already been implemented in code
- candidate messenger now runs on candidate threads with archive state, wider 2-column chat workspace, on-demand right details drawer, pinned agreement/timeline block, sticky composer, intro-day scheduling from messenger using city templates, local recruiter notes, quick templates/status actions, and local unread/read notifications
- candidate messenger second-pass redesign is landed locally: hero block removed, left rail simplified for faster triage, chat header/status summary/composer rebuilt for operational clarity, and the right drawer now acts as a decision rail focused on status, next step, risk, progress, and recruiter notes
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
