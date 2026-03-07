# Current Program State

Updated: 2026-03-07

## Current Situation

The repository is not a greenfield codebase. It already contains:
- a working production backend and SPA
- a large set of redesign planning documents
- a Codex-ready implementation handoff package
- a dirty, actively changing worktree across backend, frontend, and docs

Future agents should assume that planning is largely complete, but implementation state must always be confirmed against live code and current git status.

## What Has Already Been Done

### Planning Complete

The redesign planning package already exists in repo root:
- PRD
- design audit
- responsive/mobile audit
- screen architecture map
- design system plan
- motion guidelines
- acceptance criteria
- QA checklist
- executive summary

The Codex execution handoff package also already exists in repo root:
- decisions log
- execution plan
- epic breakdown
- task graph
- component implementation specs
- screen implementation specs
- first-wave recommendation
- rollout/regression strategy

### Repo Operating Layer Added

The repo now has a root operating layer for future Codex sessions:
- [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
- [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
- [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
- [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
- [CURRENT_TASK_TEMPLATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_TASK_TEMPLATE.md)
- [SESSION_LOG_TEMPLATE.md](/Users/mikhail/Projects/recruitsmart_admin/SESSION_LOG_TEMPLATE.md)
- [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)
- [MULTI_AGENT_STRATEGY.md](/Users/mikhail/Projects/recruitsmart_admin/MULTI_AGENT_STRATEGY.md)
- [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)

### First-Wave Implementation Started

The first implementation wave is no longer planning-only.

Completed in the current shared batch:
- wave-start operational docs were instantiated for the active run
- missing operational artifacts were added:
  - [WAVE_START_GUARDRAILS.md](/Users/mikhail/Projects/recruitsmart_admin/WAVE_START_GUARDRAILS.md)
  - [PRE_IMPLEMENTATION_CHECKLIST.md](/Users/mikhail/Projects/recruitsmart_admin/PRE_IMPLEMENTATION_CHECKLIST.md)
  - [CURRENT_TASK.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_TASK.md)
  - [SESSION_LOG.md](/Users/mikhail/Projects/recruitsmart_admin/SESSION_LOG.md)
  - [VERIFICATION_SUMMARY.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_SUMMARY.md)
- first code batch landed in shared theme files:
  - `tokens.css` gained `--z-fab`
  - `pages.css` and `mobile.css` moved key shell/mobile layers to the shared z-index contract
  - candidate-detail mobile sticky layers now derive from shared tokens instead of isolated literals
- second shared code batch also landed in the first wave:
  - `components.css` now defines shared form/footer grammar for `.ui-form-shell`
  - explicit future-safe form primitives now exist for later migrations:
    - `.ui-form-section`
    - `.ui-form-section__head`
    - `.ui-form-actions`
    - alignment variants
    - sticky-mobile variant
  - direct-child `.action-row` inside `.ui-form-shell` now gets a shared divider/alignment contract without route TSX edits
  - desktop/mobile manual review has been performed on:
    - `/app/candidates/new`
    - `/app/cities/new`
    - `/app/templates/new`
- third shared code batch also landed in the first wave:
  - `.ui-field` now defines shared helper/status primitives and support/error tokens
  - existing field-level `.subtitle`, `.text-muted`, `.ui-message`, `.ui-field__error`, and nested `.action-row.ui-toolbar--between` consumers are normalized through scoped compatibility selectors
  - mobile-safe field status wrapping now exists for `768px` and `480px` breakpoints
  - desktop/mobile manual review has been performed on:
    - `/app/candidates/new`
    - `/app/cities/new`
    - `/app/templates/new`
- fourth first-wave batch also landed as the first route-light adoption step:
  - explicit shared form grammar is now used directly in:
    - `/app/templates/new`
    - `/app/cities/new`
    - `/app/candidates/new`
  - adopted explicit route markup includes:
    - `.ui-form-actions`
    - `.ui-field__support`
    - `.ui-field__status-row`
  - shell files and business logic were not changed in this batch
  - desktop/mobile manual review has again been performed on the same three routes after markup adoption
- fifth first-wave batch also landed as a single-route follow-up:
  - explicit shared form grammar is now also used directly in:
    - `/app/templates/$templateId/edit`
  - adopted explicit route markup includes:
    - `.ui-field__support`
    - `.ui-field__status-row`
    - `.ui-form-actions`
    - `.ui-inline-checkbox`
  - `template-edit.tsx` now mounts the shared `.ui-form-shell` contract so adopted footer grammar inherits the shared divider/alignment variables
  - shell files, shared CSS files, and business logic were not changed in this batch
  - desktop/mobile manual review was performed on `/app/templates/1/edit` using a temporary seeded template in the review database
- sixth first-wave batch also landed as a paired route-light follow-up:
  - explicit shared form grammar is now also used directly in:
    - `/app/questions/new`
    - `/app/questions/$questionId/edit`
  - adopted explicit route markup includes:
    - `.ui-form-shell`
    - `.ui-field`
    - `.ui-form-actions`
    - `.ui-inline-checkbox`
    - `ui-message--error`
  - `QuestionPayloadEditor` internals were intentionally left untouched; only route-level wrapper, payload label, footer, and error grammar changed
  - shell files, shared CSS files, and business logic were not changed in this batch
  - desktop/mobile manual review was performed on `/app/questions/new` and `/app/questions/1/edit` using a temporary seeded question in the review database
- seventh first-wave batch also landed as a single-route recruiter create follow-up:
  - explicit shared form grammar is now also used directly in:
    - `/app/recruiters/new`
  - adopted explicit route markup includes:
    - `.ui-form-shell`
    - `.ui-field`
    - `.ui-field__support`
    - `.ui-field__note`
    - `.ui-form-actions`
    - `.ui-form-actions--end`
    - `ui-message--error`
  - recruiter-specific banner, hero, summary, and city-selection logic were intentionally left intact; only wrapper/footer/support/error grammar changed
  - shell files, shared CSS files, and business logic were not changed in this batch
  - desktop/mobile manual review was performed on `/app/recruiters/new`, including a temporary create-flow check to confirm the created-credentials banner still renders correctly after adoption
- an additional shared light-theme redesign tranche has now landed:
  - affected files:
    - [tokens.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/tokens.css)
    - [material.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/material.css)
    - [components.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/components.css)
    - [pages.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/pages.css)
    - [mobile.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/mobile.css)
  - the light theme now has a stronger token ladder for:
    - background and surface contrast
    - glass depth and shadow hierarchy
    - borders and separators
    - input/button/badge visibility
    - table row and header readability
    - mobile header/tab-bar/sheet separation
  - desktop/mobile manual review was completed in light theme for:
    - `/app/recruiters/new`
    - `/app/templates/1/edit`
    - `/app/candidates`
    - `/app/profile`
    - mobile More sheet interaction on `/app/candidates`
  - the light-theme tranche remained shared-only:
    - no route TSX edits
    - no shell logic changes
    - no business logic changes
- a follow-up shared-only light-theme hardening batch has now landed in [global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css):
  - normalized legacy light-theme pockets for:
    - dashboard hero
    - KPI/stat cards
    - slot-create tabs
    - toast surfaces
    - profile dropdown
    - recruiter-cabinet / profile legacy light blocks
  - desktop/mobile manual review was repeated in light theme on:
    - `/app/dashboard`
    - `/app/slots/create`
    - `/app/recruiters/new`
    - `/app/templates/1/edit`
    - `/app/candidates`
    - `/app/profile`
    - mobile More sheet on `/app/candidates`
  - this batch also stayed shared-only:
    - no route TSX edits
    - no shell logic changes
    - no business logic changes

## Current Implemented Reality

Relevant codebase facts to keep in mind:
- SPA route scope is `31` mounted routes in [frontend/app/src/app/main.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/main.tsx)
- dormant route files `vacancies.tsx` and `reminder-ops.tsx` exist but are not mounted
- frontend shell remains concentrated in [frontend/app/src/app/routes/__root.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/__root.tsx) at `1286` lines
- theme styling is still monolithic, especially [frontend/app/src/theme/global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css) at `8717` lines
- the densest screen remains [frontend/app/src/app/routes/app/candidate-detail.tsx](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/app/routes/app/candidate-detail.tsx) at `2937` lines
- inline-style debt remains high, especially in `city-edit`, `system`, `test-builder-graph`, `detailization`, and `message-templates`

## What Is Not Yet Implemented

- The full redesign plan has not been completed end-to-end
- Shared component extraction is incomplete
- Foundation token/surface cleanup is not fully done
- Full mobile hardening across all admin screens is not complete
- Admin form grammar cleanup is only partially started through shared CSS primitives; route adoption is underway but still incomplete
- Shared form helper/status grammar now exists and multiple route-light adoption batches are complete, but broader route markup still needs later passes to move more screens from compatibility selectors to explicit primitives
- Theme and shell monoliths are still major risk zones
- A real light-theme toast has now been validated in context on `/app/copilot`
- The mounted SPA shell still does not expose a live opened profile dropdown; only the profile pill is live, so any further dropdown work is a shell/UI decision, not more shared-theme patching
- One final narrow shared-only cleanup pass has now landed in [global.css](/Users/mikhail/Projects/recruitsmart_admin/frontend/app/src/theme/global.css):
  - removed duplicated top-of-file light overrides for:
    - `.app-nav`
    - `.app-nav__item`
    - `.app-profile`
  - removed duplicated mid-file light dropdown overrides so the surviving hardened legacy fallback block is the single compatibility source of truth
  - repeated desktop/mobile light-theme review confirmed no regression on:
    - `/app/dashboard`
    - `/app/candidates`
    - `/app/profile`
    - `/app/recruiters/new`
    - `/app/slots/create`
    - mobile More sheet on `/app/candidates`
  - theme-only cleanup is now effectively complete for the current shared light-theme system

## What Future Agents Should Not Re-Do

- Do not re-run the full redesign discovery from scratch unless route scope changed materially
- Do not create another competing index of canonical design docs
- Do not treat every older root `.md` file as equally current
- Do not assume `codex/bootstrap.md`, `codex/guidelines.md`, `docs/project/CODEX.md`, or `docs/LOCAL_DEV.md` are fully current without checking current code
- Do not touch backlog-only dormant routes unless the task explicitly includes them

## Most Likely Next Work Modes

1. Frontend foundation implementation using the existing execution package
2. Shell and mobile navigation hardening
3. Recruiter-first screen redesign and cleanup
4. Admin form/layout cleanup and inline-style extraction
5. QA / accessibility / motion / responsive hardening
6. Repo-level verification or release-readiness work tied to current product changes
7. Resume first-wave route/shell execution instead of further light-theme cleanup

## Open Risks

- The worktree is often dirty; collision risk is real
- Older docs in `codex/` and `docs/` can contradict the current SPA architecture
- Theme and shell changes have large blast radius
- Frontend and backend changes are happening in parallel in this repository
- Some repo docs are historical, not clearly archival by filename alone

## Latest Route-Light Implementation Update

- `frontend/app/src/app/routes/app/recruiter-edit.tsx` has now joined the explicit shared form grammar rollout.
- Completed adoption in that route:
  - `.ui-form-shell`
  - `.ui-field`
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-inline-checkbox`
  - `.ui-form-actions`
  - `.ui-form-actions--between`
  - `ui-message ui-message--error`
- Intentionally left untouched:
  - summary/load cards
  - reset-password logic
  - delete logic
  - load/delete `ApiErrorBanner` handling
- Verification state after this batch:
  - `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` all green
  - manual desktop/mobile review completed on `/app/recruiters/2/edit`
- Theme-only cleanup is effectively complete, so route-light form adoption is again the active frontend execution track.

## Recommended Agent Behavior Right Now

- Start every task by checking `git status --short`
- Use the root canonical docs first
- Keep changes in small verified batches
- If a task changes repo workflow or canonical scope, update the root context docs
- If a task changes design/system implementation state materially, update the relevant execution docs or explicitly note that they are now stale
