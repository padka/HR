# Качество, DX и UX

## Код и стиль
- `pyproject.toml` не содержит базовых зависимостей (`dependencies = []`), вся логика держится на `requirements-dev.txt`. Это ломает воспроизводимость и `pip install .` (см. Phase 2). 【F:pyproject.toml†L19-L33】
- Конфиги black/isort/ruff присутствуют и согласованы через pre-commit, но mypy запускается в режиме `--strict`, что без типовых аннотаций вызывает флап в CI. 【F:.pre-commit-config.yaml†L1-L25】
- Tailwind конфиг расширен под Liquid Glass, однако шаблоны всё ещё используют смесь utility-классов и кастомных CSS, что подтверждается невысоким количеством уникальных селекторов в `METRICS.md`.

## Тесты и покрытие
- `pytest` завершается с 5 падениями: несовместимый `TestClient.request(... allow_redirects)` и отсутствие `playwright` браузеров блокируют pipeline. 【F:audit/pytest.log†L1-L116】
- Smoke без БД обрывается на `slot_reminder_jobs`, что означает отсутствие стабильного сценария bootstrap в тестах. 【F:audit/smoke_no_db.log†L1-L8】
- В workflow CI все проверки запускаются на трёх версиях Python, но требует `pre-commit` и `pytest --cov`; при текущих зависимостях это упадёт сразу на установке. 【F:.github/workflows/ci.yml†L1-L34】【F:requirements-dev.txt†L1-L21】

## DX
- Скриптов воспроизводимости нет: чтобы запустить проект, пришлось вручную устанавливать `apscheduler`, `python-multipart`, `alembic`, скачивать playwright-браузеры. Нужен `make bootstrap`/`poetry` профиль и README с шагами.
- `audit/run_smoke_checks.py` показал, что без прогрева БД даже health-check не стартует; добавьте `make dev-db` с миграциями и seed.

## A11y и UX
- В `base.html` отсутствует skip-link, навигация недоступна с клавиатуры на мобильной версии (бургер не переключает фокус). 【F:backend/apps/admin_ui/templates/base.html†L1-L120】
- Формы (`recruiters_new.html`, `candidates_new.html`) не имеют явных описаний ошибок и aria-live областей, fallback статический. 【F:backend/apps/admin_ui/templates/recruiters_new.html†L1-L160】
- Токены стеклянных поверхностей подключены (`tokens.css`), но не все компоненты используют blur/тени — требуется визуальный аудит и, возможно, внедрение Apple-like glass preset.
