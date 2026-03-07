# CODEX_FIRST_WAVE_RECOMMENDATION

## Start Here
- Start with foundation, not with page cosmetics.
- The first three Codex sessions should be strictly ordered because each later session depends on the previous one being stable.

## Why Foundation First
- Six or more header/hero patterns already exist across routes, so page work without a shared hero primitive will duplicate effort.
- The More sheet issue in `__root.tsx` is a P0 mobile blocker and affects every route.
- Quiet vs ambient mode currently affects the entire shell, so even correct page work can look wrong if shell atmosphere is not fixed first.
- Table/card parity and admin form grammar are system concerns, not route-local concerns.
- `global.css` is too large to be a safe starting point for refactor-first work; start with token and primitive layers instead.

## Recommended Codex Sessions
### Session 1. Token And Surface Foundation
- Scope:
  - W1.1
  - W1.2
  - W1.3
- Files:
  - `frontend/app/src/theme/tokens.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/components.css`
- Outcome:
  - canonical token ladder
  - surface hierarchy
  - page shell primitives
- Checkpoint:
  - screenshot dashboard, incoming, profile
  - run lint/test/build

### Session 2. Shell Semantics Fix
- Scope:
  - W2.1
  - W2.2
  - W2.3
  - W2.4
- Files:
  - `frontend/app/src/app/routes/__root.tsx`
  - `frontend/app/src/theme/mobile.css`
  - `frontend/app/src/theme/pages.css`
- Outcome:
  - closed More sheet no longer blocks mobile quality
  - quiet routes lose ambient noise
  - shell z-index and focus behavior stabilize
- Checkpoint:
  - screenshot login, dashboard, incoming, mobile shell
  - run mobile smoke after lint/test/build

### Session 3. Shared Component Primitives
- Scope:
  - W3.1
  - W3.2
  - W3.3
  - W3.4
  - W3.5
  - W3.6
- Files:
  - `frontend/app/src/theme/components.css`
  - `frontend/app/src/theme/pages.css`
  - `frontend/app/src/theme/material.css`
  - `frontend/app/src/theme/mobile.css`
  - selective legacy cleanup in `frontend/app/src/theme/global.css`
- Outcome:
  - hero, section, toolbar, filter, state, table/card parity, overlay primitives
- Checkpoint:
  - screenshot dashboard, incoming, slots, candidates shell states
  - run lint/test/build

## First Screen After Foundation
- Pick `/app/incoming` first.
- Why:
  - high traffic
  - moderate complexity
  - strong existing structure
  - exercises hero, toolbar, filters, cards and modal overlay in one route
- What it proves:
  - shared hero works
  - shared filter bar works
  - shared card/list rhythm works
  - overlay migration works
  - quiet shell mode works on a real ops screen

## Top 10 P0/P1 Items By Priority
| Rank | Item | Impact | Effort |
|---|---|---|---|
| 1 | More sheet closed-state semantics | very high | low |
| 2 | Quiet vs ambient route mapping | high | low |
| 3 | Shared page shell primitives | very high | medium |
| 4 | Shared surface ladder | high | medium |
| 5 | Shared toolbar/filter system | very high | medium |
| 6 | Incoming screen migration | very high | medium |
| 7 | Table/card parity contract | high | medium |
| 8 | Slots and candidates migration | very high | medium-high |
| 9 | Candidate detail top-level restructure | very high | high |
| 10 | City-edit and system inline extraction | high | high |

## Anti-Patterns To Avoid
- Do not start with `candidate-detail.tsx`.
- Do not start by splitting `global.css` wholesale.
- Do not add new inline styles to speed up migration.
- Do not redesign admin forms before the admin form grammar exists.
- Do not refactor shell and a first-wave screen in the same commit.
- Do not invest in mobile kanban polish before card parity and filter sheets are stable.

## Session Checkpoint Protocol
### After Session 1
- Capture dashboard hero, incoming hero and profile panel screenshots.
- Confirm page shell primitives are being used by at least one low-risk route or local preview.
- Run lint/test/build.

### After Session 2
- Capture mobile screenshots for:
  - closed shell
  - open More sheet
  - dashboard ambient
  - incoming quiet
- Run lint/test/build plus mobile smoke.

### After Session 3
- Capture shared hero/section/toolbar examples on:
  - incoming
  - dashboard
  - candidates or slots shell
- Confirm no new inline styles were introduced.
- Run lint/test/build.

## What Waits Until Later Waves
- Full candidate detail restructure waits until W4 after primitives settle.
- City-edit and system cleanup wait until W6 after form grammar and card/table parity exist.
- Test-builder graph cleanup waits until admin workspace rules exist.
- Full motion polish waits until W7; do not polish animation early.

## Practical Start Order
1. W1 foundation
2. W2 shell
3. W3 shared components
4. `/app/incoming`
5. `/app/slots`
6. `/app/candidates`
7. `/app/dashboard`
8. `/app/messenger`
9. `/app/candidates/$candidateId`
10. `/app/calendar`
