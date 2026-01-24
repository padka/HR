# Developer Experience Guide

This document consolidates the day-to-day commands and conventions needed to
work on the Liquid Glass admin UI.

## Backend workflows

1. **Bootstrap dependencies** – run `make bootstrap` to install Python
   dependencies via Poetry (when available) or pip and to provision Node tooling
   and Playwright browsers.
2. **Prepare the database** – execute `make dev-db` to apply migrations and seed
   default reference data. The command reuses the same logic as the application
   lifespan hook, which guarantees parity between development and production
   environments.
3. **Run the server** – start the admin panel with `uvicorn` once the database
   is ready:

   ```bash
   make dev-db
   uvicorn backend.apps.admin_ui.app:app --reload
   ```

   The FastAPI application enforces HTTP Basic authentication. Configure
   `ADMIN_USER`, `ADMIN_PASSWORD` and `SESSION_SECRET` before launching the
   server. Placeholders such as `admin` or `change-me` are rejected during the
   startup validation phase.

## Frontend workflows

* Start the SPA dev server:

  ```bash
  npm --prefix frontend/app run dev
  ```

* Build the SPA bundle for FastAPI to serve from `/app`:

  ```bash
  npm --prefix frontend/app run build
  ```

  Output goes to `frontend/dist/` and is mounted by the backend.

## Playwright and UI automation

* E2E tests live under `frontend/app/tests/e2e` with config in
  `frontend/app/playwright.config.ts`.
* Run E2E tests from the SPA workspace:

  ```bash
  npm --prefix frontend/app run test:e2e
  ```

## Smoke testing

* Lightweight smoke checks are bundled under `audit/run_smoke_checks.py`. To
  verify the admin UI without touching the database run:

  ```bash
  python audit/run_smoke_checks.py
  ```

* To prime the database first, append `--with-db`. The script honours the same
  authentication variables as the main application (`ADMIN_USER`,
  `ADMIN_PASSWORD`) and defaults to the safe test credentials defined in
  `.env.example`.

## Liquid Glass token maintenance

* Design tokens are defined in the SPA theme layer (`frontend/app/src/theme`).
  Update colour ramps, blur strengths and gradient stops there, then rebuild the
  SPA bundle.
* When tokens change, refresh screenshot baselines to capture the new
  appearance.
