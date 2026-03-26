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
- MAX webhook bot now supports public candidate onboarding plus CRM linking: candidates can start profile + screening in MAX from the bot link directly, admin can still issue a MAX deep link to bind an existing CRM candidate, recruiter chat can route through MAX, and the candidate portal now also opens as a MAX mini app with a `startapp` invite link for the personal cabinet
- live MAX readiness is now explicit instead of implicit: admin health and candidate channel health expose `token_valid`, bot profile resolution, MAX link-base source, webhook public readiness, subscription readiness, and deterministic delivery block reasons; local public bootstrap is standardized via `make dev-max-live`
- candidate messenger now runs as a focused two-pane recruiter workspace: compact inbox rail on the left, chat workspace on the right, sticky composer, quick templates, local unread/read notifications, and direct link-out to the candidate card without inline candidate-details rail
- candidate messenger second-pass redesign is landed locally: hero block removed, left rail simplified for faster triage, chat header/composer rebuilt for operational clarity, and the previous inline candidate-details drawer has been removed from the route
- interview reminder flow now includes a candidate-facing readiness message 10 minutes before the meeting, delivered through the existing reminder scheduler/outbox pipeline
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
