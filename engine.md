# engine.md

## Purpose

This is the primary persistent operating note for local Codex work in this repository.

Use it for:
- durable repo rules
- markdown retention policy
- current operating boundaries

Do not turn this file into a session log.

## Read Order

1. [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
2. [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
3. [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
4. [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
5. [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
6. relevant implementation files and subsystem docs in [docs](/Users/mikhail/Projects/recruitsmart_admin/docs)

## Current Operating Boundary

- Work locally by default.
- Do not touch VPS or production unless the user explicitly asks for it in that task.
- Prefer small verified batches.
- Do not recreate large planning packages for already-closed work.

## Durable Root Docs

Keep only durable, repeatedly useful root markdown files:
- [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
- [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
- [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md)
- [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
- [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
- [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
- [REPOSITORY_WORKFLOW_GUIDE.md](/Users/mikhail/Projects/recruitsmart_admin/REPOSITORY_WORKFLOW_GUIDE.md)

Everything else at repo root must justify its existence.

## Codex Workspace Layer

- Project-scoped Codex defaults live in [`.codex/config.toml`](/Users/mikhail/Projects/recruitsmart_admin/.codex/config.toml).
- Reusable task skills live in [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/).
- [`.codexrc`](/Users/mikhail/Projects/recruitsmart_admin/.codexrc) remains a compatibility shim until config precedence is fully settled.

## Markdown Retention Policy

- Temporary markdown files are allowed only for:
  - prompt notes
  - TODO lists
  - short specs
  - active task briefs
  - temporary verification/checklist notes
- After the task is completed or abandoned, temporary markdown files must be deleted in the same cleanup pass.
- Do not leave behind:
  - `CURRENT_TASK.md`
  - `SESSION_LOG.md`
  - `VERIFICATION_SUMMARY.md`
  - ad-hoc prompt/spec/checklist files
  if the task is already closed.
- If information is worth keeping, merge it into one of the durable docs or a subsystem doc under [docs](/Users/mikhail/Projects/recruitsmart_admin/docs).
- Prefer git history over keeping large closed-task markdown packages in repo root.

## Documentation Placement Rules

- Root: only durable repo-operating docs.
- `docs/`: subsystem docs, runbooks, contracts, architecture, release notes that stay useful.
- `docs/archive/` and `codex/`: historical context only, not canonical by default.
- Do not create new root-level markdown packages unless the user explicitly asks for a durable root artifact.

## Cleanup Rule For Future Runs

If a task creates temporary markdown files, the same task must also:
1. decide whether the information is durable or temporary
2. merge durable information into an existing permanent doc if needed
3. delete the temporary markdown files before closing the task

## Current Note

- Root markdown cleanup was performed on 2026-03-08.
- Closed task-specific root markdown packages were intentionally removed.
- If an old temporary report is needed, recover it from git history instead of recreating root clutter.
