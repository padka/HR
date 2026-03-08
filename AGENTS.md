# AGENTS.md

## Project Overview

RecruitSmart Admin is a production CRM/ATS monorepo with:
- FastAPI backend in [backend](/Users/mikhail/Projects/recruitsmart_admin/backend)
- React 18 SPA in [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- Vite-built frontend bundle served by backend from [frontend/dist](/Users/mikhail/Projects/recruitsmart_admin/frontend/dist)
- supporting bot/integration modules in [backend/apps/bot](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot) and [backend/apps/max_bot](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot)

This repository has already gone through multiple planning and implementation passes. Future Codex runs should reuse durable docs and live code, not recreate closed-task markdown packages.

## Architecture Summary

- Backend entrypoint: [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- SPA route map: [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- frontend shell and mobile navigation: [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
- frontend theme system:
  - [frontend/app/src/theme/tokens.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.css)
  - [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
  - [frontend/app/src/theme/components.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/components.css)
  - [frontend/app/src/theme/pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
  - [frontend/app/src/theme/mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)
  - [frontend/app/src/theme/motion.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/motion.css)
  - [frontend/app/src/theme/material.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/material.css)

## Directory Guide

- [backend](/Users/mikhail/Projects/recruitsmart_admin/backend): apps, domain logic, migrations, shared infra
- [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app): SPA source, tests, build config
- [docs](/Users/mikhail/Projects/recruitsmart_admin/docs): subsystem docs and runbooks
- [codex](/Users/mikhail/Projects/recruitsmart_admin/codex): older Codex notes/tasks/reports; useful for history, not always canonical
- [scripts](/Users/mikhail/Projects/recruitsmart_admin/scripts): migration/dev/perf/smoke helpers
- [tests](/Users/mikhail/Projects/recruitsmart_admin/tests): backend tests
- [artifacts](/Users/mikhail/Projects/recruitsmart_admin/artifacts): generated outputs, screenshots, reports

## Canonical Docs And Precedence

Use this precedence order when documents conflict:

1. Root durable repo-operating docs:
   - [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
   - [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
   - [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
   - [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
   - [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
   - [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)
2. Current subsystem docs in [docs](/Users/mikhail/Projects/recruitsmart_admin/docs)
3. Historical/reference material in [codex](/Users/mikhail/Projects/recruitsmart_admin/codex) and [docs/archive](/Users/mikhail/Projects/recruitsmart_admin/docs/archive)

Important: several older files under `codex/`, `docs/project/`, and `docs/LOCAL_DEV.md` still reference pre-SPA or migrated workflows. Treat them as historical context unless confirmed against the current codebase.

## Read This First

Before touching code:

1. Read [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. Read [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
3. Read [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
4. Read [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
5. Open [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
6. Check `git status --short`
7. Inspect the exact files you plan to touch
8. Only then make a plan

## Run / Test / Build

Primary commands:

```bash
make install
npm --prefix frontend/app install
make dev-migrate
make dev-admin
make dev-bot
make test
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

Use [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md) for when each command is required and what it validates.

## Working Rules For Agents

- Inspect before changing code. Do not trust stale documentation over live code.
- Keep tasks narrow. One logical change set per batch.
- Do not keep closed-task markdown files in repo root.
- If you create a temporary prompt/TODO/spec/checklist markdown file, delete it before closing the task unless the user explicitly asked for a durable artifact.
- Do not make backend API or route-path changes during frontend setup/refactor tasks unless explicitly required.
- Do not revert unrelated user changes in a dirty worktree.
- Prefer shared classes/utilities over new inline styles.
- Update canonical docs when repo operating policy, active scope, or verification workflow changes.

## Planning-First Expectations

- For non-trivial tasks, identify touched files, dependencies, and verification steps before editing.
- For redesign or UX tasks, start from live code plus relevant subsystem docs in [docs](/Users/mikhail/Projects/recruitsmart_admin/docs).
- For repo/workflow tasks, start from:
  - [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
  - [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
  - [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
  - [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)

## Verification Expectations

- Docs-only changes: verify any commands you changed or referenced; for repo-wide workflow changes, run the standard frontend gate unless the task explicitly forbids it.
- Frontend changes: run `lint`, `typecheck`, `test`, and `build:verify`; add Playwright smoke when UI, shell, or routing behavior changes.
- Backend changes: run `make test`; add targeted commands for migrations, integrations, or async workflows if touched.
- Do not mark work done without reporting exact commands and outcomes.

## Regression-Minimization Rules

- Treat these as merge-risk zones:
  - [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
  - [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
  - [frontend/app/src/theme/mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)
  - [frontend/app/src/theme/pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
  - [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
  - [backend/core/settings.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py)
  - [backend/core/db.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/db.py)
  - [backend/migrations](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations)
- Do not parallelize edits to those areas without explicit coordination.

## Scope Discipline

- This repo currently has active redesign planning for `31` mounted SPA routes.
- Dormant route files `vacancies.tsx` and `reminder-ops.tsx` are backlog, not first-wave scope.
- If the task is repo setup, documentation, or workflow normalization, do not drift into product redesign or feature implementation.

## Multi-Agent Guidance

- Safe parallel work: route-level audits, docs-only tasks, isolated tests, post-foundation screen work, integration-specific docs.
- Single-threaded work: theme foundations, app shell, migrations, root canonical docs, auth/security core.
- If parallel agents are used, assign ownership by area and log boundaries in the task brief or session log.
- If a task needs temporary coordination notes, keep them local to the task and delete them before closing.

## Long-Session Workflow

- For long work, keep progress in the conversation and fold durable outcomes back into:
  - [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
  - [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
- Do not accumulate closed `CURRENT_TASK` / `SESSION_LOG` style markdown files in repo root.
- Update [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md) if the active scope or implementation state materially changes.

## Done Criteria

Work is done only when:

1. The change set stays within scope
2. Verification commands were run and reported
3. Relevant docs were updated if behavior or process changed
4. Risks and leftovers were called out explicitly
5. The next agent can resume without re-discovery
