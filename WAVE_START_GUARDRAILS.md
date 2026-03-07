# Wave Start Guardrails

## Active Wave

First implementation wave for the frontend redesign program.

## Active Scope

- W1 foundation layer
- W2 shell semantics
- Only mounted SPA routes indirectly affected by shared shell/foundation contracts
- Current session target: first verified batch within W1/W2

## Out Of Scope

- Recruiter route migration beyond what is required to prove W1/W2
- Admin route cleanup
- Dormant routes:
  - `frontend/app/src/app/routes/app/vacancies.tsx`
  - `frontend/app/src/app/routes/app/reminder-ops.tsx`
- Backend/API/business-logic changes
- Broad `global.css` refactor

## Mandatory Operating Rules

- Read canonical root docs first
- Create/update current run artifacts before code edits
- Inspect exact implementation files before patching
- Work in verified batches only
- Log every batch outcome
- Do not merge shell and route-local cosmetic rewrites into one undocumented batch

## Regression Watchpoints

- `frontend/app/src/app/routes/__root.tsx`
- `frontend/app/src/theme/pages.css`
- `frontend/app/src/theme/mobile.css`
- `frontend/app/src/theme/components.css`
- mobile More sheet behavior
- quiet vs ambient route mapping
- safe-area, z-index, overlay focus return

## Required End-Of-Batch Evidence

- files changed
- commands run
- command outcomes
- remaining risks
- next batch decision
