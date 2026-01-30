# Contributing Guidelines

Welcome to the Smart Service monorepo. To keep the project stable, please follow these rules before opening a pull request:

1. Base your work on a branch rebased from the latest `main` (default automation branch: `codex/prepare-repo`).
2. Install dependencies and tools via `make install` (Python + Node.js) and keep Node.js at version 20.
3. Run the full guardrail pipeline with `make codex`. This wraps dependency installation, pre-commit checks, the Python test suite, and the UI build.
4. Do not commit merge-conflict markers; pre-commit hooks enforce formatting (Black, Isort) and linting (Ruff) automatically.
5. Add mypy annotations where necessary to satisfy strict type checks. Use `mypy.ini` overrides for migrations/tests only when required.
6. Document changes in PRs using the template (Root cause → Fix → Verification → Risks/Rollback).
7. Pass only JSON-serializable (dict/list/primitive) structures into Jinja templates; convert ORM objects via Pydantic out-schemas or manual dumps before rendering.

Thank you for contributing!
