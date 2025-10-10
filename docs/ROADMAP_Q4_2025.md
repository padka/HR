# Q4 2025 Roadmap

## Executive Overview
- Сфокусироваться на очистке UI-ядра и зависимостей, чтобы исключить дубли CSS/JS и устранить конфликт требований Python.
- Перестроить ключевые экраны (Слоты, Кандидаты, Рекрутёры, Города, Шаблоны) вокруг Liquid Glass-токенов и единых UX-паттернов.
- Обновить Dashboard с KPI-трендами и стеклянным календарём, чтобы подчеркнуть оперативный контекст.
- Ввести управляемую историю статусов и триггеры напоминаний для Кандидатов, сохранив идемпотентность Telegram.
- Усилить QA/CI: Playwright-скриншоты, UI-превью, регламенты по линтерам и перформанс-бюджетам.

## Epic Prioritisation (ICE)
| Epic | Problem (из аудита) | Proposed Fix | Impact | Confidence | Effort | ICE |
| --- | --- | --- | --- | --- | --- | --- |
| DX/Dependencies Alignment | dev_doctor требует Python 3.13, дубли prod/dev зависимостей, нефиксированные версии JS | Синхронизировать версии Python=3.12, выровнять pyproject/requirements, зафиксировать npm/pip lockfiles, обновить dev_doctor | 8 | 7 | 3 | 18.7 |
| QA/CI Visual Guardrails | Нет автоматических скриншотов UI и линтеров, слабая защита от регрессий | Настроить Playwright для desktop/tablet/phone, добавить линтеры в CI, хранить превью | 8 | 7 | 3 | 18.7 |
| UI Core Unification | Несколько шаблонов (`base.html`, `base_liquid.html`), дубли CSS (`liquid-dashboard*.css`, `tahoe.css`, `cards.css`) | Ввести единый `base.html`, консолидировать токены в `tokens.css`, собрать один `static/build/main.css` | 9 | 7 | 4 | 15.8 |
| Slots Experience Refresh | KPI и фильтры перегружены и не читаемы, нет фильтра по городам | Переверстать KPI карточки, добавить фильтр по городам, sticky header и зебра-строки | 8 | 7 | 5 | 11.2 |
| Dashboard & KPI Panels | «Герой» перегружен, KPI и календарь без контраста | Создать стеклянный герой-блок, weekly KPI WTD + тренд, компактный календарь в `.glass` | 7 | 6 | 4 | 10.5 |
| Recruiters Grid | Карточки перегружены текстом, нет плиточного выбора городов | Сформировать сетку с `.glass` контейнерами, плиточный селектор городов, ясные бейджи статусов | 6 | 7 | 4 | 10.5 |
| Candidates v1 Interactive Table | Таблица перегружена, нет inline-редактирования и видимых фильтров | Добавить статусы-капсулы, inline-редактирование ключевых полей, фильтры по городам/стадиям | 9 | 6 | 6 | 9.0 |
| Cities Minimal Editor | Таблица и редактор шумные, нет быстрых фильтров | Развести таблицу и редактор, добавить плитку рекрутёров, сделать формы минималистичными | 6 | 6 | 4 | 9.0 |
| Templates & Tests Authoring | Редактор без превью, нет подсветки ошибок, дубли ошибок | Сделать редактор с вкладками Edit/Preview, валидатор JSON, бейджи ошибок | 7 | 6 | 5 | 8.4 |
| Candidates v2 Status Engine | Статусы вычисляются на лету, нет истории и идемпотентности | Ввести `candidate_status_history`, T-2h напоминания, идемпотентный outbox | 8 | 5 | 7 | 5.7 |

## Definition of Done по эпику
### DX/Dependencies Alignment
- dev_doctor, Makefile и документация требуют Python 3.12.x; CI матрица включает 3.12 и nightly smoke.
- requirements и optional-dev синхронизированы с pyproject; удалены дубли, pip-compile lockfile приложен.
- npm lockfile обновлён и зафиксирован; `npm ci` и `pip install -e .[dev]` проходят на чистой машине.
- `make doctor`, `make setup`, `make ui`, `make lint`, `make test` завершаются без WARN/FAIL.
- На пустой БД все веб-страницы отвечают без 500-ок.

### QA/CI Visual Guardrails
- Playwright сценарии создают скриншоты desktop/tablet/phone для Dashboard, Slots, Candidates, Recruiters, Cities, Templates.
- Скриншоты публикуются как артефакты CI; порог регрессий ≤2 px diff (pixelmatch).
- Линтеры Ruff/Black/mypy/Tailwind `--minify` подключены в CI, build времени ≤5 мин.
- Для ключевых страниц измерен TTI (LightHouse или WebPageTest) ≤2.5 c на демо-данных.
- Отчёт о визуальных регрессиях хранится в `previews/` и обновляется PR.

### UI Core Unification
- Один `backend/apps/admin_ui/templates/base.html`; все страницы расширяют его.
- `tokens.css` содержит единственный источник токенов (цвета, радиусы, тени, типографику) и импортируется в `main.css`.
- `static/build/main.css` gzip ≤ 70 KB; legacy `liquid-dashboard*.css`, `tahoe.css`, `cards.css`, `forms.css`, `lists.css` удалены/инлайнены.
- Утилиты `.glass`, `.badge-*`, `.pill`, `.surface` документированы и покрывают ≥90% компонентов.
- Снимки UI (до/после) для Dashboard, Slots, Candidates показывают отсутствия визуальных артефактов.

### Slots Experience Refresh
- Верхние KPI карточки используют токены (`--color-accent-*`), показывают WTD/WoW и живут в `components/slot-kpi.html`.
- Таблица имеет sticky header и zebra striping, рендер 200 строк ≤100 мс.
- Фильтры по городам/рекрутёрам/статусам работают без перезагрузки (JS live filter) и показывают активное состояние.
- Переходы hover/focus имеют контраст ≥ WCAG AA; клавиатурная навигация покрывает фильтры и таблицу.
- API-ответы `/api/slots` ≤200 мс на демо-данных.

### Dashboard & KPI Panels
- Герой-блок использует `.glass` контейнер, содержит KPI snapshot и CTA ≤3 штук.
- Weekly KPI карточки показывают WTD, тренд (стрелка/мини-спарклайн) и цветовой код.
- Календарь встроен в стеклянную панель с фиксированным фильтром по дате.
- Dashboard загружается ≤2.0 c TTI, Lighthouse Performance ≥85.
- Состояние Telegram бота отображается компактным статус-бейджем.

### Recruiters Grid
- Сетка карточек адаптивна (≥3 колонки desktop, 2 tablet, 1 mobile) и использует `.glass` и `.badge-status`.
- Плиточный выбор городов доступен и при смене фильтра обновляет список без полной перезагрузки.
- Карточки содержат ключевые CTA (контакт, активность) с клавиатурным фокусом.
- Сборка рендерит 100 рекрутёров ≤120 мс на демо-данных.
- Скриншоты UI подтверждают визуальное соответствие макету Liquid Glass.

### Candidates v1 Interactive Table
- Таблица имеет статусы-капсулы (цвет + иконка), inline toggle активности, inline выбор города/стадии.
- Фильтры по городу, стадии и поиску отображены в верхней панели и работают без перезагрузки.
- 200 строк рендерятся ≤100 мс, API `/candidates` отвечает ≤200 мс.
- А11y: все интерактивные элементы доступны с клавиатуры и имеют aria-label.
- Сняты визуальные тесты (desktop/tablet) до/после.

### Cities Minimal Editor
- Таблица и редактор разделены: таблица в левом `.glass` блоке, редактор в правом слайдере.
- Фильтр по ответственным рекрутёрам и статусу активен и сохраняет состояние в URL.
- Формы используют токены типографики, placeholder и helper-тексты очищены.
- Создание/редактирование города ≤3 клика; рендер списка ≤100 мс.
- Нет 500-ок при пустом списке городов.

### Templates & Tests Authoring
- Редактор шаблонов — вкладки Edit/Preview; превью обновляется без перезагрузки.
- JSON вопросов валидируется, ошибки выводятся в `.badge-danger` с подсветкой строки.
- Цветовые бейджи различают глобальные и городские шаблоны.
- Сохранение срабатывает идемпотентно; не возникает дублирующих запросов в сеть.
- e2e сценарии покрывают создание/редактирование/откат изменений.

### Candidates v2 Status Engine
- Добавлена таблица `candidate_status_history` (только CREATE/ADD миграции).
- Напоминание T-2h и Test-2/soft decline используют идемпотентный ключ (slot_id + trigger).
- Outbox имеет дедупликацию и retry-метрики; мониторинг логирует статусы отправок.
- UI показывает журнал статусов в карточке кандидата.
- Метрики: 0 повторных уведомлений по одному событию, 0 пропущенных напоминаний на демо-данных.

## Delivery Cadence & PR Order
1. **feature/ui-core-unify** — закрыть эпик UI Core Unification и подготовить токены/базовый шаблон.
2. **feature/slots-kpi-and-city-filter** — реализовать KPI карточки, фильтры и таблицу из эпику Slots Experience Refresh.
3. **feature/candidates-interactive-v1** — применить интерактивную таблицу кандидатов (эпик Candidates v1).
4. **feature/dashboard-liquid-refresh** — Dashboard & KPI Panels.
5. **feature/recruiters-glass-grid** — Recruiters Grid.
6. **feature/cities-minimal-editor** — Cities Minimal Editor.
7. **feature/templates-authoring** — Templates & Tests Authoring.
8. **feature/qa-visual-guardrails** — QA/CI Visual Guardrails.
9. **feature/candidates-status-engine** — Candidates v2 Status Engine.
10. **feature/dx-deps-alignment** — DX/Dependencies Alignment (частично стартовать параллельно в Sprint 0).

## Risk Mitigation & Rollback
- CSS/темы: внедрить `body`-класс `theme-liquid`; подключить legacy стили под `body.theme-legacy` и переключатель в `.env`/feature flag для быстрого отката.
- Telegram: все отправки проходят через outbox с идемпотентным ключом (candidate_id + trigger); предусмотреть ручной `RESEND` флаг и мониторинг.
- Миграции: только `CREATE TABLE`/`ADD COLUMN`, alembic `autogenerate` запрещён; перед мерджем freeze head -> tag `db-schema-v{date}`.
- QA: визуальные регрессии и метрики производительности хранятся в `previews/`; при сбое можно переключиться на предыдущий build артефакта.

## Timeline & Progress Metrics
| Milestone | Недели | Фокус | Контрольные метрики |
| --- | --- | --- | --- |
| **M1 – Foundation** | W1–W4 | DX/Deps Alignment, UI Core Unification, QA baseline | CSS bundle ≤90 KB (перед оптимизацией), `make doctor` без FAIL, 0 500-ок на smoke, ≥6 Playwright baseline скриншотов |
| **M2 – Experience** | W5–W8 | Slots, Dashboard, Recruiters, Cities | CSS bundle ≤70 KB gzip, Slots/Candidates таблицы ≤100 мс рендер, KPI API ≤200 мс, Lighthouse ≥85 |
| **M3 – Automations** | W9–W12 | Templates Authoring, Candidates v1/v2, QA расширение | 100% критических экранов в визуальных тестах, 0 повторных Telegram-уведомлений, 0 падений миграций, TTI Dashboard ≤2.0 с |

Еженедельные метрики: размер `main.css` (gzip), TTI Dashboard/Slots/Candidates, доля обновлённых Playwright скриншотов, количество 500-ок, среднее время ответа `/api/slots`, `/api/candidates`.

