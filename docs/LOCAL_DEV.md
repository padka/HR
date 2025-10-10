# Local development checklist

The admin UI now standardises on **Python 3.12** (3.11 temporarily supported) and **Node 20**. Use the matrix below to spin up
an environment on macOS or Linux.

## Runtime matrix

| Platform | Python setup | Node setup | Notes |
| --- | --- | --- | --- |
| macOS (Apple Silicon) | `brew install pyenv` → `pyenv install 3.12.6` | `nvm install 20` | Export `PYTHON=python3.12` when running `make setup`. |
| macOS (Intel) | Same as above or use `python-build 3.12.6` | `fnm install 20` | Rosetta not required. |
| Ubuntu 22.04+ | `sudo apt install python3.12 python3.12-venv` | `curl -fsSL https://deb.nodesource.com/setup_20.x \| sudo -E bash -` | Ensure `python3.12-venv` is present before creating the virtualenv. |
| Other distros | Build from source via `pyenv` | `nvm`/`fnm` | Keep Node pinned to 20.x to match the lockfile. |

## Quick start

1. Create a virtual environment:
   ```bash
   python3.12 -m venv .venv
   ```
   Python 3.11 still works but will produce a warning in `make doctor`.
2. Bootstrap tooling and run preflight checks:
   ```bash
   make setup
   ```
   This installs `.[dev]`, Node devDependencies, Playwright browsers, and runs `make doctor`.
3. Provide a session secret (once per machine):
   ```bash
   export SESSION_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
   echo "SESSION_SECRET_KEY=$SESSION_SECRET_KEY" >> .env
   ```
4. Start the admin UI:
   ```bash
   make run
   ```
5. (Optional) Render previews and smoke screenshots:
   ```bash
   make previews
   make screens
   ```

## Verification commands

- `make doctor` — checks Python runtime (3.12 recommended) and confirms core imports (`fastapi`, `sqlalchemy`, `pydantic`, etc.).
  Python 3.11 reports **WARN** with an upgrade hint; older versions fail.
- `deptry .` — validates Python imports against the dependency list.
- `npx depcheck` — inspects Node devDependencies; mark PostCSS/Tailwind plugins as used if depcheck asks for confirmation.
- `make ui` — rebuilds `static/build/main.css` using the pinned Tailwind pipeline.

## Environment variables

| Variable | Purpose | Notes |
| --- | --- | --- |
| `SESSION_SECRET_KEY` | Enables session cookies | Mandatory for local auth (`SESSION_SECRET`/`SECRET_KEY` aliases still work). |
| `ADMIN_TRUSTED_HOSTS` | Comma-separated allow-list | Defaults to `localhost,127.0.0.1,testserver`. |
| `FORCE_SSL` | Force HTTPS in local runs | Leave unset during development. |

## Troubleshooting

- **`make doctor` shows WARN on Python 3.11** — upgrade to 3.12 when possible; functionality remains intact meanwhile.
- **Node engine warning with newer Node** — install Node 20 via `nvm`/`fnm` to silence `npm` warnings and stay aligned with CI.
- **Missing Playwright browsers** — rerun `make setup` or `npx playwright install --with-deps`.
- **Session secret warning** — export `SESSION_SECRET_KEY` before running `make run` to avoid anonymous sessions.

Run `make doctor` after any toolchain change to confirm the environment is healthy.
