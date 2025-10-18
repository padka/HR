# Codex: Smart Service HR Admin

## Назначение продукта
Панель управления Smart Service HR обслуживает массовый рекрутинг: обработка откликов, назначения слотов интервью, контроль очередей и операционные действия (ОД) рекрутёров. Интерфейс ориентирован на сотрудников колл-центров и руководителей, позволяет видеть статусы кандидатов, квоты по городам и управлять шаблонами коммуникации.

## Архитектура и основные модули
- **Бэкенд:** FastAPI-приложение `backend.apps.admin_ui.app:app` с шаблонами Jinja2 и асинхронным доступом к БД через SQLAlchemy. Статические файлы монтируются через `StaticFiles` по пути `/static` (см. `backend/apps/admin_ui/app.py`).
- **Шаблоны:** располагаются в `backend/apps/admin_ui/templates/`. Ключевые экраны — `index.html`, `slots_list.html`, `candidates_list.html`, `recruiters_list.html`, `cities_list.html`, `templates_list.html`.
- **Статика:** CSS/JS хранится в `backend/apps/admin_ui/static/`. Текущая сборка — Tailwind CLI (`package.json` → `npm run build`), выходной файл `static/build/main.css`. Дополнительные слои — `static/css/tokens.css`, `static/css/ui.css`, а также модули JS в `static/js/modules/`.
- **Роуты админки:** определены в `backend/apps/admin_ui/routers/`. Основные сегменты: `/slots`, `/candidates`, `/recruiters`, `/cities`, `/templates`, `/questions`, `/system`, `/api`.
- **Принципы ТЗ:** интерфейс разделяет действия рекрутёра (назначение/подтверждение слотов, смена статусов) и кандидата (профиль, ответы бота). Все изменения должны логироваться и быть доступны в аналитике KPI.

## Команды запуска и сборки
```bash
# Бэкенд (FastAPI)
uvicorn backend.apps.admin_ui.app:app --reload --port 8000

# Генерация CSS через Tailwind CLI
npm install
npm run build

# Тесты Python
pytest
```
Дополнительно доступны make-таргеты (`make bootstrap`, `make dev-db`, `make test`) из README.md.

## Локальный запуск
1. **Создайте виртуальное окружение:** `python3 -m venv .venv && source .venv/bin/activate` (Python ≥3.11).
2. **Установите зависимости:** `pip install -r requirements.txt -r requirements-dev.txt`.
3. **Поставьте frontend-пакеты:** `npm install` (или `npm ci` для чистой среды).
4. **Скопируйте конфиг:** `cp .env.example .env` и заполните минимум `ADMIN_USER`, `ADMIN_PASSWORD`, `SESSION_SECRET_KEY` (≥32 символов).
5. **Соберите Tailwind:** `npm run build` — сформирует `backend/apps/admin_ui/static/build/main.css`.
6. **Запустите FastAPI:** `ADMIN_USER=... ADMIN_PASSWORD=... SESSION_SECRET_KEY=... uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000`.
7. **Проверьте здоровье:** `curl http://127.0.0.1:8000/health` (ожидаемый JSON статус `ok`).
8. **Запустите тесты (опционально):** `pytest -q`. На текущем состоянии часть async-тестов падает из-за политики uvloop, Playwright-сценарии требуют предварительного `npx playwright install --with-deps`.

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
Первый прогон создаёт базовые снимки через `npm run test:e2e:update`. Обычный запуск `npm run test:e2e` падает при любом визуальном расхождении. Снимки хранятся рядом с тестами в папках `__snapshots__`.
