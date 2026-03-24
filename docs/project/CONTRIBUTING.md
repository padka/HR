# Contributing Guidelines

Keep changes small, verified, and aligned with the current root docs.

## Working Rules

1. Start from the latest shared base branch or the current active work branch.
2. Install dependencies with `make install` and `npm --prefix frontend/app install`.
3. Use [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md) as the source of truth for validation.
4. Run the relevant gate for the area you touched:
   - backend: `make test`
   - frontend: `npm --prefix frontend/app run lint`, `typecheck`, `test`, `build:verify`
   - UI/routing/shell changes: add `npm --prefix frontend/app run test:e2e:smoke`
5. Do not commit merge-conflict markers.
6. Keep type hints in place where they clarify contracts.
7. Update durable docs when repo policy, active scope, or workflow changes.
8. Pass only JSON-serializable data into Jinja templates.

## PR Shape

Use a compact summary:

- Root cause
- Fix
- Verification
- Risks / rollback

## Notes

- There is no separate Codex meta-command in the current workflow; use the commands in [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md).
- For current repo policy, use [AGENTS.md](/Users/mikhail/Projects/recruitsmart_admin/AGENTS.md), [engine.md](/Users/mikhail/Projects/recruitsmart_admin/engine.md), and [VERIFICATION_COMMANDS.md](/Users/mikhail/Projects/recruitsmart_admin/VERIFICATION_COMMANDS.md).
