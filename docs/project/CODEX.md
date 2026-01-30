# Codex: Smart Service HR Admin

## Назначение продукта
Панель управления Smart Service HR обслуживает массовый рекрутинг: обработка откликов, назначения слотов интервью, контроль очередей и операционные действия (ОД) рекрутёров. Интерфейс ориентирован на сотрудников колл-центров и руководителей, позволяет видеть статусы кандидатов, квоты по городам и управлять шаблонами коммуникации.

## Архитектура и основные модули
- **Бэкенд:** FastAPI-приложение `backend.apps.admin_ui.app:app` с асинхронным доступом к БД через SQLAlchemy. SPA-бандл монтируется под `/app/*` (см. `backend/apps/admin_ui/app.py`).
- **Шаблоны:** legacy Jinja удалены, оставлены только публичные страницы `test2_public.html` / `test2_public_result.html`.
- **Frontend (SPA):** React + TypeScript в `frontend/app/`, сборка Vite → `frontend/dist/`.
- **Роуты админки:** определены в `backend/apps/admin_ui/routers/`. Основные сегменты: `/slots`, `/candidates`, `/recruiters`, `/cities`, `/templates`, `/questions`, `/system`, `/api`.
- **Принципы ТЗ:** интерфейс разделяет действия рекрутёра (назначение/подтверждение слотов, смена статусов) и кандидата (профиль, ответы бота). Все изменения должны логироваться и быть доступны в аналитике KPI.

## Команды запуска и сборки
```bash
# Бэкенд (FastAPI)
uvicorn backend.apps.admin_ui.app:app --reload --port 8000

# Сборка SPA
npm --prefix frontend/app install
npm --prefix frontend/app run build

# Тесты Python
pytest
```
Дополнительно доступны make-таргеты (`make bootstrap`, `make dev-db`, `make test`) из README.md.

## Локальный запуск
1. **Создайте виртуальное окружение:** `python3 -m venv .venv && source .venv/bin/activate` (Python ≥3.11).
2. **Установите зависимости:** `pip install -r requirements.txt -r requirements-dev.txt`.
3. **Поставьте frontend-пакеты:** `npm --prefix frontend/app install`.
4. **Скопируйте конфиг:** `cp .env.example .env` и заполните минимум `ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET_KEY` (≥32 символов).
5. **Соберите SPA:** `npm --prefix frontend/app run build` — сформирует `frontend/dist/`.
6. **Запустите FastAPI:** `ADMIN_USER=... ADMIN_PASSWORD=... SESSION_SECRET_KEY=... uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000`.
7. **Проверьте здоровье:** `curl http://127.0.0.1:8000/health` (ожидаемый JSON статус `ok`).
8. **Запустите тесты (опционально):** `pytest -q`. Playwright-e2e запускаются из `frontend/app` (`npm --prefix frontend/app run test:e2e`).

## Сериализация для `|tojson`
При использовании фильтра Jinja `|tojson` в шаблонах передавайте сериализуемые
структуры (`dict`, `list`, Pydantic-модели). Если источник данных — ORM-слой,
преобразуйте его через `fastapi.encoders.jsonable_encoder` в роутере или
сервисе до передачи в контекст шаблона.

## Правила PR и работы с репозиторием
- Ветки: `main` (стабильная), `develop` (интеграция), `feature/*` (задачи).
- Коммиты: Conventional Commits (`feat|fix|chore|docs(scope): message`).
- PR должен включать чеклист DoD: линтеры/тесты зелёные, статические ассеты собираются через Vite (после миграции), отсутствуют inline-стили и `<script>` без бандла, UI проверен на ключевых сценариях.
- Для визуальных изменений прикладываем скриншоты и результаты axe-проверки.

## Где читать дальше
1. `codex/bootstrap.md` — карта проекта и быстрый старт.
2. `codex/guidelines.md` — соглашения по коду, процессам и DoD.
3. `codex/context/guide_full.md` — полный гайд по продукту, архитектуре и CI/CD.

## Визуальные тесты (Playwright)
E2E живёт в `frontend/app/tests/e2e` и запускается через `npm --prefix frontend/app run test:e2e`. Снимки хранятся рядом с тестами в папках `__snapshots__`.
