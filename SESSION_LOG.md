# Session Log

## Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-start / `codex/structural-security-tranche`

## Objective

Start the first implementation wave with explicit operational artifacts, confirm the live W1/W2 state, complete at least one verified shared batch, and leave a resumable trail for the next agent.

## Plan

1. Read canonical docs and confirm wave scope
2. Create/update current run artifacts
3. Inspect live W1/W2 implementation files
4. Implement one narrow verified batch
5. Record results, risks, and next step

## Files Inspected

- `README.md`
- `AGENTS.md`
- `PROJECT_CONTEXT_INDEX.md`
- `CURRENT_PROGRAM_STATE.md`
- `REPOSITORY_WORKFLOW_GUIDE.md`
- `VERIFICATION_COMMANDS.md`
- `CODEX_FIRST_WAVE_RECOMMENDATION.md`
- `CODEX_EXECUTION_PLAN.md`
- `COMPONENT_IMPLEMENTATION_SPECS.md`
- `SCREEN_IMPLEMENTATION_SPECS.md`
- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/app/routes/__root.ui-mode.test.tsx`
- `frontend/app/tests/e2e/mobile-smoke.spec.ts`
- `frontend/app/tests/e2e/smoke.spec.ts`

## Files Changed

- `WAVE_START_GUARDRAILS.md`
- `PRE_IMPLEMENTATION_CHECKLIST.md`
- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`

## Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

## Results

- Canonical read order completed
- `WAVE_START_GUARDRAILS.md` was missing and has been created
- `PRE_IMPLEMENTATION_CHECKLIST.md` was missing and has been created
- Current run artifacts have been instantiated before code edits
- Live W1/W2 code inspection completed
- Confirmed in live code:
  - More sheet is absent from the DOM until opened
  - quiet vs ambient route mapping already exists
  - first-wave primitives already exist in partial form
- Chosen first code batch:
  - z-index ladder normalization in shared theme/mobile layers
- Batch B implemented:
  - added `--z-fab` to `tokens.css`
  - replaced shared hardcoded mobile shell z-index values with tokens
  - tokenized desktop app header layer in `pages.css`
  - normalized candidate-detail mobile sticky layers to shared z-index math
- Verification passed:
  - lint: pass with 2 existing warnings
  - typecheck: pass
  - test: pass
  - build:verify: pass
  - test:e2e:smoke: pass

## Blockers

- Dirty worktree includes active changes in the same frontend files that W1/W2 uses
- Current batch stayed narrow because `mobile.css`, `pages.css`, and `__root.tsx` are active conflict zones
- No hard blocker remained after Batch B verification

## Next Step

- decide whether the next session should take Batch C in shell semantics or move to the next W1 foundation gap
- likely next safe target: form/footer grammar or next shared primitive gap before route-level migration

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-continuation / `codex/structural-security-tranche`

### Objective

Continue the first implementation wave from the existing session state and take the next safest shared W1/W2 batch without starting any route migration.

### Worktree State

- `git status --short` confirms the repo is heavily dirty across backend, frontend, docs, and generated artifacts.
- The same shared theme files used by this wave are already modified in the working tree:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/app/routes/__root.tsx`
- This continuation batch must stay additive and narrow to avoid entangling unrelated changes.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed Batch B is already complete and verified.
- Inspected `components.css`, `pages.css`, `candidate-new.tsx`, `city-new.tsx`, and `template-new.tsx`.
- Selected the preferred next shared batch:
  - normalize form/footer grammar in the shared theme layer
- Why this is safer than a shell follow-up:
  - no need to reopen `__root.tsx`
  - affected routes already share `.ui-form-shell`
  - direct-child `.action-row` patterns are limited and easy to target contextually
  - the batch can remain CSS-only

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `frontend/app/src/theme/components.css`
- optional: `frontend/app/src/theme/pages.css` only if the inspection proves it is required

### Localized Success Criteria

- one narrow shared batch only
- no route TSX migrations
- no shell semantics changes
- no backlog-only routes touched
- shared form section/footer grammar becomes explicit in the theme layer
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` stay green
- targeted manual review notes are recorded for affected form flows

### Regression Watchpoints

- global `.action-row` behavior must remain unchanged outside `.ui-form-shell`
- nested toolbars inside `template-new.tsx` must not be treated as footers
- mobile stacked actions must remain usable at small widths
- `global.css` must stay untouched in this batch

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/components.css`

### Implementation Result

- Batch D completed as a CSS-only shared batch.
- Added explicit shared form/footer primitives in `components.css`:
  - `.ui-form-section`
  - `.ui-form-section--compact`
  - `.ui-form-section__head`
  - `.ui-form-actions`
  - `.ui-form-actions--start`
  - `.ui-form-actions--end`
  - `.ui-form-actions--between`
  - `.ui-form-actions--sticky-mobile`
- Normalized `.ui-form-shell` itself:
  - shared spacing variables
  - child `min-width: 0`
  - direct-child `.action-row` now behaves like a form footer with divider + alignment contract
  - `.ui-form-grid > *` now has `min-width: 0`
- Kept the batch additive:
  - no route TSX changes
  - no shell changes
  - no `global.css` changes
  - no backlog routes touched

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Batch D completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Launched a temporary manual-review server on `127.0.0.1:18001` with the same auth/test assumptions as Playwright smoke.
- Reviewed the affected `.ui-form-shell` consumers on desktop and on mobile `375x812`:
  - `/app/candidates/new`
  - `/app/cities/new`
  - `/app/templates/new`
- Confirmed:
  - direct-child form action rows inside `.ui-form-shell` now render with footer divider spacing
  - `candidate-new` and `city-new` footers stack cleanly on mobile and keep 2 visible actions
  - `template-new` final footer keeps `space-between` behavior
  - nested token/tool rows inside the template textarea remain regular inline rows without footer border/padding

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning in test mode
  - `manifest.json` 404 on local test server
- Manual-review server shutdown produced a cancelled long-poll request error while interrupting Uvicorn. This happened during teardown, not during steady-state review.

### Next Step

- next safest batch is still shared and foundation-level:
  - extract a small shared form status/helper grammar around inline errors/help/meta rows in `components.css`
- keep Batch C shell work deferred unless a fresh inspection proves a smaller shell-only delta than the next form batch

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-helper-status / `codex/structural-security-tranche`

### Objective

Continue the first implementation wave with the next safest shared-only batch: field-level helper/status grammar in `components.css`, without route migrations and without reopening shell work.

### Worktree State

- `git status --short` still shows a heavily dirty repo across backend, frontend, docs, and artifacts.
- `frontend/app/src/theme/components.css` remains an active conflict zone, so this batch must stay tightly scoped to additive selectors in that file.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed prior batches are complete and verified:
  - Batch B z-index normalization
  - Batch D form/footer grammar
- Inspected current `.ui-field` consumers and found a narrow shared gap:
  - `components.css` only defines basic `ui-field` + hint/error rules
  - `template-new.tsx` uses `.subtitle` and nested status rows inside `.ui-field`
  - `city-new.tsx` uses `.ui-field__error` plus route-local field status rows
- Why this is safer than shell follow-up or route migration:
  - stays in `components.css`
  - can improve existing field-level messaging via scoped selectors
  - avoids `__root.tsx`, route TSX, and `global.css`

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `frontend/app/src/theme/components.css`

### Localized Success Criteria

- one shared-only batch
- `components.css` is the only code file changed
- no route TSX migrations
- no shell changes
- no backlog-only routes touched
- helper/status grammar around `.ui-field` becomes more explicit and consistent
- Batch D footer grammar remains intact
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` stay green
- targeted manual review is recorded for `/app/candidates/new`, `/app/cities/new`, `/app/templates/new` on desktop and mobile `375x812`

### Regression Watchpoints

- `.ui-form-shell > .action-row` footer behavior from Batch D must not change
- field-level `.subtitle` selectors must stay scoped to `.ui-field`
- nested tool rows inside `.ui-field` must not pick up footer styling
- `global.css` and route-local form markup must stay untouched

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/components.css`

### Implementation Result

- Batch E completed as a shared-only CSS batch inside `components.css`.
- Added explicit field helper/status primitives:
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-field__status-row`
  - `.ui-field__status`
  - `.ui-field__status-item`
  - success / warning / error status modifiers
- Normalized existing field-level consumers without route markup changes:
  - `.ui-field > .subtitle`
  - `.ui-field > .text-muted`
  - `.ui-field > .ui-message`
  - `.ui-field > .text-danger`
  - `.ui-field > .ui-message--error`
  - `.ui-field > .action-row.ui-toolbar--between`
- Added scoped support/error tokens on `.ui-field` itself:
  - `--ui-field-support-gap`
  - `--ui-field-support-color`
  - `--ui-field-error-color`
- Added mobile-safe behavior for status/meta rows:
  - field-level status rows stretch at `max-width: 768px`
  - explicit `.ui-field__status-row` stacks at `max-width: 480px`
- Follow-up tweak after manual review:
  - normalized support typography for children inside field status rows so `template-new` no longer inherits oversized `.subtitle` text on mobile

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Batch E completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Reused a temporary manual-review server on `127.0.0.1:18001` with Playwright-style test auth and fake AI seed.
- Reviewed the affected form flows on desktop and on mobile `375x812`:
  - `/app/templates/new`
  - `/app/cities/new`
  - `/app/candidates/new`
- Confirmed on desktop:
  - `template-new` type helper text resolves to `12px` muted support text
  - `template-new` nested field status row keeps `space-between` layout and `12px` helper text
  - `city-new` validation error keeps `12px` compact error treatment
  - footer divider/alignment from Batch D remains unchanged
- Confirmed on mobile `375x812`:
  - `template-new` helper text remains muted and the nested status row stacks into a clean single-column helper row
  - `city-new` validation error remains compact with no footer collision; timezone status row stays readable
  - `candidate-new` footer still keeps 2 visible actions with divider, wrap, and no helper/status regression

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning in test mode
  - `manifest.json` 404 on local review server
- Manual-review server teardown still produced the known interrupted long-poll / cancelled ASGI request noise after `Ctrl-C`. This occurred during shutdown only.

### Next Step

- next safest batch should stay shared-first but move closer to eventual adoption:
  - inspect whether one narrow route-light batch can switch a small form cluster to explicit `.ui-form-actions` / `.ui-field__status-row` classes without broad rewrites
- keep Batch C shell work deferred unless a fresh inspection proves it is smaller and safer than the first shared-form adoption pass

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-route-light-adoption / `codex/structural-security-tranche`

### Objective

Continue the first implementation wave with the first route-light adoption batch: explicit shared form grammar only for `template-new.tsx`, `city-new.tsx`, and `candidate-new.tsx`.

### Worktree State

- `git status --short` still shows a heavily dirty repository across docs, backend, frontend, generated artifacts, and the same W1/W2 files already touched by this wave.
- The three target route files are already modified in the broader worktree, so this batch must stay minimal and markup-only to avoid entangling unrelated changes.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed Batch E is complete and verified.
- Inspected `components.css` plus the three target routes and found the smallest safe adoption surface:
  - `template-new.tsx` still relies on compatibility selectors for field support, field status row, and footer actions
  - `city-new.tsx` still relies on compatibility selectors for timezone status row, plan-field errors, and footer actions
  - `candidate-new.tsx` is mostly aligned already and only needs explicit footer/action adoption in this batch
- Why this is safer than shell follow-up or a broader route pass:
  - scope is limited to exactly 3 mounted routes
  - no CSS redesign is required
  - no business logic changes are required
  - the shared grammar already exists and only needs explicit markup adoption

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `frontend/app/src/app/routes/app/template-new.tsx`
- `frontend/app/src/app/routes/app/city-new.tsx`
- `frontend/app/src/app/routes/app/candidate-new.tsx`

### Localized Success Criteria

- only the 3 listed routes are touched
- the batch stays form-only
- explicit shared classes are adopted where appropriate:
  - `.ui-form-actions`
  - `.ui-field__support`
  - `.ui-field__status-row`
- no shell changes
- no backlog-only routes touched
- no business logic changes
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` stay green
- targeted manual review is recorded for all three routes on desktop and mobile `375x812`

### Regression Watchpoints

- direct form footer alignment must remain unchanged after swapping to `.ui-form-actions`
- `template-new` token buttons must remain a regular inline control row, not a footer row
- `city-new` timezone pill styling must survive explicit status-row adoption
- `candidate-new` submit/cancel visibility must stay stable on mobile
- no route-local cleanup beyond explicit shared grammar adoption is allowed

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/template-new.tsx`
- `frontend/app/src/app/routes/app/city-new.tsx`
- `frontend/app/src/app/routes/app/candidate-new.tsx`

### Implementation Result

- Batch F completed as the first route-light adoption batch.
- `template-new.tsx`
  - adopted `.ui-field__support` + `.ui-field__note` for the selected template description
  - adopted `.ui-field__status-row` + `.ui-field__status-item` for the char-count row
  - adopted `.ui-form-actions.ui-form-actions--between` for the footer actions
- `city-new.tsx`
  - adopted `.ui-field__status-row` for the timezone status row
  - adopted `.ui-field__support` wrappers for plan validation errors
  - adopted `.ui-form-actions.ui-form-actions--end` for the footer actions
- `candidate-new.tsx`
  - adopted `.ui-field__support` + `.ui-field__note` for the deferred scheduling note
  - adopted `.ui-form-actions.ui-form-actions--end` for the footer actions
- Kept the batch narrow:
  - no shell files touched
  - no backlog routes touched
  - no CSS changes
  - no business logic changes

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Batch F completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Started a temporary review server on `127.0.0.1:18001` using batch-specific sqlite data for this run.
- Reviewed the adopted routes on desktop and mobile `375x812`:
  - `/app/templates/new`
  - `/app/cities/new`
  - `/app/candidates/new`
- Confirmed on desktop:
  - `template-new` support note now renders through `.ui-field__support .ui-field__note` at `12px`
  - `template-new` status row uses `.ui-field__status-row` and footer uses `.ui-form-actions--between`
  - `city-new` timezone status row keeps pill styling while using `.ui-field__status-row`
  - `city-new` field error remains compact and footer uses `.ui-form-actions--end`
  - `candidate-new` deferred scheduling note uses `.ui-field__support .ui-field__note`
  - `candidate-new` footer keeps 2 visible actions with explicit `.ui-form-actions--end`
- Confirmed on mobile `375x812`:
  - `template-new` support note stays muted and the explicit status row stacks cleanly into one column
  - `city-new` explicit timezone status row remains readable; error and footer do not collide
  - `candidate-new` explicit support note remains readable and footer actions stay visible/wrapped correctly

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
  - `manifest.json` 404 on local review server
- This manual-review server ran with active background jobs/Redis and emitted periodic poll / long-poll logs; no new route-level failures were observed.
- Server teardown completed cleanly after a second `Ctrl-C`.

### Next Step

- next safest batch should stay route-light and form-only:
  - inspect `frontend/app/src/app/routes/app/template-edit.tsx` as a single-file follow-up for explicit `.ui-form-actions` / `.ui-field__support` / `.ui-field__status-row` adoption
- keep Batch C shell work deferred unless a fresh inspection proves it is smaller and safer than the next form-only route batch

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-template-edit / `codex/structural-security-tranche`

### Objective

Continue the first implementation wave with the next safest route-light batch: adopt explicit shared form grammar in `template-edit.tsx` only, without shell work, CSS redesign, or broader route migration.

### Worktree State

- `git status --short` still shows a heavily dirty repo across backend, frontend, docs, and artifacts.
- The active route file for this batch has existing inline-style debt and surrounding unrelated changes must remain untouched.
- This continuation batch must stay isolated to a small set of markup-only form grammar changes in one route file plus live run artifacts.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed Batch F is complete and verified.
- Inspected `template-edit.tsx` against the now-shared `components.css` primitives.
- Selected `template-edit.tsx` as the next safest follow-up because:
  - it mirrors `template-new` support/status/footer patterns already adopted successfully
  - it is a mounted route already in the first-wave scope
  - the needed changes are form-only and logic-free
  - the batch can stay inside one route file without reopening shell or shared CSS work

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/template-edit.tsx`

### Localized Success Criteria

- only `template-edit.tsx` is touched in application code
- the batch stays form-only
- explicit shared classes are adopted where appropriate:
  - `.ui-form-actions`
  - `.ui-field__support`
  - `.ui-field__status-row`
- no shell changes
- no backlog-only routes touched
- no business logic changes
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` stay green
- targeted manual review is recorded for `/app/templates/$templateId/edit` on desktop and mobile `375x812`

### Regression Watchpoints

- footer checkbox/save/delete alignment must remain unchanged after swapping to `.ui-form-actions`
- token insert row must remain an inline control row, not a footer row
- char-count row must stay single-line on desktop and stacked on mobile
- loading and page-level error copy must remain untouched in this batch

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/template-edit.tsx`

### Implementation Result

- Batch G completed as a single-route follow-up on `template-edit.tsx`.
- Adopted explicit shared form grammar in route markup:
  - `.ui-field__support` + `.ui-field__note` for the selected template description
  - `.ui-field__status-row` + `.ui-field__status-item` for the char-count row
  - `.ui-form-actions.ui-form-actions--between` for the footer actions
  - `.ui-inline-checkbox` for the footer checkbox row
- Added `ui-form-shell` to the existing route wrapper so the adopted footer grammar inherits the shared divider/alignment contract without changing shell or CSS files.
- Kept the batch narrow:
  - no shell files touched
  - no backlog routes touched
  - no CSS changes
  - no business logic changes
  - token insert row, preview block, loading state, and broader inline-style debt stayed untouched

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Batch G completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests
- Smoke needed one retry outside the sandbox because the Playwright web server could not bind to `127.0.0.1:18000` inside the sandbox; the rerun passed without code changes.

### Manual Review

- Started a temporary review server on `127.0.0.1:18001` using batch-specific sqlite data for this run.
- Created one test template through the existing `/api/templates` endpoint so `/app/templates/1/edit` existed for review.
- Reviewed the adopted route on desktop and mobile `375x812`:
  - `/app/templates/1/edit`
- Confirmed on desktop:
  - selected type description renders through `.ui-field__support .ui-field__note` at `12px`
  - char-count row uses `.ui-field__status-row` and stays horizontal with `space-between`
  - footer uses `.ui-form-actions.ui-form-actions--between` with shared top divider and 2 visible actions
  - checkbox label uses `.ui-inline-checkbox` and keeps aligned spacing
- Confirmed on mobile `375x812`:
  - support note remains muted/readable
  - char-count row stacks into one column with `align-items: stretch`
  - footer keeps `space-between`, wraps safely, and retains the shared divider spacing

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
  - `manifest.json` 404 on local review server
- Manual-review server teardown still emits the existing cancelled long-poll / ASGI shutdown noise after `Ctrl-C`.

### Next Step

- next safest batch should stay route-light and form-only:
  - inspect `frontend/app/src/app/routes/app/question-new.tsx` and `frontend/app/src/app/routes/app/question-edit.tsx` together as the next small paired adoption batch
- keep Batch C shell work deferred unless a fresh inspection proves it is smaller and safer than the next question-form batch

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-questions-pair / `codex/structural-security-tranche`

### Objective

Continue the first implementation wave with the next safest route-light batch: adopt explicit shared form grammar in `question-new.tsx` and `question-edit.tsx` only, without shell work, CSS redesign, or broader route migration.

### Worktree State

- `git status --short` still shows a heavily dirty repo across backend, frontend, docs, and artifacts.
- The active question routes are relatively small, but the worktree around frontend/theme/shell remains noisy, so this batch must stay inside the two listed route files plus live run artifacts.
- The prior Playwright web-server bind caveat is already confirmed and must be documented again if smoke needs an out-of-sandbox rerun.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed Batch G is complete and verified.
- Inspected `components.css`, `template-edit.tsx`, `question-new.tsx`, `question-edit.tsx`, and `QuestionPayloadEditor.tsx`.
- Selected the question create/edit pair as the next safest follow-up because:
  - both routes are short and structurally similar
  - both already use simple stacked form markup with route-local footer/check/payload label patterns
  - the required adoption can stay markup-only and logic-free
  - `QuestionPayloadEditor` already owns its internal validation UI, so the route batch can stay outside component internals

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/question-new.tsx`
- `frontend/app/src/app/routes/app/question-edit.tsx`

### Localized Success Criteria

- only `question-new.tsx` and `question-edit.tsx` are touched in application code
- the batch stays form-only
- explicit shared classes are adopted where appropriate:
  - `.ui-form-shell`
  - `.ui-form-actions`
  - `.ui-inline-checkbox`
  - `.ui-message--error`
- payload label/editor blocks are normalized through shared form grammar where safe
- no shell changes
- no backlog-only routes touched
- no business logic changes
- no CSS redesign unless strictly required and justified
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` stay green
- targeted manual review is recorded for both routes on desktop and mobile `375x812`

### Regression Watchpoints

- `QuestionPayloadEditor` internal builder/preview/status behavior must remain untouched
- footer alignment must remain stable after moving submit buttons under `.ui-form-actions`
- payload label hierarchy must stay readable on mobile
- active checkbox must not collide with footer actions on small widths
- no additional admin/question routes may be touched in this batch

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/question-new.tsx`
- `frontend/app/src/app/routes/app/question-edit.tsx`

### Implementation Result

- Batch H completed as a paired route-light adoption batch for the question create/edit routes.
- `question-new.tsx`
  - adopted `.ui-form-shell` for the route wrapper
  - adopted `.ui-field` for the stacked inputs
  - wrapped the payload editor block in an explicit field container
  - adopted `.ui-form-actions.ui-form-actions--between` for the footer
  - adopted `.ui-inline-checkbox` for the active toggle
  - adopted `ui-message ui-message--error` for route-level form errors
- `question-edit.tsx`
  - adopted `.ui-form-shell` for the route wrapper
  - adopted `.ui-field` for the stacked inputs
  - wrapped the payload editor block in an explicit field container
  - adopted `.ui-form-actions.ui-form-actions--between` for the footer
  - adopted `.ui-inline-checkbox` for the active toggle
  - adopted `ui-message ui-message--error` for route-level detail/form errors
- Kept the batch narrow:
  - no shell files touched
  - no backlog routes touched
  - no CSS changes
  - no business logic changes
  - `QuestionPayloadEditor` internals stayed untouched

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Batch H completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests
- Unlike Batch G, smoke passed inside the sandbox for this batch and did not need an out-of-sandbox rerun.

### Manual Review

- Started a temporary review server on `127.0.0.1:18001` using batch-specific sqlite data for this run.
- Created one test question through the existing `/api/questions` endpoint so `/app/questions/1/edit` existed for review.
- Reviewed the adopted routes on desktop and mobile `375x812`:
  - `/app/questions/new`
  - `/app/questions/1/edit`
- Confirmed on desktop:
  - both routes now mount `.ui-form-shell`
  - payload blocks sit inside explicit `.ui-field` containers with readable `Payload (JSON)` labels
  - `QuestionPayloadEditor` status stays visible at `12px` and keeps its existing success tone
  - footers use `.ui-form-actions.ui-form-actions--between` with shared divider spacing
  - active toggles use `.ui-inline-checkbox` and stay aligned with the primary button
- Confirmed on mobile `375x812`:
  - payload hierarchy remains readable and does not collide with the editor body
  - footer actions wrap safely with `align-items: stretch`
  - active toggle and primary action stay visible and stable
  - edit route keeps the same footer contract as create while preserving the ID subtitle

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
  - `manifest.json` 404 on local review server
- Manual-review server teardown still emits the existing cancelled long-poll / ASGI shutdown noise after `Ctrl-C`.

### Next Step

- next safest batch should stay route-light and form-only:
  - inspect `frontend/app/src/app/routes/app/recruiter-new.tsx` as the next single-route follow-up
- keep Batch C shell work deferred unless a fresh inspection proves it is smaller and safer than the recruiter create-form batch

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-recruiter-create / `codex/structural-security-tranche`

### Objective

Continue the first implementation wave with the next safest single-route batch: adopt explicit shared form grammar in `recruiter-new.tsx` only, without shell work, CSS redesign, or broader route migration.

### Worktree State

- `git status --short` still shows a heavily dirty repo across backend, frontend, docs, and artifacts.
- `recruiter-new.tsx` is a safer batch boundary than shared shell/theme files because it isolates the change to one create flow in application code.
- The prior Playwright bind caveat remains a known execution risk and must be documented again if smoke needs an out-of-sandbox rerun.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed Batch H is complete and verified.
- Inspected `components.css`, `template-edit.tsx`, `question-new.tsx`, and `recruiter-new.tsx`.
- Selected `recruiter-new.tsx` as the next safest route-light follow-up because:
  - it is a single create route with clear recruiter-specific structure that can remain intact
  - the lowest-risk adoption points are already obvious:
    - outer wrapper
    - field-level support and validation blocks
    - bottom footer/actions
    - route-level error message
  - the credentials banner, city selection logic, and summary card can stay untouched
  - the batch can remain markup-only and logic-free

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`

### Localized Success Criteria

- only `recruiter-new.tsx` is touched in application code
- the batch stays form-only
- explicit shared classes are adopted where appropriate:
  - `.ui-form-shell`
  - `.ui-form-actions`
  - `.ui-form-actions--end`
  - `.ui-field__support`
  - `.ui-field__note`
  - `ui-message ui-message--error`
- recruiter-specific banner/summary flow remains intact
- no shell changes
- no backlog-only routes touched
- no business logic changes
- no credential/banner logic changes
- no CSS redesign unless strictly required and justified
- `lint`, `typecheck`, `test`, `build:verify`, and `test:e2e:smoke` stay green
- targeted manual review is recorded for `/app/recruiters/new` on desktop and mobile `375x812`

### Regression Watchpoints

- created-credentials banner must retain its current behavior and CTA flow
- recruiter hero and aside summary must not shift unexpectedly
- city search / selection logic must remain untouched
- footer alignment must remain stable after adopting explicit shared action classes
- support/error rows must not collide with route-local section copy on mobile

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/recruiter-new.tsx`

### Implementation Result

- Batch I completed as a single-route form-only adoption batch for `recruiter-new.tsx`.
- Adopted explicit shared wrapper/footer/support grammar while keeping recruiter-specific flow intact:
  - route wrapper now mounts `.ui-form-shell`
  - active create-form labels now also mount `.ui-field`
  - field-level helper and validation copy now renders through `.ui-field__support` and `.ui-field__note`
  - route-level and field-level validation now render through `ui-message ui-message--error`
  - bottom footer now uses `.ui-form-actions.ui-form-actions--end`
- Kept the batch narrow:
  - no shell files touched
  - no shared CSS files touched
  - no backlog routes touched
  - no business logic changes
  - `createdCredentials` banner logic and CTA flow stayed intact

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Batch I completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests inside the sandbox

### Manual Review

- Started a temporary review server on `127.0.0.1:18001` using batch-specific sqlite data for this run.
- Reviewed `/app/recruiters/new` on:
  - desktop `1440x960`
  - mobile `375x812`
- Confirmed on desktop:
  - the route wrapper now inherits the shared `.ui-form-shell` contract without shifting the recruiter-specific hero/summary layout
  - name/region/contact fields render helper and validation copy through explicit shared support/error grammar
  - bottom footer uses `.ui-form-actions.ui-form-actions--end` and keeps the create/reset/cancel alignment readable
  - empty-name validation renders inline without colliding with the region helper copy
  - after creating a test recruiter, the `createdCredentials` banner still appears with the same copy/copy-button/list CTA behavior
- Confirmed on mobile `375x812`:
  - field helper/error copy remains readable and stacked correctly
  - recruiter hero, summary card, and footer remain visible and stable
  - footer actions stay readable above the mobile navigation and do not collide with support text
  - the credentials banner remains readable after create and does not break the rest of the form layout

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
  - `manifest.json` 404 on local review server
- Manual-review server teardown again emitted the existing cancelled long-poll / ASGI shutdown noise after `Ctrl-C`.

### Next Step

- next safest batch should stay route-light and form-only:
  - inspect `frontend/app/src/app/routes/app/recruiter-edit.tsx` as the next single-route follow-up
- keep Batch C shell work deferred unless a fresh inspection proves it is smaller and safer than the recruiter edit-form batch

## Recruiter Edit Route-Light Outcome

### Files Changed

- `frontend/app/src/app/routes/app/recruiter-edit.tsx`
- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`

### Implementation Result

- Completed the `recruiter-edit.tsx` route-light adoption batch.
- Shared grammar adopted in place without CSS changes:
  - `.ui-form-shell`
  - `.ui-field`
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-inline-checkbox`
  - `.ui-form-actions`
  - `.ui-form-actions--between`
  - `ui-message ui-message--error`
- Reset-password controls were normalized to shared action grammar, but the mutation logic and credentials flow were left unchanged.
- Bottom footer was normalized to a shared between-layout with the destructive action kept separate from save/reset/cancel controls.
- Load/delete `ApiErrorBanner` usage was preserved.

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Started a temporary review server on `127.0.0.1:18007` with:
  - sqlite DB `sqlite+aiosqlite:////tmp/recruitsmart_manual_ui_review_recruiter_edit.db`
  - login `playwright_admin` / `playwright_admin_password`
- Created `UI Review Recruiter` through the existing `/api/recruiters` endpoint to guarantee an edit route for the review.
- Reviewed `/app/recruiters/2/edit` on:
  - desktop
  - mobile `375x812`
- Confirmed on desktop:
  - outer panel now inherits the shared `.ui-form-shell` contract
  - name validation renders inline via `ui-message ui-message--error`
  - region / Telegram helper copy renders via explicit shared support grammar
  - reset-password flow still works: accepting the confirm repopulated the password field and enabled the copy button
  - delete CTA still opens the destructive confirmation prompt; after dismiss, recruiter `#2` still existed via `GET /api/recruiters/2`
  - summary/load cards remained visually unchanged
- Confirmed on mobile `375x812`:
  - form and aside sections stack cleanly
  - helper/error copy remains readable
  - footer actions remain visible above the mobile nav
  - no collision appeared between validation copy, service block, and footer controls

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- Review harness still emitted baseline warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite auto-upgrade warning during test startup
  - `manifest.json` 404 on the local review server
- Playwright MCP reported a stale handled confirm-dialog state after reset/delete checks, but the route remained interactive and the backend confirmed no delete occurred after dismiss.

### Next Step

- Next safest batch should stay route-light and form-only:
  - inspect `frontend/app/src/app/routes/app/city-edit.tsx`
- Keep shell work deferred.

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: light-theme-nav-profile-hardening / `codex/structural-security-tranche`

### Objective

Continue the existing light-theme session with one more shared-only hardening batch in `frontend/app/src/theme/global.css`, focused on the remaining legacy nav/profile light selectors near the top of the file.

### Worktree State

- `git status --short` still shows a heavily dirty repository across docs, backend, frontend, and test artifacts.
- Existing light-theme batches remain present in:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/global.css`
- This continuation must stay in `frontend/app/src/theme/global.css` only.

### Audit Findings

- Remaining weak legacy selectors at the top of `global.css`:
  - `:root[data-theme='light'] .app-nav`
  - `:root[data-theme='light'] .app-nav__item:not(.is-active)`
  - `:root[data-theme='light'] .app-nav__item.is-active`
  - `:root[data-theme='light'] .app-profile`
  - base `.app-profile-pill`
  - base `.profile-dropdown-menu` / `.profile-dropdown-item` block
- What is broken or visually weak:
  - light nav/profile surfaces still use pale white-alpha recipes and weak boundary contrast
  - inactive nav state still depends on `opacity: 0.5`
  - active nav state still assumes white text instead of a readable light active surface
  - base dropdown is still dark-biased before the later light hardening block
- Mounted shell reality:
  - desktop navigation currently uses `vision-nav-pill` / `vision-nav__item`
  - the visible desktop profile entry uses `app-profile-pill`
  - no live React-rendered `profile-dropdown-menu` component is currently mounted in `__root.tsx`

### Batch Selection Rationale

- `global.css` remains the correct next step because these early legacy selectors still conflict with the redesigned light token/surface hierarchy.
- This is safer than route or shell work because:
  - it stays shared-only
  - it removes weak legacy light formulas
  - it does not require TSX changes
- Validation caveat to carry through this run:
  - a real toast can be triggered and inspected in context
  - an opened profile dropdown may be impossible to validate as a live runtime state if the mounted shell continues to expose only the profile pill link

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/global.css`

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/global.css`

### Implementation Result

- Shared-only hardening batch completed in `frontend/app/src/theme/global.css`.
- Normalized the remaining legacy light-theme nav/profile pockets:
  - `.app-nav`
  - `.app-nav__item`
  - `.app-nav__icon`
  - `.app-profile`
  - `.app-profile-pill`
  - `.app-profile__icon`
  - `.profile-dropdown-menu`
  - `.profile-dropdown-header`
  - `.profile-dropdown-item`
- Kept the batch narrow:
  - no route TSX changes
  - no shell/root refactor
  - no business logic changes
  - no dark-theme redesign

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Review harness:
  - isolated local server on `127.0.0.1:18005`
  - light mode forced with `theme=light` and `ui:liquidGlassV2=1`
- Login behavior on this harness:
  - `playwright_admin` / `playwright_admin_password` worked on the SPA login form
  - `admin` / `admin` failed on the same harness
- Desktop reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - `/app/copilot`
- Mobile `375x812` reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - More sheet on `/app/candidates`
- Interactive validation:
  - real toast validated on `/app/copilot` by enabling a seeded knowledge-base document; observed toast text: `Документ включён`
  - mounted SPA shell still exposes only `.app-profile-pill` as a live profile entry
  - `document.querySelector('.profile-dropdown-menu')` returned `false` in the live shell
  - opened dropdown styling was validated via a temporary in-context DOM harness positioned under the live profile pill so the remaining legacy dropdown CSS could be reviewed without out-of-scope shell changes
- Review findings:
  - dashboard chrome, KPI cards, and header/profile pill now look materially more grounded in light mode
  - candidates list/table and recruiter create form stayed readable with no new washout regressions
  - profile cards and admin quick links still read clearly after the nav/profile hardening pass
  - mobile More sheet remains legible and separated from the dimmed background

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- Existing test/local warnings remain unchanged:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
  - `manifest.json` 404 on isolated review server
- Manual-review server will emit existing ASGI shutdown / cancelled-task noise on teardown.

### Next Step

- next safest batch should stay shared-only and light-theme-specific:
  - one last `global.css` cleanup pass for residual top-of-file nav/profile legacy selectors that are now effectively dead or duplicated

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: light-theme-global-final-cleanup / `codex/structural-security-tranche`

### Objective

Take one final narrow shared-only cleanup pass in `frontend/app/src/theme/global.css` to reduce residual legacy light-theme debt without reopening redesign scope.

### Worktree State

- `git status --short` still shows a heavily dirty repo across backend, frontend, docs, and artifacts.
- `frontend/app/src/theme/global.css` remains an active merge-risk zone, so this continuation must stay surgical and shared-only.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, and `VERIFICATION_SUMMARY.md` before editing.
- Confirmed prior light-theme batches already hardened the live token/surface system plus the major legacy light pockets in `global.css`.
- Fresh audit of `global.css` found the remaining safe cleanup targets:
  - duplicated early light overrides for `.app-nav`, `.app-nav__item`, and `.app-profile`
  - duplicated later light overrides for `.profile-dropdown-menu` rows
- Runtime reality checked again:
  - live shell uses `vision-nav-pill` / `vision-nav__item`
  - live shell exposes `.app-profile-pill`
  - `.app-nav`, `.app-profile`, and `.profile-dropdown-menu` are currently dormant fallback selectors
- This makes `global.css` the correct final theme-only step:
  - cleanup can reduce legacy debt without touching route TSX, shell code, or business logic
  - active light-theme visuals should stay stable because the surviving hardened block near the end of `global.css` remains the single compatibility source of truth

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/global.css`

### Localized Success Criteria

- only `frontend/app/src/theme/global.css` changes in app code
- residual legacy light-theme debt is reduced through safe removal/merge of duplicated or dead selectors
- no route TSX changes
- no shell/root changes
- no business logic changes
- full frontend verification gate stays green
- desktop/mobile light-theme manual review is recorded again
- final handoff states clearly whether theme-only cleanup is effectively complete

### Regression Watchpoints

- `global.css` still overrides all imported theme layers, so selector deletion must be backed by runtime usage checks
- the visible profile pill must remain readable in light theme after cleanup
- mobile header/tab-bar/More sheet separation must remain stable
- runtime dropdown absence in the mounted shell must remain documented, not papered over

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/global.css`

### Implementation Result

- Final narrow `global.css` cleanup batch completed.
- Removed duplicated early light overrides that no longer govern the active shell:
  - `.app-nav`
  - `.app-nav__item`
  - `.app-profile`
- Removed the duplicated mid-file light dropdown block so the surviving hardened nav/profile fallback block remains the single source of truth for dormant legacy surfaces:
  - `.profile-dropdown-menu`
  - `.profile-dropdown-header`
  - `.profile-dropdown-item`
  - `.profile-dropdown-item--danger`
- Simplified redundant border-color declarations in the surviving legacy fallback block.
- Kept the batch shared-only:
  - no route TSX changes
  - no shell/root changes
  - no business logic changes

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Review harness:
  - isolated local server on `127.0.0.1:18006`
  - effective login on this harness: `playwright_admin` / `playwright_admin_password`
  - light theme forced with:
    - `localStorage.setItem('theme', 'light')`
    - `localStorage.setItem('ui:liquidGlassV2', '1')`
- Desktop reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
- Mobile `375x812` reviewed:
  - `/app/dashboard`
  - `/app/candidates`
  - `/app/profile`
  - `/app/recruiters/new`
  - `/app/slots/create`
  - More sheet on `/app/candidates`
- Review findings:
  - dashboard active nav and profile pill remained clearly legible after cleanup
  - candidates list/table header remained readable and stable in light mode
  - profile action cards stayed well-bounded
  - recruiter create and slots create surfaces retained strong form/tab hierarchy
  - mobile header, tab bar, active tab, and More sheet remained visually stable and readable
  - no visual regression appeared from removing the duplicated selectors

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- Existing local/test warnings remain unchanged:
  - Pydantic `model_` namespace warning
  - SQLite auto-upgrade warning in test mode
  - `manifest.json` 404 on isolated review server
- Runtime opened profile dropdown is still absent from the mounted shell. This cleanup pass did not and could not change that product/runtime limitation.

### Next Step

- Theme-only cleanup is effectively complete for the current shared light-theme system.
- Next exact batch should move back to implementation work outside theme cleanup:
  - `frontend/app/src/app/routes/app/recruiter-edit.tsx`
  - scope: single-route, form-only adoption of the already-established shared wrapper/support/footer grammar
  - keep summary/load cards, reset-password banner, delete flow, and shell untouched

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: recruiter-edit-route-light / `codex/structural-security-tranche`

### Objective

Continue the first-wave implementation session with the next safest single-route batch: adopt the already-proven shared form grammar in `frontend/app/src/app/routes/app/recruiter-edit.tsx`.

### Worktree State

- `git status --short` still shows a heavily dirty repository across backend, frontend, docs, and generated artifacts.
- This continuation must keep app-code changes limited to `frontend/app/src/app/routes/app/recruiter-edit.tsx`.

### Batch Selection Rationale

- Re-read the live run artifacts and confirmed the preceding route-light sequence is already landed:
  - `template-edit`
  - `question-new`
  - `question-edit`
  - `recruiter-new`
- Fresh audit of `recruiter-edit.tsx` shows it is the next safe follow-up because:
  - it shares the same recruiter form domain as `recruiter-new`
  - the route already has stable sections that can adopt explicit classes without logic changes
  - the primary gaps are wrapper/field/footer/message grammar, not data flow
- Must remain untouched in this batch:
  - summary/load cards
  - reset-password mutation logic and credentials copy flow
  - delete mutation flow
  - load/error query behavior

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/app/routes/app/recruiter-edit.tsx`

### Localized Success Criteria

- only `frontend/app/src/app/routes/app/recruiter-edit.tsx` changes in app code
- batch remains form-only
- explicit shared wrapper/support/footer grammar is adopted where appropriate
- no shell work
- no business logic changes
- no reset-password/delete logic changes
- full frontend verification gate stays green
- desktop/mobile manual review is recorded for the recruiter edit route

### Regression Watchpoints

- route mixes form content with edit-only service and destructive zones
- reset-password banner must keep working and stay readable
- delete CTA must remain intact
- footer/action adoption must not collide with aside summary cards or mobile bottom chrome
- preferred scope:
  - prune or align any remaining `.app-nav` / `.app-profile` light overrides that no mounted route currently uses
  - keep route TSX and shell logic untouched
  - if product scope prefers runtime dropdown support, that must be a separate shell/UI task rather than more theme-only patching

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: light-theme-global-hardening / `codex/structural-security-tranche`

### Objective

Continue the active light-theme implementation with one shared-only hardening pass in `frontend/app/src/theme/global.css`, targeting only the remaining legacy light-theme selectors that still weaken the new token and surface hierarchy.

### Worktree State

- `git status --short` still shows a heavily dirty repository across backend, frontend, docs, and artifacts.
- The light-theme shared tranche from the previous run is already present in:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/mobile.css`
- This follow-up batch must stay in `frontend/app/src/theme/global.css` only to avoid mixing shared-system hardening with route or shell work.

### Audit Findings

- `global.css` still overrides the newer light-theme system with several legacy blocks:
  - `.toast` is always rendered on a dark, nearly black surface
  - `.stat-card` has a second old definition that flattens KPI cards in light mode
  - `.dashboard-hero--incoming` still uses a dark-biased atmospheric gradient
  - `.slot-create-tabs` and `.slot-create-tab.is-active` still use weak white-alpha pills tuned for dark surfaces
  - profile and recruiter-cabinet light overrides remain pale and weakly bounded compared to the newer surface ladder
- Safe normalization targets for this batch:
  - dashboard hero
  - stat cards
  - toasts
  - slot-create tabs
  - profile dropdown
  - profile / cabinet legacy light pockets
- What must remain untouched:
  - route TSX
  - `__root.tsx`
  - dark-theme formulas
  - business logic

### Batch Selection Rationale

- `global.css` is now the correct next step because the previous light-theme tranche fixed the shared token and component layers, but the legacy file still overrides those improvements on specific old surfaces.
- This batch is safer than route work because:
  - it stays shared-only
  - it removes conflicting legacy light formulas instead of introducing new route-local patches
  - it does not depend on markup changes

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/global.css`

### Localized Success Criteria

- only `frontend/app/src/theme/global.css` changes in app code
- no route TSX edits
- no shell work
- no business logic changes
- dashboard/stat/profile/toast/tab surfaces align visibly better with the new light token and surface system
- lint, typecheck, test, build:verify, and `test:e2e:smoke` stay green
- desktop/mobile light-theme manual review is recorded again

### Regression Watchpoints

- avoid touching generic dark-theme behavior
- avoid broad header/nav cleanup outside the targeted legacy light pockets
- keep profile-specific hardening scoped so it does not destabilize existing recruiter cabinet layout
- avoid turning light theme into flat white panels by overcorrecting away from the current premium glass direction

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/global.css`

### Implementation Result

- Shared-only `global.css` light-theme hardening batch completed.
- Hardened legacy light pockets in `global.css`:
  - `dashboard-hero`
  - `dashboard-hero--incoming`
  - `stat-card`
  - `slot-create-tabs`
  - `slot-create-tab`
  - `toast`
  - `profile-dropdown-menu`
  - `profile-hero`
  - `profile-page .action-link`
  - `profile-avatar__upload`
  - `profile-avatar__delete`
  - `profile-cabinet .cabinet-glass`
  - `cabinet-kpi-card`
  - `cabinet-form` light inputs
  - `cabinet-table`
- Scope discipline held:
  - no route TSX edits
  - no shell work
  - no business logic changes
  - no dark-theme redesign

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Review harness:
  - isolated local server on `127.0.0.1:18004`
  - light mode forced through:
    - `localStorage.setItem('theme', 'light')`
    - `localStorage.setItem('ui:liquidGlassV2', '1')`
- Login note:
  - the isolated harness accepted `admin/admin`
  - `playwright_admin/playwright_admin_password` was rejected on this harness
- Desktop reviewed:
  - `/app/dashboard`
  - `/app/slots/create`
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
- Mobile `375x812` reviewed:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
  - `/app/slots/create`
  - More sheet interaction on `/app/candidates`
- Review findings:
  - dashboard hero and KPI cards now read as layered light surfaces with stronger boundaries and clearer value hierarchy
  - slot-create tabs now show a clearly legible active state instead of faint white-on-white pills
  - recruiter create and template edit forms remained stable; the global hardening did not wash out footer/actions or helper copy
  - profile and recruiter-cabinet cards now feel more structured and readable in light mode, especially KPI cards and panel surfaces
  - mobile More sheet, tab bar, and mobile header remained readable and structurally separated after the `global.css` pass
- Review caveats:
  - toast styling was hardened in CSS, but a safe real-user trigger was not forced during this pass
  - `manifest.json` 404 remains a local review baseline warning, not a regression

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- Existing local/test warnings remain unchanged:
  - Pydantic `model_` protected namespace warning
  - `manifest.json` 404 on local review harness
  - existing mobile-web-app-capable warning in browser console
- Review-harness auth mismatch:
  - the isolated harness did not accept the expected `playwright_admin` pair even though the smoke setup uses it elsewhere
  - manual review proceeded with `admin/admin`

### Next Step

- next exact batch should stay shared-only and light-theme-specific:
  - finish legacy light-theme cleanup at the top of `frontend/app/src/theme/global.css`
- preferred scope:
  - old `.app-nav`, `.app-nav__item`, `.app-profile`, and `.app-profile-pill` light overrides that predate the new page-shell theme layer
  - verify the profile dropdown in an opened state and, if possible, trigger one real toast to validate the new toast surface in-context
- keep route TSX and shell logic untouched unless a fresh audit proves a shared file is no longer sufficient

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: light-theme-redesign / `codex/structural-security-tranche`

### Objective

Audit, redesign, and harden the light theme as a shared product UI layer without reopening shell architecture, route-level migrations, or business logic.

### Worktree State

- `git status --short` still shows a heavily dirty repo across docs, backend, frontend, and artifacts.
- Active light-theme files are already part of the dirty worktree and therefore remain high-risk shared zones:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/mobile.css`
- This run must stay shared-only and avoid opportunistic cleanup in route files or shell logic.

### Audit Findings

- Light theme is currently weaker than dark theme because the shared glass system is still dark-biased.
- `tokens.css` leaves several light-theme depth variables underdefined:
  - `--glass-subtle`
  - `--glass-glow-subtle`
  - `--glass-glow`
  - `--glass-inset`
  - `--glass-inset-strong`
- `html[data-ui='liquid-glass-v2'][data-theme='light']` uses almost-white surface steps and soft borders, which reduces separation between:
  - page shells
  - cards
  - tables
  - overlays
  - mobile nav/header surfaces
- Shared component selectors in `global.css` and `components.css` still assume dark-backdrop contrast:
  - `.ui-btn`
  - `.ui-btn--ghost`
  - `.chip`
  - `.status-badge`
  - `.data-card`
  - `.data-table`
  - `.modal-overlay`
  - `.ui-alert`
- Light mobile surfaces currently rely on translucent `bg-elevated` mixes and need stronger structural contrast for header/tab-bar readability.

### Preserved Strengths

- dark theme direction stays untouched
- shared form grammar from prior batches stays intact
- route structure, shell semantics, and business logic stay out of scope
- liquid-glass v2 still provides the right base for premium layered surfaces if light-theme tokens are hardened

### Batch Selection Rationale

- Chosen next safe batch:
  - shared-only light-theme redesign across tokens and shared theme layers
- Why this is safe enough despite broad surface area:
  - no route TSX edits
  - no shell logic changes
  - no business logic changes
  - high-specificity light-theme overrides can improve weak shared primitives without destabilizing dark theme
- Planned implementation slices:
  - LT-B/LT-C: tokens + shared surfaces + hierarchy
  - LT-D/LT-E/LT-F: controls, states, tables, overlays, mobile light surfaces

### Planned Files

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`

### Localized Success Criteria

- light theme becomes materially higher contrast and more structured
- shared page/card/table/control surfaces are clearer in light theme
- desktop and mobile light theme remain operational for CRM workflows
- dark theme behavior is preserved
- no shell/root architecture changes
- no route-level migrations
- full verification remains green

### Regression Watchpoints

- button visibility in light theme
- table row separation and sticky headers in light theme
- mobile header / tab bar / sheet readability
- form helper and footer grammar from prior batches must remain intact
- any selector added here must stay light-theme-specific and not disturb dark theme

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`
- `CURRENT_PROGRAM_STATE.md`
- `frontend/app/src/theme/tokens.css`
- `frontend/app/src/theme/material.css`
- `frontend/app/src/theme/components.css`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`

### Implementation Result

- Landed one shared-only light-theme redesign tranche across token, surface, component, page-shell, and mobile layers.
- Material changes completed:
  - rebuilt the light token ladder in `tokens.css`
  - hardened light liquid-glass surfaces in `material.css`
  - strengthened controls, badges, alerts, tables, overlays, and helper typography in `components.css`
  - improved light shell atmosphere, nav pills, page hero/section separation, and quiet/ambient backgrounds in `pages.css`
  - strengthened mobile light header/tab-bar/sheet/card/FAB surfaces in `mobile.css`
- Scope discipline held:
  - no route TSX edits
  - no shell logic edits
  - no dark-theme redesign
  - no business logic changes

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Light-theme shared batch completed
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests

### Manual Review

- Review servers used:
  - primary isolated light-theme review server on `127.0.0.1:18001`
  - clean fallback isolated light-theme review server on `127.0.0.1:18003`
- Light theme forced through:
  - `localStorage.setItem('theme', 'light')`
  - `localStorage.setItem('ui:liquidGlassV2', '1')`
- Desktop reviewed:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
- Mobile `375x812` reviewed:
  - `/app/recruiters/new`
  - `/app/templates/1/edit`
  - `/app/candidates`
  - `/app/profile`
  - mobile More sheet on `/app/candidates`
- Review findings:
  - light create/edit forms now have visibly stronger section boundaries, calmer white surfaces, and more readable helper/status copy
  - primary and ghost actions read clearly against the new light surface ladder
  - candidates list/table hierarchy is clearer through stronger header, row, and border separation; the mobile list cards remain readable
  - profile/settings-like cards and quick links remain readable in light mode on both desktop and mobile
  - mobile header, tab bar, and More sheet no longer blend into page content the way the old light theme did

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- Existing test-mode warnings remain unchanged:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
- Manual review still sees `manifest.json` 404 on isolated local review servers.
- The first isolated review harness on `18001` hit a pre-existing sqlite schema gap while a detailization-related request was triggered:
  - missing table `detailization_entries`
  - this produced backend-side `503` noise unrelated to the light-theme CSS batch
  - the review was continued on a fresh isolated harness at `18003`

### Next Step

- next exact batch should stay shared-only and light-theme-specific:
  - targeted cleanup of legacy light-theme stragglers in `frontend/app/src/theme/global.css`
- preferred scope:
  - `dashboard-hero`
  - `stat-card`
  - `slot-create-tab`
  - `toast`
  - profile-specific legacy light blocks
- keep route TSX migrations and shell work out of the next light-theme batch unless a new audit proves they are strictly necessary

## Continuation

### Session

- Date: 2026-03-07
- Agent: Codex
- Task / branch: first-wave-recruiter-create-revalidate / `codex/structural-security-tranche`

### Objective

Re-run the requested `recruiter-new.tsx` batch in a disciplined way, confirm whether new route work is actually needed, and leave fresh verification/manual-review evidence without reopening scope.

### Worktree State

- `git status --short` still shows the same heavily dirty repo across backend, frontend, docs, and artifacts.
- Fresh inspection confirmed the requested route batch is already present in live code and in the active run artifacts.
- Because the adoption already exists, this continuation must not manufacture a duplicate route change.

### Batch Selection Rationale

- Re-read `CURRENT_TASK.md`, `SESSION_LOG.md`, `VERIFICATION_SUMMARY.md`, and `recruiter-new.tsx`.
- Confirmed `recruiter-new.tsx` already mounts the exact Batch I shared grammar:
  - `.ui-form-shell`
  - `.ui-field`
  - `.ui-field__support`
  - `.ui-field__note`
  - `.ui-form-actions.ui-form-actions--end`
  - `ui-message ui-message--error`
- Chosen safe action for this run:
  - do not touch application code
  - re-run the full verification gate
  - perform fresh desktop/mobile manual review
  - update live artifacts with revalidation evidence only

### Files Changed

- `CURRENT_TASK.md`
- `SESSION_LOG.md`
- `VERIFICATION_SUMMARY.md`

### Implementation Result

- No new application code changes were required in this run.
- Requested Batch I for `recruiter-new.tsx` was already implemented in live code before this continuation started.
- This run served as a fresh revalidation pass for the already-landed route-light adoption.

### Checks Run

```bash
npm --prefix frontend/app run lint
npm --prefix frontend/app run typecheck
npm --prefix frontend/app run test
npm --prefix frontend/app run build:verify
npm --prefix frontend/app run test:e2e:smoke
```

### Results

- Revalidation completed for the already-landed `recruiter-new.tsx` batch
- `lint`: pass with 2 existing warnings
- `typecheck`: pass
- `test`: pass, 10 files / 30 tests
- `build:verify`: pass, bundle budgets OK
- `test:e2e:smoke`: pass, 11 Playwright smoke tests inside the sandbox

### Manual Review

- Started a temporary review server on `127.0.0.1:18001` with a batch-specific sqlite DB for this revalidation run.
- Reviewed `/app/recruiters/new` on:
  - desktop `1440x960`
  - mobile `375x812`
- Confirmed in the fresh review:
  - the route still mounts `.ui-form-shell`
  - helper/support/error grammar is still explicit and readable
  - footer actions stay stable on desktop and mobile
  - empty-name validation still renders inline without collisions
  - create-flow credentials banner still appears correctly after a successful test create and remains readable on mobile

### Warnings / Non-Blocking Noise

- Existing lint warnings remain unchanged:
  - `frontend/app/src/app/routes/__root.ui-mode.test.tsx:12`
  - `frontend/app/src/app/routes/app/profile.tsx:14`
- E2E/manual review environments still emit existing non-blocking warnings:
  - Pydantic `model_` protected namespace warning
  - SQLite automatic schema upgrade warning during test startup
  - `manifest.json` 404 on local review server
- Manual-review server teardown again emitted the existing cancelled long-poll / ASGI shutdown noise after `Ctrl-C`.

### Next Step

- next safest batch should stay route-light and form-only:
  - inspect `frontend/app/src/app/routes/app/recruiter-edit.tsx` as the next single-route follow-up
- keep Batch C shell work deferred unless a fresh inspection proves it is smaller and safer than the recruiter edit-form batch
