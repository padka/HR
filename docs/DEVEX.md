# Developer Experience Guide

This document consolidates the day-to-day commands and conventions needed to
work on the Liquid Glass admin UI.

## Backend workflows

1. **Bootstrap dependencies** – run `make bootstrap` to install Python
   dependencies via `pip install -e ".[dev]"`, provision Node tooling, and
   download Playwright browsers.
2. **Prepare the database** – execute `make dev-db` to apply migrations and seed
   default reference data. The command reuses the same logic as the application
   lifespan hook, which guarantees parity between development and production
   environments.
3. **Run the server** – start the admin panel with `uvicorn` or the supplied
   `app_demo.py` helper once the database is ready:

   ```bash
   make dev-db
   uvicorn backend.apps.admin_ui.app:app --reload
   ```

   The FastAPI application enforces HTTP Basic authentication. Configure
   `ADMIN_USER`, `ADMIN_PASSWORD` and `SESSION_SECRET` before launching the
   server. Placeholders such as `admin` or `change-me` are rejected during the
   startup validation phase.

## Frontend workflows

* Build Tailwind assets on demand with `npm run build:css`. The output is
  written to `backend/apps/admin_ui/static/build/main.css` and served directly by
  FastAPI.
* Tailwind configuration derives from `tailwind.config.js`. Extend the Liquid
  Glass design tokens in that file and keep utility classes close to the
  pre-defined palette to ensure a consistent look-and-feel.

## Playwright and UI automation

* `make bootstrap` installs the Playwright CLI and downloads the required
  browsers. Afterwards run UI snapshot tests with:

  ```bash
  pytest tests/test_ui_screenshots.py
  ```

* Regenerate snapshots intentionally via `pytest tests/test_ui_screenshots.py --update-snapshots`.
* Store custom Playwright helpers under `tests/` and document them inline—the
  project currently favours pytest-style fixtures over bespoke CLI wrappers.

## Dependency updates

* The single source of truth for Python dependencies is `pyproject.toml`.
  Runtime requirements live in `[project.dependencies]`, and developer tooling
  lives in `[project.optional-dependencies].dev`.
* To add or upgrade a dependency:
  1. Edit `pyproject.toml` with the new pinned version.
  2. Reinstall extras locally: `pip install -e ".[dev]"`.
  3. Run the relevant checks (`make test`, `pytest`, or CI-equivalent commands).
  4. If you touched runtime dependencies, rebuild the Docker image or rerun the
     deployment installation step (`pip install -e ".[dev]"`) before validation.

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

* Tailwind tokens that power the Liquid Glass look reside in
  `tailwind.config.js`. Update colour ramps, blur strengths and gradient stops in
  that file and document rationale in the accompanying comments.
* When tokens change, rebuild CSS (`npm run build:css`) and refresh screenshot
  baselines to capture the new appearance.
* Template partials under `backend/apps/admin_ui/templates/` should only use
  approved utility classes. Keep hover/focus/active states aligned with the
  shared components catalogue and avoid embedding ad-hoc colours—prefer token
  aliases defined in Tailwind.

## Liquid Glass template conventions

* Include skip-links and ARIA annotations when extending forms. The base layout
  exposes `#main-content` as the primary landmark for assistive technologies.
* Whenever a template introduces a new interaction, ensure keyboard navigation
  is possible and that focus outlines remain visible against Liquid Glass
  gradients.
* Document any deviation from these guidelines directly in the template and in
  commit messages so that design reviews remain traceable.
