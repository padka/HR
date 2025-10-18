# Скрипты и утилиты

## Python
- `make bootstrap` — создаёт виртуальное окружение в `.venv`, устанавливает Python/Node зависимости.
- `make dev-db` — применяет миграции и заполняет seed-данные через `backend.core.bootstrap.ensure_database_ready()`.
- `make test` — запускает `pytest` с параметрами по умолчанию.
- `python tools/recompute_weekly_kpis.py --weeks 8` — пересчитывает KPI (см. README.md).

## FastAPI / Uvicorn
```bash
uvicorn backend.apps.admin_ui.app:app --reload --host 0.0.0.0 --port $FASTAPI_PORT
```
Переменные окружения: `ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `DATABASE_URL`, `COMPANY_TZ`, `FORCE_SSL` (false локально).

## Node / Vite
- `npm run dev` — запуск Vite dev server (после миграции).
- `npm run build` — production-сборка (генерация `static/build/manifest.json`).
- `npm run lint` — линтеры (добавить при миграции).
- `npm run test:e2e` — Playwright smoke (headless).

## Playwright
```bash
npx playwright install
npm run test:e2e -- --reporter=line --project=chromium
```
Артефакты сохраняются в `playwright-report/` (trace, видео, axe).

## Docker/Compose (план)
- `docker compose up admin` — запускает uvicorn + Vite-бандл (после добавления Dockerfile и compose).
- Секреты прокидываются через `.env` (`ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `BOT_TOKEN`).
