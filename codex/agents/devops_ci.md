# Агент DevOps & CI

## Цель
Построить надёжный pipeline GitHub Actions: lint → test → build, публиковать артефакты (Vite манифест, Playwright отчёты), подготовить базовый Dockerfile/compose.

## Контекст
- Python backend (`backend/apps/admin_ui/app.py`) + JS сборка (Tailwind/Vite).
- Python dependencies: `pyproject.toml` (runtime + `dev` extras), Node `package.json`.
- Существующие Make-таргеты: `make bootstrap`, `make dev-db`, `make test`.
- Нет настроенного manifest-helper и Docker-образа.

## Дорожная карта
1. **CI pipeline**
   - Workflow `.github/workflows/ci.yml`: matrix Python 3.11 + Node 20.
   - Шаги: checkout, setup-python (cache pip), setup-node (cache npm), install deps (`pip install -e ".[dev]"`, `npm ci`).
   - Джобы: `lint` (ruff/black/mypy), `test` (pytest, Playwright smoke), `build` (npm run build, uvicorn smoke via `python -m compileall` + `pytest -k smoke`).
   - Сохранять артефакты: `frontend-dist/manifest.json`, `playwright-report/`, `coverage.xml`.
2. **Docker/Compose**
  - Dockerfile: базовый `python:3.11-slim`, установка Poetry/pip, копирование `pyproject.toml`, `requirements`, `backend`, `codex` (без dev).
  - Stage для Node build: `node:20` → Vite build → копия ассетов.
  - docker-compose: сервисы `admin` (uvicorn), `db` (PostgreSQL), `redis` (если потребуется для очередей напоминаний).
3. **Секреты и конфигурация**
   - Использовать GitHub Actions secrets: `ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `DATABASE_URL` (для миграций в CI).
   - Masking логов, `FORCE_SSL=false` для CI.
4. **Наблюдаемость**
   - Добавить step upload `uvicorn` logs, `pytest` junit XML, `axe` результаты.
   - Подготовить мониторинг health (`curl http://localhost:8000/health`).

## DoD
- Workflow зелёный для ветки `develop` и PR.
- Dockerfile проходит `docker build` в CI (`--target production`).
- Документация обновлена (`codex/context/guide_full.md`, `codex/context/decisions.log.md`).
- Переменные окружения описаны в `codex/tools/scripts.md`.
