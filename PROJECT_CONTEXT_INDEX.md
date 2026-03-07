# Project Context Index

## What This Project Is

RecruitSmart Admin is a production recruiting CRM/ATS repository with a FastAPI backend, a React SPA admin interface, recruiter operations workflows, candidate scheduling, messaging, and bot/integration support.

## Main Subsystems

- Backend admin server: [backend/apps/admin_ui](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_ui)
- Backend admin API / webapp helpers: [backend/apps/admin_api](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/admin_api)
- Domain and shared infrastructure: [backend/domain](/Users/mikhail/Projects/recruitsmart_admin/backend/domain), [backend/core](/Users/mikhail/Projects/recruitsmart_admin/backend/core)
- Frontend SPA: [frontend/app](/Users/mikhail/Projects/recruitsmart_admin/frontend/app)
- Telegram/Max workers: [backend/apps/bot](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/bot), [backend/apps/max_bot](/Users/mikhail/Projects/recruitsmart_admin/backend/apps/max_bot)
- Migrations: [backend/migrations](/Users/mikhail/Projects/recruitsmart_admin/backend/migrations)
- Scripts/tooling: [scripts](/Users/mikhail/Projects/recruitsmart_admin/scripts), [tools](/Users/mikhail/Projects/recruitsmart_admin/tools)

## Read Order For Future Agents

1. [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
4. [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
5. Relevant planning or execution spec for the task area

## Canonical Doc Sets

### Repo Operating Layer

- [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
- [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
- [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
- [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
- [CURRENT_TASK_TEMPLATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_TASK_TEMPLATE.md)
- [SESSION_LOG_TEMPLATE.md](/Users/mikhail/Projects/recruitsmart_admin/SESSION_LOG_TEMPLATE.md)
- [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)
- [MULTI_AGENT_STRATEGY.md](/Users/mikhail/Projects/recruitsmart_admin/MULTI_AGENT_STRATEGY.md)
- [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)

### Redesign Planning Canon

- [DESIGN_REDESIGN_PRD.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_REDESIGN_PRD.md)
- [DESIGN_AUDIT_REPORT.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_AUDIT_REPORT.md)
- [UI_PRINCIPLES_AND_LAYOUT_PATTERNS.md](/Users/mikhail/Projects/recruitsmart_admin/UI_PRINCIPLES_AND_LAYOUT_PATTERNS.md)
- [RESPONSIVE_AND_MOBILE_AUDIT.md](/Users/mikhail/Projects/recruitsmart_admin/RESPONSIVE_AND_MOBILE_AUDIT.md)
- [SCREEN_ARCHITECTURE_MAP.md](/Users/mikhail/Projects/recruitsmart_admin/SCREEN_ARCHITECTURE_MAP.md)
- [DESIGN_SYSTEM_PLAN.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_SYSTEM_PLAN.md)
- [MOTION_AND_INTERACTION_GUIDELINES.md](/Users/mikhail/Projects/recruitsmart_admin/MOTION_AND_INTERACTION_GUIDELINES.md)
- [IMPLEMENTATION_ROADMAP_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/IMPLEMENTATION_ROADMAP_FOR_CODEX.md)
- [ACCEPTANCE_CRITERIA.md](/Users/mikhail/Projects/recruitsmart_admin/ACCEPTANCE_CRITERIA.md)
- [DESIGN_QA_CHECKLIST.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_QA_CHECKLIST.md)
- [EXECUTIVE_SUMMARY.md](/Users/mikhail/Projects/recruitsmart_admin/EXECUTIVE_SUMMARY.md)

### Codex Execution Handoff Canon

- [DESIGN_DECISIONS_LOG.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_DECISIONS_LOG.md)
- [CODEX_EXECUTION_PLAN.md](/Users/mikhail/Projects/recruitsmart_admin/CODEX_EXECUTION_PLAN.md)
- [EPIC_BREAKDOWN_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/EPIC_BREAKDOWN_FOR_CODEX.md)
- [TASK_GRAPH_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/TASK_GRAPH_FOR_CODEX.md)
- [COMPONENT_IMPLEMENTATION_SPECS.md](/Users/mikhail/Projects/recruitsmart_admin/COMPONENT_IMPLEMENTATION_SPECS.md)
- [SCREEN_IMPLEMENTATION_SPECS.md](/Users/mikhail/Projects/recruitsmart_admin/SCREEN_IMPLEMENTATION_SPECS.md)
- [CODEX_FIRST_WAVE_RECOMMENDATION.md](/Users/mikhail/Projects/recruitsmart_admin/CODEX_FIRST_WAVE_RECOMMENDATION.md)
- [ROLLOUT_AND_REGRESSION_STRATEGY.md](/Users/mikhail/Projects/recruitsmart_admin/ROLLOUT_AND_REGRESSION_STRATEGY.md)

## Current Active Scope

- Frontend redesign planning and execution preparation for `31` mounted SPA routes from [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- First implementation priority: foundation, shell, recruiter-first screens, mobile hardening, then admin cleanup
- Active frontend critical files:
  - [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx)
  - [frontend/app/src/theme/tokens.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.css)
  - [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css)
  - [frontend/app/src/theme/pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
  - [frontend/app/src/theme/mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)

## Backlog / Not First-Wave Scope

- Dormant route files not mounted in the current SPA router:
  - [frontend/app/src/app/routes/app/vacancies.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/vacancies.tsx)
  - [frontend/app/src/app/routes/app/reminder-ops.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/reminder-ops.tsx)
- Historical reports and alternate drafts in repo root and [docs/archive](/Users/mikhail/Projects/recruitsmart_admin/docs/archive)
- Older `codex/` bootstrap/context files that reference retired Jinja/Tailwind workflows

## Where To Look First By Task Type

- Repo setup / workflow: [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md), [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md), [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
- Frontend redesign: [DESIGN_DECISIONS_LOG.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_DECISIONS_LOG.md), [CODEX_EXECUTION_PLAN.md](/Users/mikhail/Projects/recruitsmart_admin/CODEX_EXECUTION_PLAN.md), [SCREEN_IMPLEMENTATION_SPECS.md](/Users/mikhail/Projects/recruitsmart_admin/SCREEN_IMPLEMENTATION_SPECS.md)
- Backend/domain changes: inspect touched modules directly, then use subsystem docs under [docs](/Users/mikhail/Projects/recruitsmart_admin/docs)
- QA / regression / rollout: [ROLLOUT_AND_REGRESSION_STRATEGY.md](/Users/mikhail/Projects/recruitsmart_admin/ROLLOUT_AND_REGRESSION_STRATEGY.md), [DESIGN_QA_CHECKLIST.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_QA_CHECKLIST.md)
