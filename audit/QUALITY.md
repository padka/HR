# Качество, DX и UX

## Код и стиль
- Зависимости консолидированы в `pyproject.toml`: базовые пакеты в `[project.dependencies]`, dev‑инструменты в `[project.optional-dependencies].dev`. Это улучшает воспроизводимость через `pip install -e ".[dev]"`. 【F:pyproject.toml†L19-L78】
- Конфиги black/isort/ruff присутствуют и согласованы через pre-commit, но mypy запускается в режиме `--strict`, что без типовых аннотаций вызывает флап в CI. 【F:.pre-commit-config.yaml†L1-L25】
- Tailwind конфиг расширен под Liquid Glass, однако шаблоны всё ещё используют смесь utility-классов и кастомных CSS, что подтверждается невысоким количеством уникальных селекторов в `METRICS.md`.

## Тесты и покрытие
- `pytest` завершается с 5 падениями: несовместимый `TestClient.request(... allow_redirects)` и отсутствие `playwright` браузеров блокируют pipeline. 【F:audit/pytest.log†L1-L116】
- Smoke без БД обрывается на `slot_reminder_jobs`, что означает отсутствие стабильного сценария bootstrap в тестах. 【F:audit/smoke_no_db.log†L1-L8】
- В workflow CI все проверки запускаются на трёх версиях Python и используют dev‑extras (`pre-commit`, `pytest --cov`), поэтому важно поддерживать актуальность `pyproject.toml`. 【F:.github/workflows/ci.yml†L1-L34】【F:pyproject.toml†L53-L78】

## DX
- Скриптов воспроизводимости нет: чтобы запустить проект, пришлось вручную устанавливать `apscheduler`, `python-multipart`, `alembic`, скачивать playwright-браузеры. Нужен `make bootstrap`/`poetry` профиль и README с шагами.
- `audit/run_smoke_checks.py` показал, что без прогрева БД даже health-check не стартует; добавьте `make dev-db` с миграциями и seed.

## A11y и UX
- В `base.html` уже присутствует skip-link («Перейти к основному контенту»), так что пункт о его отсутствии устарел. 【F:backend/apps/admin_ui/templates/base.html†L33-L36】
- Формы (`recruiters_new.html`, `candidates_new.html`) не имеют явных описаний ошибок и aria-live областей, fallback статический. 【F:backend/apps/admin_ui/templates/recruiters_new.html†L1-L160】
- Токены стеклянных поверхностей подключены (`tokens.css`), но не все компоненты используют blur/тени — требуется визуальный аудит и, возможно, внедрение Apple-like glass preset.
