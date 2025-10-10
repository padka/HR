# Liquid Glass PR Checklist

## Summary
- Кратко опишите, что меняется (2–3 буллета).
- Укажите, какие экраны или сервисы затронуты.

## Rollout
1. `make setup`
2. `make ui`
3. `make init-db`
4. `make run`
5. `make screens`

## Visual QA Checklist
- [ ] Нет 500-ок на свежей БД (дым-тесты `/`, `/slots`, `/candidates`, `/recruiters`, `/cities`, `/templates`).
- [ ] Артефакты `previews/` и `ui_screenshots/` приложены к сборке.
- [ ] `audit/CSS_SIZE.md` в бюджете (≤ 90 KB raw, ≤ 70 KB gzip) или добавлен комментарий с WARN.
- [ ] Видимый фокус и контраст (WCAG AA) на новых/изменённых интерактивах.
- [ ] Скриншоты не отличаются более чем на 2 px diff (если сравнение включено).

## Regression Checklist (по необходимости)
- [ ] Линтеры (`make lint`, `npm run lint:deps`) зелёные.
- [ ] `make previews` и `make screens` проходят локально.
- [ ] Обновлённые миграции отсутствуют или описаны в rollout-плане.
