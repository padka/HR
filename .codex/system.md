# Codex System Guardrails

- Always base work on the `codex/prepare-repo` branch rebased onto the latest `main`.
- Keep the repository free from merge-conflict markers and rely on pre-commit hooks for linting/formatting.
- Use the standardized workflows: `make install`, `make test`, `make ui`, and `make codex` before pushing.
- Python support targets 3.11 – 3.13 with strict type-checking and Ruff/Black/Isort alignment.
- UI builds must succeed with Node.js 20; `npm run build` is the canonical command.
- Document every change with root-cause, fix, verification, and risk/rollback notes in PRs.
