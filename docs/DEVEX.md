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

* Основная таблица стилей расположена в `backend/apps/admin_ui/static/css/main.css`
  и подключается напрямую через базовый шаблон. Цветовые токены хранятся в
  `backend/apps/admin_ui/static/css/tokens.css`.
* При обновлении стилей правьте `main.css` и токены, после чего вручную
  проверяйте ключевые страницы через `uvicorn`. Дополнительной сборки Tailwind
  больше не требуется.

## Playwright and UI automation

* `make bootstrap` installs the Playwright CLI and downloads the required
  browsers. Afterwards run UI snapshot tests with:

  ```bash
  pytest tests/test_ui_screenshots.py
  ```

* Regenerate snapshots intentionally via `pytest tests/test_ui_screenshots.py --update-snapshots`.
* Store custom Playwright helpers under `tests/` and document them inline—the
  project currently favours pytest-style fixtures over bespoke CLI wrappers.

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

* Цветовые и радиусные токены, а также значения blur/shadow теперь описаны в
  `backend/apps/admin_ui/static/css/tokens.css`. Обновляйте их там и фиксируйте
  изменения в комментариях коммита.
* После обновления токенов убедитесь, что связанные утилиты в `main.css`
  используют `rgb(var(--token))` и при необходимости скорректируйте оттенки.
* Шаблоны под `backend/apps/admin_ui/templates/` должны продолжать опираться на
  существующие утилиты (`.glass`, `.badge-*`, `.btn-*`). Новые цвета или
  тени добавляйте исключительно через токены.

## Liquid Glass template conventions

* Include skip-links and ARIA annotations when extending forms. The base layout
  exposes `#main-content` as the primary landmark for assistive technologies.
* Whenever a template introduces a new interaction, ensure keyboard navigation
  is possible and that focus outlines remain visible against Liquid Glass
  gradients.
* Document any deviation from these guidelines directly in the template and in
  commit messages so that design reviews remain traceable.
