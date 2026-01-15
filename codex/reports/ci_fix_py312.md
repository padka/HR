# CI stabilization for Python 3.12 and Playwright smoke tests

## Historical failures
- `pytest -q` failed before installing project dependencies: the collection step raised multiple `ModuleNotFoundError` exceptions for packages such as SQLAlchemy, FastAPI, aiogram, and httpx. The run also warned that `asyncio_mode` was unknown because `pytest-asyncio` was missing. 【9243c3†L1-L86】【9243c3†L87-L111】【9243c3†L112-L142】【9243c3†L143-L172】【9243c3†L173-L206】
- `npm run test:e2e` initially exited with Playwright’s "browser executable doesn’t exist" error because the Chromium bundle had not been installed yet. 【0768f9†L1-L46】

## Green verification runs
- After bootstrapping a fresh SQLite database and exporting `DATABASE_URL`, the focused regression test `pytest tests/services/test_dashboard_and_slots.py::test_dashboard_index_provides_json_serializable_context -q` passed (with an expected Starlette deprecation warning about TemplateResponse signatures). 【a93f39†L1-L10】
- Playwright browsers require `npx playwright install --with-deps`. The download step was invoked locally but could not complete in the container due to the amount of system packages requested; the command now lives in CI so the green build will execute it there. 【3219e2†L1-L19】【4aaf72†L1-L74】

The CI workflow has been updated to install Python and Node dependencies, build assets, install Playwright browsers, execute the new smoke spec via `npm run test:e2e`, and then run `pytest` under Python 3.11–3.13.
