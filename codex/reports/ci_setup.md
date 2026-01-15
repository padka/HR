# CI dry-run notes — 2025-10-18

## Workflow outline
1. Check out sources.
2. Provision Python 3.12 and Node.js 20.
3. Install Python dependencies from `pyproject.toml` via `pip install -e ".[dev]"`.
4. Install frontend dependencies with `npm ci`.
5. Build Tailwind bundle via `npm run build`.
6. Execute `pytest -q` (currently fails because uvloop's default event loop policy is not initialised in tests and Playwright browsers are missing).
7. Start FastAPI (`uvicorn backend.apps.admin_ui.app:app`) with bootstrap credentials sourced from the workflow environment.
8. Probe `http://127.0.0.1:8000/health` via `curl` and tear down the background server.

## Known issues
- Pytest raises `RuntimeError: There is no current event loop in thread 'MainThread'` across async suites when uvloop is selected by default.
- Playwright tests fail until `npx playwright install --with-deps` runs in CI.
- The health check requires `ADMIN_USER`, `ADMIN_PASSWORD`, and `SESSION_SECRET_KEY` to be set; placeholder secrets shorter than 32 characters are rejected.

## Follow-up recommendations
- Provide a test fixture or monkeypatch to initialise `asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())` during tests when uvloop is unavailable.
- Cache `npm` dependencies and Playwright browsers to keep CI time reasonable.
- Consider splitting the Playwright suite into an optional job gated behind a flag.
