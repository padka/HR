# Multi-Agent Strategy

## Goal

Use multiple Codex agents only where this repository can support parallelism without constant merge conflict or architectural drift.

## Project-Specific Constraints

The following areas are high-conflict and should be treated as single-threaded:
- [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
- [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- [frontend/app/src/theme/tokens.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.css)
- [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
- [frontend/app/src/theme/pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
- [frontend/app/src/theme/mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)
- [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- [backend/core/settings.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py)
- [backend/core/db.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/db.py)
- [backend/migrations](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations)
- root canonical docs

## Safe Parallel Work Types

- Docs-only tasks that do not change the same canonical files
- Codebase exploration and audit collection
- Route-level implementation after shell/theme contracts are stabilized
- Test additions for already-stable behavior
- Integration-specific backend work isolated from shared settings/auth
- QA and regression passes after implementation waves land

## Work Types That Should Remain Single-Threaded

- Theme/token refactors
- App shell and mobile navigation changes
- Auth/session/security changes
- Migration and DB contract changes
- Root workflow/documentation precedence changes
- Large monolithic screen refactors in the same file

## Recommended Ownership Boundaries

### Foundation Owner

Owns:
- theme tokens
- surface ladder
- shell/layout contract
- app shell/mobile sheet behavior

Files:
- `frontend/app/src/theme/*.css`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/main.tsx`

### Recruiter Workflow Owner

Owns after foundation is stable:
- dashboard
- incoming
- slots
- candidates
- candidate detail
- messenger
- calendar

Files:
- `frontend/app/src/app/routes/app/dashboard.tsx`
- `incoming.tsx`
- `slots.tsx`
- `candidates.tsx`
- `candidate-detail.tsx`
- `messenger.tsx`
- `calendar.tsx`

### Admin Workflow Owner

Owns after foundation is stable:
- cities / city-edit / city-new
- recruiters / recruiter-edit / recruiter-new
- templates / questions / message-templates
- system / test-builder / detailization / simulator / copilot

### Backend Integration Owner

Owns:
- HH integration
- bot and max-bot additions
- service-layer work that does not alter shared auth/session/db contracts

### QA / Hardening Owner

Owns:
- Playwright smoke/e2e
- Vitest additions
- accessibility checks
- rollout and regression verification

## Merge-Risk Zones

- `global.css` because it spans almost every route
- `__root.tsx` because it owns shell, nav, polling, and mobile behaviors
- `candidate-detail.tsx` because it is both large and state-dense
- `city-edit.tsx` and other high-inline-debt forms because visual extraction can collide with adjacent admin cleanup
- backend settings/db/auth because many services depend on them

## Recommended Parallelization Sequence

1. Single-thread foundation and shell
2. Freeze contract for page shell, surfaces, toolbar, state blocks, and mobile nav
3. Split recruiter screens into parallel substreams only after step 2 lands
4. Run QA/playwright in parallel with late-stage screen polish, not before structure stabilizes
5. Tackle admin cleanup after recruiter flows if shared component contracts are settled

## Suggested Cluster Map

- Cluster A: foundation + shell
- Cluster B: recruiter daily ops screens
- Cluster C: admin forms and configuration screens
- Cluster D: integrations and messaging
- Cluster E: QA, accessibility, responsive hardening
- Cluster F: docs and rollout artifacts

## Coordination Rules

- One agent owns one merge-risk file at a time
- Parallel agents must declare file boundaries up front
- If two tasks need the same theme or shell file, merge them into one stream
- If a shared component contract changes, dependent agents pause and rebase after the contract lands

## Branch / Worktree Guidance

- Use branch names with `codex/` prefix
- Prefer one branch per wave or clean ownership boundary
- Do not stack unrelated implementation streams on top of an unstable foundation branch

## Recommended Sequence For Future Redesign Work

1. W1 foundation tokens and surfaces
2. W2 shell and mobile navigation
3. W3 shared component primitives
4. W4 recruiter-first screens
5. W5 mobile hardening
6. W6 admin cleanup
7. W7 regression, motion, accessibility, responsive QA
