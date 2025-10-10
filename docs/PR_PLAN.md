# Initial PR Plan (Phase C Kick-off)

## PR 1 — feature/ui-core-unify (Epic: UI Core Unification)
**Scope & Goals**
- Слить `base.html` и `base_liquid.html` в единый шаблон.
- Перенести токены в `tokens.css`, собрать `main.css` и удалить legacy CSS.
- Документировать утилиты `.glass`, `.badge-*`, `.pill`, `.surface`.

**Commit Flow**
1. `chore(styles): add liquid glass tokens registry`
2. `feat(ui-core): consolidate base layout and shared partials`
3. `refactor(styles): remove legacy liquid-dashboard and tahoe css`
4. `docs(ui): record base template migration notes`

**Verification Commands**
- `make setup`
- `make ui`
- `make init-db`
- `make run`
- `npm run build:css`

**Reviewer DoD Checklist**
- Бандл `static/build/main.css` gzip ≤70 KB; legacy CSS не подключается.
- Все страницы расширяют новый `base.html`, нет 500-ок при переходах.
- Liquid Glass утилиты задокументированы и используются компонентами.
- В `previews/` обновлены скриншоты Dashboard, Slots, Candidates (desktop/tablet).

## PR 2 — feature/slots-kpi-and-city-filter (Epic: Slots Experience Refresh)
**Scope & Goals**
- Вынести KPI карточки в частичный шаблон, применить Liquid Glass стили.
- Добавить фильтр по городам и улучшить таблицу (sticky header, zebra).
- Ускорить live-фильтрацию и API `/api/slots`.

**Commit Flow**
1. `feat(slots): introduce reusable slot kpi component`
2. `feat(slots): add city pill-filter and live toolbar state`
3. `style(slots): apply glass table visuals with sticky header`
4. `perf(slots): trim api payload and cache recruiter map`
5. `test(slots): capture playwright screenshots for slots views`

**Verification Commands**
- `make setup`
- `make ui`
- `make init-db`
- `make run`
- `npm run build:css`
- `npm run build:js`
- `make playwright` (или `pytest tests/ui/test_slots.py` при необходимости)

**Reviewer DoD Checklist**
- KPI карточки отображают WTD/WoW и корректно обновляются при смене фильтра.
- Фильтр по городам реагирует без перезагрузки и имеет активное состояние.
- Таблица поддерживает клавиатурную навигацию, sticky header работает в браузерах Chromium/Firefox.
- Рендер 200 строк ≤100 мс (замер в DevTools Performance).
- API `/api/slots` укладывается ≤200 мс на демо-данных.

## PR 3 — feature/candidates-interactive-v1 (Epic: Candidates v1 Interactive Table)
**Scope & Goals**
- Внедрить статусы-капсулы и inline-редактирование ключевых полей.
- Добавить стеклянный тулбар с фильтрами по городу, стадии и поиску.
- Обновить JS для идемпотентного сохранения inline-правок.

**Commit Flow**
1. `feat(candidates): add status capsules and inline actions`
2. `feat(candidates): implement toolbar filters and search debounce`
3. `style(candidates): align table with glass surfaces`
4. `test(candidates): extend playwright flows for inline editing`
5. `docs(candidates): describe interactive table ux patterns`

**Verification Commands**
- `make setup`
- `make ui`
- `make init-db`
- `make run`
- `npm run build:css`
- `npm run build:js`
- `make playwright`

**Reviewer DoD Checklist**
- Inline-редактирование (город, активность) работает без перезагрузки; ошибки показываются в `.badge-danger`.
- Фильтры/поиск сохраняют состояние при перезагрузке страницы (query params).
- Таблица рендерится ≤100 мс, API `/candidates` ≤200 мс.
- Playwright тесты покрывают happy-path + отмену правки.
- Скриншоты Candidates (desktop/tablet) обновлены и соответствуют Liquid Glass стилю.

