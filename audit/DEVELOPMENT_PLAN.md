# Roadmap по доработке проекта

## 1. Стабилизация инфраструктуры (P0)

### 1.1. Привести зависимости в порядок
- Синхронизировать `pyproject.toml`, `requirements-dev.txt`, `requirements.txt` (если появится) и `Makefile`, добавив недостающие рантайм-зависимости: `apscheduler`, `python-multipart`, `alembic`, а также привести версии FastAPI/Starlette к зафиксированному диапазону.
- Пересобрать lock-файлы и убедиться, что `pip install -e .[dev]` поднимает весь стек, включая Playwright CLI.
- Обновить CI (`.github/workflows/ci.yml`) так, чтобы установка зависимостей шла из единого источника.

**Артефакты:** `pyproject.toml`, `requirements-dev.txt`, `Makefile`, `.github/workflows/ci.yml`.

### 1.2. Исправить bootstrap базы и миграции
- В `backend/core/bootstrap.py` обеспечить обязательный прогон Alembic миграций на чистой базе, добавить контроль успешного создания `slot_reminder_jobs`.
- Проверить миграцию `0008_add_slot_reminder_jobs.py` на повторный запуск.
- Добавить smoke-тест `audit/run_smoke_checks.py` в CI и `make dev-db` для локального сценария.

**Артефакты:** `backend/core/bootstrap.py`, `backend/migrations/runner.py`, `backend/migrations/versions/0008_add_slot_reminder_jobs.py`, `Makefile`, CI workflow.

### 1.3. Починить тестовый контур
- Обновить тестовые хелперы под Starlette ≥0.37 (`follow_redirects`) и зафиксировать версию клиента в зависимостях.
- Включить обязательный прогрев Playwright: `playwright install --with-deps` в README, Makefile и CI.
- Прогнать smoke и e2e тесты в CI матрице после фиксов.

**Артефакты:** `tests/test_admin_recruiters_ui.py`, обвязка тестов, `.github/workflows/ci.yml`, `README.md`, `Makefile`.

## 2. Безопасность и DevEx (P1)

### 2.1. Укрепить аутентификацию админки
- Перевести `.env.example` в шаблон без реальных значений, добавить валидацию секретов при старте.
- Расширить `require_admin` логированием и rate-limit (например, через `starlette.middleware.sessions` + custom throttling или интеграцию с внешним nginx rate limit).
- Включить стандартные security middleware (`HTTPSRedirectMiddleware`, `TrustedHostMiddleware`, `SecurityMiddleware` с CSP/HSTS) в `backend/apps/admin_ui/app.py`.

**Артефакты:** `.env.example`, `backend/apps/admin_ui/security.py`, `backend/apps/admin_ui/app.py`, `backend/core/settings.py`.

### 2.2. Улучшить DX
- Добавить цели `make bootstrap`, `make dev-db`, `make test` с последовательной установкой Poetry/pip, применением миграций и запуском тестов.
- Обновить README/`docs/` пошаговыми инструкциями (backend, frontend, Playwright, smoke).
- Задокументировать процесс обновления Liquid Glass токенов и правил для шаблонов.

**Артефакты:** `Makefile`, `README.md`, `docs/` (новый раздел DevEx).

## 3. Liquid Glass и UX (P2)

### 3.1. Привести шаблоны к Liquid Glass
- Провести ревизию шаблонов Jinja (`backend/apps/admin_ui/templates/*`), внедрить готовые токены/utility-классы, унифицировать состояние компонентов (hover, focus, active).
- Настроить автоматическую сборку Tailwind/PostCSS (`npm run build:css`) и добавить снапшоты в `tests/test_ui_screenshots.py`.
- Расширить `tailwind.config.js` пресетами Apple-like blur/gradients, убрать неиспользуемые кастомные классы.

**Артефакты:** `backend/apps/admin_ui/templates/`, `tailwind.config.js`, `ui_screenshots/`, `tests/test_ui_screenshots.py`.

### 3.2. A11y и навигация
- Добавить skip-links и aria-live регионы в `base.html` и формы (`recruiters_new.html`, `candidates_new.html`).
- Исправить mobile-nav: фокус-ловушки, управление клавиатурой, контраст кнопок.
- Прогнать автоматические проверки (axe/pa11y) и добавить чек-лист в `docs/ACCESSIBILITY.md`.

**Артефакты:** `backend/apps/admin_ui/templates/base.html`, `backend/apps/admin_ui/templates/recruiters_new.html`, `backend/apps/admin_ui/templates/candidates_new.html`, новый `docs/ACCESSIBILITY.md`.

## 4. Контроль качества и метрик

- Автоматизировать сбор метрик (`audit/collect_metrics.py`) в CI и сохранять артефакты (CSS селекторы, время ответа API) для отслеживания Liquid Glass прогресса.
- Включить `audit/run_smoke_checks.py` в nightly pipeline, публиковать результаты в `METRICS.md`/`QUALITY.md`.
- Настроить pre-commit хуки (ruff, mypy, black) и согласовать с CI.

**Артефакты:** `.github/workflows/ci.yml`, `audit/collect_metrics.py`, `audit/METRICS.md`, `.pre-commit-config.yaml`.

## 5. Таймлайн и приоритезация

1. **Неделя 1 (P0):** зависимости, bootstrap, тесты, smoke.
2. **Неделя 2 (P1):** безопасность, DevEx, документация.
3. **Неделя 3-4 (P2):** Liquid Glass ревизия, a11y, визуальные снапшоты, метрики.

Каждый блок завершать демо/ревью и фиксацией артефактов в README и `docs/`.
