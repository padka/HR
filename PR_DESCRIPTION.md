# Liquid Glass UI Toolkit
## Summary
- Перенесена сборка CSS на `static/css/main.css` → `static/build/main.css`, обновлены токены и Tailwind для Apple Liquid Glass.
- Добавлены документы `docs/Audit.md` и `docs/DesignSystem.md` с анализом проблем и системой токенов.
- Реализован офлайн-демо `app_demo.py`, генератор превью и тест Playwright для автоскриншотов.
- Настроены Makefile-команды и GitHub Actions workflow для сборки CSS, превью и скриншотов.
## Rollout
1. Установить зависимости: `make setup` (Python dev extras + npm + playwright).
2. Собрать стили: `make ui` (генерирует `backend/apps/admin_ui/static/build/main.css`).
3. Запустить демо: `make demo` (FastAPI на http://127.0.0.1:8000).
4. Сгенерировать превью/скриншоты: `make previews` и `make screens`.
## Regression checklist
- [ ] Dashboard метрики и карточки отображаются со стеклянными слоями в обеих темах.
- [ ] Списки/таблицы имеют липкий заголовок, зебру и сортировку.
- [ ] Формы показывают акцентный focus, ошибки и переключатели тем.
- [ ] Модалки/тосты анимируются c cubic-bezier(0.16, 1, 0.3, 1).
- [ ] Генерация превью и скриншотов проходит без обращения к боевому бэкенду.
