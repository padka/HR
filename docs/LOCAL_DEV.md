# Local Admin UI Development

This guide captures everything needed to spin up and validate the admin UI locally on Python&nbsp;3.13.

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

## Working with themes

- The header contains a tri-state theme button (`auto → light → dark`). Press it or use <kbd>Shift</kbd>+<kbd>Alt</kbd>+<kbd>T</kbd> to cycle when focused.
- The current preference lives in `localStorage['tg-admin-theme']`. Remove the key (or set it to `auto`) to return to system defaults.
- The runtime helper is exposed as `window.TGTheme.apply('light' | 'dark' | 'auto')` for quick experimentation in DevTools.
- To emulate system changes, open Chrome DevTools → **Rendering** panel and toggle `Emulate CSS prefers-color-scheme` between `light` and `dark`. The UI should follow automatically when the mode is `auto`.

## Screenshots & automated UI checks

- `make screens` runs Playwright in headless mode and captures screenshots for every demo route across three viewports (desktop/tablet/mobile) and both themes. Artifacts land in `ui_screenshots/` and are uploaded by CI.
- `pytest tests/test_ui_screenshots.py` is the underlying test suite. It also verifies that the theme toggle persists choices via `localStorage` and that recruiter cards respond to keyboard input.
- If Playwright complains about missing browsers, rerun `npx playwright install --with-deps`.

## Recruiter UI demo

- `make demo` launches the FastAPI showcase on http://127.0.0.1:8000.
- `/recruiters` renders the liquid glass grid with actions (open, disable, copy link) and keyboard-friendly focus states.
- `/recruiters/10/edit` demonstrates the city multi-select and unsaved-changes guard; `Select all` respects the current search filter.

## Troubleshooting

- **`make doctor` fails with missing package** – rerun `make setup`; it pins all Python dependencies for Python&nbsp;3.13.
- **Session middleware disabled warning** – export `SESSION_SECRET_KEY` before `make run`. Without it, admin logins will not persist.
- **Using a different Python version** – the tooling expects Python&nbsp;3.13. Use `pyenv` or `asdf` to install the required interpreter, or override `PYTHON=python3.13` when running `make setup`.
- **TLS redirects during local testing** – ensure `FORCE_SSL` is unset. HTTPS redirects are only activated when `FORCE_SSL=1`.
- **Theme toggle appears stuck** – clear `localStorage['tg-admin-theme']` and reload; the app will fall back to the system preference.
