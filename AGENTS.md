# AGENTS.md

Project-level operating rules for Codex in Attila Recruiting.

## 1. Canonical Docs And Precedence

Use this order when docs conflict:

1. [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
4. [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
5. [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
6. [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
7. [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)
8. subsystem docs in [docs](/Users/mikhail/Projects/recruitsmart_admin/docs)
9. historical/reference material in [codex](/Users/mikhail/Projects/recruitsmart_admin/codex)

Current Codex workspace layer:

- project-scoped config: [`.codex/config.toml`](/Users/mikhail/Projects/recruitsmart_admin/.codex/config.toml)
- compatibility shim: [`.codexrc`](/Users/mikhail/Projects/recruitsmart_admin/.codexrc)
- reusable skills: [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/)

If a workflow or command is described in older docs but conflicts with the current root docs or live code, treat the older material as historical unless the codebase proves otherwise.

## 2. Repository Shape

Attila Recruiting is a production CRM/ATS monorepo with:

- FastAPI backend in [backend](/Users/mikhail/Projects/recruitsmart_admin/backend)
- React 18 SPA in [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- Vite-built bundle served from [frontend/dist](/Users/mikhail/Projects/recruitsmart_admin/frontend/dist)
- PostgreSQL/Alembic persistence
- Redis-backed notifications/cache flows
- Telegram bot and MAX bot runtimes
- candidate portal, recruiter dashboard, slot scheduling, messaging, analytics, and automation flows

Key boundaries:

- backend entrypoint: [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- admin API: [backend/apps/admin_api/main.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/main.py)
- Telegram bot: [backend/apps/bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/app.py)
- MAX bot: [backend/apps/max_bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot/app.py)
- SPA route map: [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- shell / navigation: [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)

## 3. Mandatory Workflow

When a request is clear enough to act on:

1. Read the relevant canonical docs first.
2. Inspect the exact files you plan to touch.
3. Identify side effects, callers, data flow, and rollback surface.
4. Choose the smallest safe implementation path.
5. Check security, scalability, and domain integrity before editing medium/high-risk paths.
6. Verify version-sensitive behavior against official docs and MCP-backed sources, not memory.
7. Make the change in a small, reviewable batch.
8. Run the relevant validation commands.
9. Report what changed, why, verification performed, and residual risk.

Ask questions only if a wrong assumption could break production, corrupt data, or produce an unsafe architecture.

## 4. Risk Tiers

### Low risk

- docs
- copy
- styling
- harmless UI polish
- workflow shims

### Medium risk

- business logic
- queries
- integrations
- internal workflow changes
- recruiter-facing UI behavior

### High risk

- auth / permissions
- candidate portal token exchange
- scheduling / slot assignment
- status transitions
- migrations
- queueing / retries
- webhooks
- external side effects
- AI-generated outputs that affect business actions

### Required gates for high risk

- architecture review first
- security review
- scalability review
- rollback plan
- validation plan with explicit commands
- no silent fallbacks
- no duplicate side effects on retries

## 5. Security, Scalability, And Data Integrity Rules

- Preserve candidate, recruiter, slot, office, city, interview, and analytics data integrity.
- Treat client-side state as untrusted unless the server validates it.
- Keep side effects idempotent where practical.
- Retries must not duplicate external actions.
- Critical business actions must be observable via logs, statuses, or events.
- Do not weaken auth/session/CSRF/webhook checks to make a flow “work”.
- Do not log secrets, tokens, or unnecessary PII.
- Prefer explicit contracts and typed interfaces.
- Prefer deterministic scheduling and auditable state transitions.

## 6. Documentation And Version-Sensitive Decisions

For OpenAI/Codex/MCP/Agents SDK/API usage and any version-sensitive dependency behavior:

- verify against current official documentation or MCP-backed docs first
- do not rely on memory for current APIs or recommended production practice
- if docs/MCP are unavailable, say so explicitly and use the safest documented fallback

Use current docs-backed sources for:

- Codex CLI/config behavior
- MCP server configuration
- OpenAI API / Agents SDK changes
- framework/library upgrades
- security-sensitive defaults

## 7. Repo-Local Skills

Use skills from [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/) for repeated work:

- `architecture-review`
- `security-gate`
- `scalability-review`
- `dependency-upgrade-check`
- `release-readiness`
- `recruiter-crm-domain-check`

When a skill matches the task, use it before editing. Do not use a skill for trivial docs-only or copy-only work.

## 8. Multi-Agent Workflow

Recommended subagents:

- Architect: map code boundaries, side effects, and minimal safe plan
- Implementer: apply the approved diff with minimal scope
- Security Reviewer: challenge auth, secrets, CSRF, webhooks, trust boundaries, and retries
- Scalability Reviewer: inspect hot paths, query count, caching, concurrency, and burst behavior
- UI/UX Reviewer: review recruiter/admin and candidate-facing clarity, next actions, and hierarchy
- Docs / Version Verifier: confirm version-sensitive decisions against current docs/MCP
- QA / Browser Flow Reviewer: validate critical browser or portal flows

Use parallel agents only when file ownership is disjoint. Do not parallelize edits in merge-risk zones without coordination.

## 9. Validation Expectations

- Docs-only changes: verify any commands or workflows you changed or referenced; for repo-wide workflow changes, run the standard frontend gate unless the task explicitly forbids it.
- Frontend changes: run `lint`, `typecheck`, `test`, and `build:verify`; add Playwright smoke when shell, routing, portal, or critical UI flows change.
- Backend changes: run `make test`; add targeted commands when touching migrations, integrations, async workflows, or external side effects.
- High-risk changes: add tighter targeted tests before broad validation.
- Do not mark work complete without reporting the exact commands and outcomes.

## 10. Git Discipline

- Expect a dirty worktree; do not revert unrelated user changes.
- Work in small logical batches.
- Prefer isolated worktrees or clearly bounded file ownership for concurrent work.
- Use Conventional Commits when creating commits.
- Do not leave temporary task/spec/checklist markdown in repo root after the task is closed.

## 11. Final Response Shape

For implementation tasks, keep the final response short and structured:

1. what changed
2. why this approach
3. security review
4. scalability review
5. validation performed
6. remaining risks
7. follow-up suggestions

## 12. Merge-Risk Zones

Treat these as coordination-sensitive:

- [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
- [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
- [frontend/app/src/theme/mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)
- [frontend/app/src/theme/pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
- [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- [backend/core/settings.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py)
- [backend/core/db.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/db.py)
- [backend/migrations](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations)

## 13. Done Criteria

Work is done only when:

1. the change set stays within scope
2. relevant validation commands were run and reported
3. durable docs were updated if behavior or process changed
4. risks and leftovers were called out explicitly
5. the next agent can resume without rediscovery
