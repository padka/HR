# Repository Workflow Guide

## Purpose

This guide explains how Codex should work inside this repository without re-discovering the same context every session.

## Start A Task

1. Read:
   - [README.md](/Users/mikhail/Projects/recruitsmart_admin/README.md)
   - [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md)
   - [PROJECT_CONTEXT_INDEX.md](/Users/mikhail/Projects/recruitsmart_admin/PROJECT_CONTEXT_INDEX.md)
   - [CURRENT_PROGRAM_STATE.md](/Users/mikhail/Projects/recruitsmart_admin/CURRENT_PROGRAM_STATE.md)
   - [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md)
2. Check the current worktree:
   ```bash
   git status --short
   ```
3. Inspect the exact files involved in the task before proposing edits.
4. Open the relevant canonical spec set if the task touches redesign, rollout, or QA.

## Inspect Before Changing Code

- Prefer `rg`, `rg --files`, `sed -n`, `wc -l`, and targeted file reads.
- Check both implementation files and adjacent tests/configs.
- For frontend tasks, always inspect:
  - route file
  - shared theme file
  - `main.tsx` or `__root.tsx` if routing/shell is involved
  - relevant Playwright/Vitest coverage
- For backend tasks, always inspect:
  - route/controller entrypoint
  - service layer
  - shared settings/db/auth modules if impacted
  - targeted tests

## Plan In Verified Batches

- Define a short plan before editing.
- Keep one logical change set per batch.
- Avoid mixing repo-setup work, redesign work, and backend business logic in the same batch unless tightly coupled.
- If the task is large, split by wave or subsystem and verify each wave separately.

## Preferred Batch Structure

1. Inspect and confirm scope
2. Edit one ownership area
3. Run relevant checks
4. Summarize results and remaining risks
5. Only then move to the next area

## Working With Existing Planning Packages

- If the task is redesign implementation, do not create a new roadmap.
- Use the existing root handoff chain:
  - [DESIGN_DECISIONS_LOG.md](/Users/mikhail/Projects/recruitsmart_admin/DESIGN_DECISIONS_LOG.md)
  - [CODEX_EXECUTION_PLAN.md](/Users/mikhail/Projects/recruitsmart_admin/CODEX_EXECUTION_PLAN.md)
  - [EPIC_BREAKDOWN_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/EPIC_BREAKDOWN_FOR_CODEX.md)
  - [TASK_GRAPH_FOR_CODEX.md](/Users/mikhail/Projects/recruitsmart_admin/TASK_GRAPH_FOR_CODEX.md)
- If the task changes execution assumptions materially, update the relevant canonical file instead of creating a shadow doc.

## How To Work In Parallel

- Split only when ownership boundaries are clean.
- Good split candidates:
  - docs-only work
  - route audits after shell/foundation is fixed
  - QA/playwright work after UI structure stabilizes
  - isolated backend integration modules
- Bad split candidates:
  - `__root.tsx`
  - theme foundations
  - auth/session/security
  - migrations
  - root canonical docs

Detailed rules live in [MULTI_AGENT_STRATEGY.md](/Users/mikhail/Projects/recruitsmart_admin/MULTI_AGENT_STRATEGY.md).

## When To Use Separate Branches Or Worktrees

- Use separate branches/worktrees for:
  - independent screen clusters
  - QA-only follow-ups
  - docs-only repo-setup tasks
  - integration modules that do not touch shared settings or shell/theme
- Do not split branches when:
  - multiple tasks edit the same root theme file
  - multiple tasks edit the same route monolith
  - the task depends on unstable unfinished foundations

## Avoiding Overlap

- Claim one ownership area per agent/session.
- List touched files in the task brief or session log before editing.
- If a file is already heavily modified in the worktree, inspect carefully and work around existing changes instead of resetting them.
- If overlap is unavoidable, sequence the work instead of parallelizing it.

## Verification Before Closing A Task

- Run the exact relevant commands, not just “basic checks”.
- Report both commands and outcomes.
- If a command was intentionally skipped, say why.
- For frontend work, `build:verify` is the default final gate.
- For backend work, `make test` is the default final gate.
- For shell/mobile/routing work, add Playwright smoke.

## Documentation Update Rules

Update docs when:
- the canonical scope changes
- the preferred commands change
- the active redesign wave changes
- doc precedence changes
- a task creates new canonical files

Do not create redundant docs when one of the existing canonical files can be updated instead.

## Reporting Format

Each finished task should report:
- what was done
- files changed
- commands run
- outcomes
- remaining risks
- next recommended step

Use [SESSION_LOG_TEMPLATE.md](/Users/mikhail/Projects/recruitsmart_admin/SESSION_LOG_TEMPLATE.md) for long or resumable sessions.

## Closing Checklist

- Scope stayed controlled
- Verification ran
- Canonical docs are still accurate
- No unrelated files were reverted
- Remaining risks are explicit
- The next agent has a clear next step
