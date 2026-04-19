# AGENTS.md

Operational guide for Codex in RecruitSmart.

## 1. Purpose And Current Reality

RecruitSmart is a production CRM/ATS monorepo for recruiting workflows in the Russian market context.

Current supported runtime:

- Admin SPA
- Telegram bot runtime
- Telegram Mini App / recruiter webapp
- HH integration
- n8n HH callbacks

Guarded pilot boundary:

- bounded MAX operator rollout surface in `admin_ui`
- bounded MAX launch/auth, webhook, and `/miniapp` host shell in `admin_api`
- bounded MAX candidate mini-app surface at `/miniapp` over shared `candidate_access`, default-off
- shared candidate journey reused for MAX pilot

Unsupported historical runtime:

- legacy candidate portal implementation
- historical MAX runtime

Target state only, not current runtime:

- standalone candidate web flow
- full MAX runtime / channel rollout beyond bounded pilot
- SMS / voice fallback integration

Operational rules:

- Telegram is the only supported live messaging runtime today, but it must not be treated as the only future candidate channel.
- Browser and SMS docs may describe target architecture. MAX docs may describe either the mounted bounded pilot or future full rollout; distinguish those states before making runtime decisions.
- Any new MAX work must land as a bounded adapter layer over shared backend contracts, not as a restoration of the removed historical MAX runtime.
- The bounded MAX pilot surface exists now at `/api/max/launch`, `/api/max/webhook`, `/miniapp`, shared `/api/candidate-access/*`, and bounded operator rollout controls, but it is default-off and controlled-pilot only. It is not a production runtime rollout.
- Shared candidate journey and business logic remain canonical for MAX. Do not fork Test1, screening, booking, or launch semantics into MAX-only logic.
- Browser candidate rollout, SMS rollout, analytics cutover, and messaging v2 full rollout remain out of scope unless the task explicitly changes that.
- Do not auto-merge candidates or guess requisition aggressively; ambiguity still defaults to `applications.requisition_id = null`.
- Root [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md) is the single agent guide for this repo. Add nested `AGENTS.md` only if a subtree needs materially different rules.

## 2. Canonical Sources And Precedence

When sources conflict, use this order:

1. Live code and mounted entrypoints:
   - [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
   - [backend/apps/admin_api/main.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/main.py)
   - [backend/apps/bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/app.py)
   - [bot.py](/Users/mikhail/Projects/recruitsmart_admin/bot.py)
   - [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
2. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
4. [docs/README.md](/Users/mikhail/Projects/recruitsmart_admin/docs/README.md)
5. Canonical docs under:
   - [docs/architecture](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture)
   - [docs/security](/Users/mikhail/Projects/recruitsmart_admin/docs/security)
   - [docs/frontend](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend)
   - [docs/qa](/Users/mikhail/Projects/recruitsmart_admin/docs/qa)
   - [docs/data](/Users/mikhail/Projects/recruitsmart_admin/docs/data)
6. Stream-specific reports, specs, RFCs, and ADRs as implementation truth for their stream
7. Historical material in [docs/archive](/Users/mikhail/Projects/recruitsmart_admin/docs/archive) and stale legacy docs

Current Codex workspace layer:

- project config: [`.codex/config.toml`](/Users/mikhail/Projects/recruitsmart_admin/.codex/config.toml)
- compatibility shim: [`.codexrc`](/Users/mikhail/Projects/recruitsmart_admin/.codexrc)
- reusable skills: [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/)

Treat these as non-canonical for operational decisions unless live code or canonical docs explicitly point back to them:

- [docs/MIGRATIONS.md](/Users/mikhail/Projects/recruitsmart_admin/docs/MIGRATIONS.md)
- [docs/TECHNICAL_OVERVIEW.md](/Users/mikhail/Projects/recruitsmart_admin/docs/TECHNICAL_OVERVIEW.md)
- [docs/project/CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/docs/project/CODEX.md)
- [docs/project/CLAUDE.md](/Users/mikhail/Projects/recruitsmart_admin/docs/project/CLAUDE.md)
- [docs/project/CONTRIBUTING.md](/Users/mikhail/Projects/recruitsmart_admin/docs/project/CONTRIBUTING.md)
- stale gate artifacts under [docs/gates](/Users/mikhail/Projects/recruitsmart_admin/docs/gates) if they conflict with current runtime truth

## 3. Repository Map

- [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py): main admin/browser runtime, auth/session/CSRF boundary, admin SPA host
- [backend/apps/admin_api/main.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api/main.py): Telegram/recruiter webapp boundary and HH callback boundary
- [backend/apps/bot/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot/app.py) and [bot.py](/Users/mikhail/Projects/recruitsmart_admin/bot.py): Telegram runtime
- [backend/domain](/Users/mikhail/Projects/recruitsmart_admin/backend/domain): domain logic and business truth
- [backend/migrations](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations) and [scripts/run_migrations.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/run_migrations.py): schema path
- [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app): SPA source, unit tests, Playwright tests, Vite config
- [frontend/dist](/Users/mikhail/Projects/recruitsmart_admin/frontend/dist): checked-in built bundle served by backend
- [docs/architecture](/Users/mikhail/Projects/recruitsmart_admin/docs/architecture), [docs/security](/Users/mikhail/Projects/recruitsmart_admin/docs/security), [docs/frontend](/Users/mikhail/Projects/recruitsmart_admin/docs/frontend), [docs/qa](/Users/mikhail/Projects/recruitsmart_admin/docs/qa), [docs/data](/Users/mikhail/Projects/recruitsmart_admin/docs/data): canonical documentation domains
- [scripts/check_openapi_drift.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/check_openapi_drift.py) and [scripts/export_openapi.py](/Users/mikhail/Projects/recruitsmart_admin/scripts/export_openapi.py): OpenAPI tooling
- [artifacts/verification](/Users/mikhail/Projects/recruitsmart_admin/artifacts/verification) and architecture reports: evidence only, not runtime truth

Coordination-sensitive paths:

- [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
- [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
- [frontend/app/src/theme/mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)
- [frontend/app/src/theme/pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
- [backend/apps/admin_ui/app.py](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui/app.py)
- [backend/core/settings.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/settings.py)
- [backend/core/db.py](/Users/mikhail/Projects/recruitsmart_admin/backend/core/db.py)
- [backend/migrations](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations)

## 4. How Codex Should Work Here

When a request is clear enough to act on:

1. Read the relevant canonical docs first.
2. Inspect the exact files you plan to touch.
3. Map side effects, callers, data flow, and rollback surface.
4. Choose the smallest safe implementation path.
5. Use plan-first thinking for multi-file, medium-risk, and high-risk changes.
6. Use multi-agent review for non-trivial changes. Parallelize only when file ownership is disjoint.
7. Make one narrow logical batch, validate it, then move to the next batch.
8. Do not widen scope on your own. Do not mix unrelated cleanup into the same diff.
9. Ask questions only if a wrong assumption could break production, corrupt data, or force unsafe architecture.

## 5. Current Project Stage And Split Discipline

Current active streams:

- PR1: hardening/runtime/docs cleanup
- PR2: Phase A schema foundation
- PR3: Phase B skeleton/adapters
- PR4: profiler/report/data-quality
- PR5: persistent idempotency, first bounded dual-write path, and proof packaging

Current backend reality for this phase:

- `backend/migrations/versions/0102_phase_a_schema_foundation.py` and `backend/migrations/versions/0103_persistent_application_idempotency_keys.py` are already present in the live workspace.
- The first backend dual-write path (`candidate create`) already exists behind `CANDIDATE_CREATE_DUAL_WRITE_ENABLED=false`.
- Backend phase is not closed until a second bounded dual-write path and a fresh integrated PostgreSQL proof, or a single explicit external blocker, are recorded.

Rules:

- Do not mix these streams in one PR or one change set unless the task explicitly says to unify them.
- Before touching runtime, migrations, OpenAPI, candidate journey, or analytics, check whether the task overlaps PR1, PR2, PR3, or PR5 boundaries.
- Prefer one narrow scope, run checks, then move to the next stream.
- After each meaningful milestone, run the relevant validation commands and update the execution log before moving on.

Migration/runtime discipline:

- [backend/migrations/versions/0102_phase_a_schema_foundation.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0102_phase_a_schema_foundation.py) and [backend/migrations/versions/0103_persistent_application_idempotency_keys.py](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations/versions/0103_persistent_application_idempotency_keys.py) are foundation layers.
- No runtime cutover from foundation or schema-only tasks.
- No real dual-write before the persistent idempotency layer exists.
- No candidate portal restoration or MAX runtime restoration as part of foundation or hardening work.

## 6. Engineering Constraints And Do-Not Rules

- Do not guess requisition from weak demand, Telegram presence, city, or source alone.
- Ambiguous demand must default to `applications.requisition_id = null`.
- Do not auto-merge duplicate or ambiguous candidates or ownership records.
- Do not let `n8n` write directly to PostgreSQL or event tables.
- Business mutation and `application_events` insert must be in the same database transaction on any new dual-write path.
- `application_events` is append-only. Corrections are follow-up events, not row edits.
- No real dual-write before persistent idempotency exists.
- No browser candidate rollout, no full MAX runtime/channel rollout, and no SMS runtime rollout without an explicit separate task or milestone.
- No analytics cutover inside foundation or runtime-hardening work.
- No backfill, cleanup, or runtime enablement unless the task explicitly asks for it.
- OpenAPI truth must come from live app factories, not manual edits of generated schema files.

## 7. Risk Gates, Security, And Data Integrity

Low risk:

- docs
- copy
- styling
- harmless UI polish
- workflow shims

Medium risk:

- business logic
- queries
- integrations
- recruiter-facing UI behavior
- internal workflow changes

High risk:

- auth / permissions
- scheduling / slot assignment
- status transitions
- migrations
- queueing / retries
- webhooks
- external side effects
- AI-generated outputs that affect business actions

Required gates for high risk:

- architecture review first
- security review
- scalability review
- rollback plan
- validation plan with explicit commands
- no silent fallbacks
- no duplicate side effects on retries

Always preserve:

- candidate, recruiter, slot, office, city, interview, and analytics data integrity
- client state treated as untrusted unless the server validates it
- idempotent side effects where practical
- no weakened auth, session, CSRF, or webhook protections
- no secrets or unnecessary PII in logs
- deterministic scheduling and auditable state transitions

## 8. Documentation And Version-Sensitive Decisions

For OpenAI, Codex, MCP, Agents SDK, or any version-sensitive dependency behavior:

- verify against current official documentation or MCP-backed docs first
- do not rely on memory for current APIs or defaults
- if docs or MCP are unavailable, say so explicitly and use the safest documented fallback

Use current docs-backed sources for:

- Codex CLI and config behavior
- MCP server configuration
- OpenAI API or Agents SDK behavior
- framework or library upgrades
- security-sensitive defaults

## 9. Repo-Local Skills

Use repo-local skills from [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/) when the task matches:

- `architecture-review`
- `security-gate`
- `scalability-review`
- `dependency-upgrade-check`
- `release-readiness`
- `recruiter-crm-domain-check`

Do not use a skill for trivial docs-only or copy-only work.

## 10. Validation Policy

After each meaningful milestone, run the checks relevant to the touched scope and report exact outcomes.

Core Python checks:

- `python -m py_compile <touched_python_files>`
- `ruff check <touched_or_new_python_files>`
- focused `python -m pytest ...` or `make test`

Schema and API checks:

- `make test-postgres-proof` when schema or migration behavior is touched
- `make openapi-check` or `python scripts/check_openapi_drift.py` when routes, contracts, schema generation, or OpenAPI tooling are touched

Frontend checks:

- `npm --prefix frontend/app run lint`
- `npm --prefix frontend/app run typecheck`
- `npm --prefix frontend/app run test`
- `npm --prefix frontend/app run build:verify`
- `npm --prefix frontend/app run test:e2e:smoke` for critical UI, shell, routing, or browser flow changes

Rules:

- If a command cannot run because dependencies, services, or env are missing, say so explicitly.
- If you add prep code for a future runtime step, include proof that no runtime wiring was enabled yet.
- Do not cite or rely on deprecated bootstrap/demo commands from old docs, or on root-level `npm run ...`.

## 11. Git And Workspace Discipline

- Expect a dirty worktree. Do not revert unrelated user changes.
- Prefer isolated worktrees or branches for non-trivial tasks.
- Work in small logical batches.
- Use Conventional Commits when creating commits.
- Do not leave temporary task, prompt, checklist, or spec markdown in repo root after the task is closed.
- Do not use destructive reset or checkout commands unless explicitly requested.

## 12. Final Response And Definition Of Done

For implementation tasks, keep the final response short and structured:

1. what changed
2. why this approach
3. security review
4. scalability review
5. validation performed
6. remaining risks
7. follow-up suggestions

Work is done only when:

1. the change set stays within scope
2. relevant validation commands were run and reported
3. durable docs were updated if behavior or process changed
4. no unintended runtime wiring or scope mixing was introduced
5. risks, leftovers, and blockers were called out explicitly
6. the next agent can resume without rediscovery
