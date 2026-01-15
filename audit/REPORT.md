# Итоговый отчёт (Liquid Glass audit)

## Главное
1. **База не поднимается на чистой среде.** `ensure_database_ready()` требует alembic и падает до создания таблиц (`slot_reminder_jobs`). Без ручной установки `alembic` сервис не стартует. 【F:backend/core/bootstrap.py†L19-L53】【F:audit/smoke_no_db.log†L1-L8】
2. **Пакетная установка выровнена.** Базовые и dev‑зависимости закреплены в `pyproject.toml`, поэтому `pip install -e ".[dev]"` и CI используют единый источник истины. 【F:pyproject.toml†L19-L78】【F:.github/workflows/ci.yml†L1-L34】
3. **Тестовый контур нестабилен.** `pytest` падает на несовместимом API `TestClient` и отсутствии playwright-браузеров, что блокирует release pipeline. 【F:audit/pytest.log†L1-L116】
4. **Админка защищена только HTTP Basic и демо-секретами.** `.env.example` хранит реальные ID и дефолтные пароли, `require_admin` не усиливает безопасность. 【F:.env.example†L1-L37】【F:backend/apps/admin_ui/security.py†L15-L38】
5. **Внедрение Liquid Glass незавершено.** Tailwind-токены подключены, но шаблоны используют ограниченное число классов (≈60 селекторов), отсутствуют визуальные снапшоты и a11y-хуки. 【F:tailwind.config.js†L1-L56】【F:audit/METRICS.md†L1-L19】

Позитив: модульная структура (`backend/apps`), чистая Jinja2-организация, есть pre-commit и CI матрица 3×Python.

## Карта зависимостей
```
FastAPI (backend/apps/admin_ui.app)
 ├─ Lifespan → ensure_database_ready() → migrations.runner (alembic, SQLAlchemy)
 │                                        ↳ domain.models (Declarative Base)
 ├─ Lifespan → setup_bot_state() → bot.services (aiogram, apscheduler)
 │                                ↳ bot.reminders (scheduler, redis)
 ├─ Routers → services.* → repositories (DB sessions via backend.core.db)
 └─ Templates → static CSS (Tailwind tokens, build/main.css)

admin_ui API
 └─ HTTP Basic require_admin → settings (env vars)
```

## Liquid Glass соответствие
- **Токены:** `tokens.css` подключён, Tailwind расширен цветами/blur (Apple-like). 【F:backend/apps/admin_ui/templates/base.html†L18-L27】【F:tailwind.config.js†L1-L56】
- **Компоненты:** списки/формы используют кастомные классы (`surface glass`, `choice-tile`), но не все страницы применяют стеклянные эффекты, отсутствуют state-анимации. 【F:backend/apps/admin_ui/templates/recruiters_new.html†L1-L60】
- **Сборка:** `npm run build:css` выдаёт `main.css` 39,5 KB, ≈60 уникальных селекторов (нужно расширять). 【F:audit/METRICS.md†L1-L14】
- **DX:** нет автоматической проверки дизайна/скриншотов, Playwright тесты падают без ручного `playwright install`. 【F:audit/pytest.log†L65-L116】

## Roadmap (DoD)
- **P0 (устойчивость):** синхронизировать зависимости, починить миграции на чистой БД, привести pytest/Playwright к стабильному состоянию.
- **P1 (безопасность & DX):** убрать демо-секреты, добавить security middleware, автоматизировать bootstrap (`make dev-db`), задокументировать установку браузеров.
- **P2 (Liquid Glass & a11y):** ревизия шаблонов под стекло, внедрение визуальных снапшотов, добавить skip-links/aria-live и фокус-менеджмент.
