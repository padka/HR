# Repository Workflow Guide

## Start Sequence

1. Read [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. Read [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. Read [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
4. Read [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
5. Read [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
6. Run `git status --short`
7. Inspect the exact files you plan to touch

## Working Rules

- Keep tasks narrow.
- Inspect before editing.
- Prefer updating code and permanent docs over creating new root markdown packages.
- If temporary markdown notes are needed during a task, delete them before closing the task.
- Keep subsystem docs under [docs](/Users/mikhail/Projects/recruitsmart_admin/docs), not in repo root.

## Verification Rule

- Backend changes: run `make test`
- Frontend changes: run:
  - `npm --prefix frontend/app run lint`
  - `npm --prefix frontend/app run typecheck`
  - `npm --prefix frontend/app run test`
  - `npm --prefix frontend/app run build:verify`
- Add `npm --prefix frontend/app run test:e2e:smoke` when UI, routing, mobile, overlays, or shell behavior changes

## Reporting Rule

Every finished task should report:
- what was done
- files changed
- commands run
- outcomes
- remaining risks

## Cleanup Rule

- Closed task markdown files do not stay in repo root.
- If a prompt/TODO/spec/checklist file is no longer active, delete it.
- If a note must be preserved, merge it into a durable doc instead of keeping a one-off file.
