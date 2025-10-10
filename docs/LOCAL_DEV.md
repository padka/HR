# Local Admin UI Development

This guide captures everything needed to spin up the admin UI locally on Python&nbsp;3.13.

## Quick start

1. Create a fresh virtualenv (Python&nbsp;3.13 recommended):
   ```bash
   python3.13 -m venv .venv
   ```
2. Install project dependencies and run the preflight checks:
   ```bash
   make setup
   ```
3. Provide a session secret so the admin login works:
   ```bash
   export SESSION_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')
   ```
   Add the line to `.env` if you want it persisted.
4. Start the API:
   ```bash
   make run
   ```

The `make setup` target installs Python dependencies (via `pip install -e ".[dev]"`), Node tooling, downloads Playwright browsers, and finally runs `make doctor` to verify your environment.

## Environment variables

| Variable | Purpose | Notes |
| --- | --- | --- |
| `SESSION_SECRET_KEY` | Enables session cookies for the admin UI | Mandatory for local auth. `SESSION_SECRET` or `SECRET_KEY` are accepted aliases. |
| `ADMIN_TRUSTED_HOSTS` | Comma-separated list of allowed hosts | Defaults to `localhost,127.0.0.1,testserver`. |
| `FORCE_SSL` | Redirect all HTTP traffic to HTTPS | Optional. Leave unset for local development. |

## Troubleshooting

- **`make doctor` fails with missing package** – rerun `make setup`; it pins all Python dependencies for Python&nbsp;3.13.
- **Session middleware disabled warning** – export `SESSION_SECRET_KEY` before `make run`. Without it, admin logins will not persist.
- **Using a different Python version** – the tooling expects Python&nbsp;3.13. Use `pyenv` or `asdf` to install the required interpreter, or override `PYTHON=python3.13` when running `make setup`.
- **TLS redirects during local testing** – ensure `FORCE_SSL` is unset. HTTPS redirects are only activated when `FORCE_SSL=1`.

Run `make doctor` anytime you change environments to confirm everything is ready.

