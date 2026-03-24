# Repository Workflow Guide

This is a compatibility guide. The working rules live in [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md) and [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md).

## Standard workflow

1. Read the canonical docs first.
2. Check `git status --short`.
3. Inspect the exact files you plan to touch.
4. Pick the smallest safe change set.
5. Use a matching skill from [`.agents/skills/`](/Users/mikhail/Projects/recruitsmart_admin/.agents/skills/) when the task is medium/high risk or domain-specific.
6. Make the change.
7. Run the relevant validation commands from [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md).
8. Update durable docs if repo policy, workflow, or active scope changed.
9. Delete temporary notes before closing the task.

## Multi-agent workflow

- Use Architect first for non-trivial work.
- Then use Implementer for the approved diff.
- Add Security Reviewer, Scalability Reviewer, UI/UX Reviewer, Docs / Version Verifier, or QA / Browser Flow Reviewer as needed.
- Keep file ownership explicit when running multiple agents.

## Output expectations

- small diff
- explicit verification commands
- risks called out
- no silent assumptions
- no closed-task clutter at repo root
