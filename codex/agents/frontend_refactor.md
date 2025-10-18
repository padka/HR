# Агент Frontend Refactorer

## Цель
Перевести админку на Vite + PostCSS + Tailwind JIT, разделить стили по слоям (tokens/components/pages), внедрить UI-core (modal, sheet, toast, focus-trap) и избавиться от inline-скриптов.

## Контекст
- Исходные CSS: `backend/apps/admin_ui/static/css/{tokens.css,main.css,ui.css}`.
- Сборка сейчас выполняется Tailwind CLI → `static/build/main.css`; подключение в `templates/base.html`.
- Inline-скрипты в `templates/base.html` (настройка темы и topbar) и `slots_list.html` (sheet, фильтры).
- JS-модули страниц находятся в `static/js/modules/` и импортируются напрямую через `/static/...`.

## Основные задачи
1. **Vite bootstrap**
   - Создать `frontend/` с Vite config (mode `admin`), настроить `@vite/client` для dev и `manifest.json` для prod.
   - Подключить PostCSS (`postcss.config.cjs`) и Tailwind (`tailwind.config.js`) из корня.
   - Настроить alias на `@ui` → `./frontend/ui` для компонентов.
2. **Разделение стилей**
   - Вынести дизайн-токены в `frontend/styles/tokens.css` (из текущего `tokens.css`).
   - Создать `frontend/styles/components.css` для UI-core и `frontend/styles/pages/*.css` для экранов.
   - Очистить `tailwind.config.js` от лишних путей после миграции (использовать Vite glob import).
3. **UI-core**
   - Скелет модалки/шита/тоста/фокус-трапа в `frontend/ui/core/`.
   - Подготовить `createFocusTrap`, `presentSheet`, `showToast`, `modalController` с событиями CustomEvent.
   - В шаблонах использовать хелперы макросов (обновить `page_primitives.html`).
4. **Manifest helper**
   - Добавить Jinja-хелпер `vite_asset()` с кэшем манифеста, хранить в `backend/apps/admin_ui/utils.py` или отдельном модуле.
   - Обновить `base.html` и страницы для подключения ассетов через `{% vite_asset 'admin.ts' %}`.
5. **Удаление inline-скриптов**
   - Перенести topbar и тему в Vite entrypoints (`frontend/entries/app.ts`).
   - Вынести `slots_list.html`-скрипты в отдельный модуль (`frontend/entries/slots.ts`).
6. **Smoke-проверка**
   - После миграции выполнить `npm run dev` + `uvicorn ...` и пройти `/slots` (открытие фильтров, таблица, модалки) вручную.

## Требования к результату
- Vite манифест кладётся в `backend/apps/admin_ui/static/build/manifest.json` (генерация), но в git не коммитится.
- В `codex/context/decisions.log.md` фиксируем решения об архитектуре UI-core.
- Структура стилей документируется в `codex/context/guide_full.md`.
- Все ассеты проходят через Vite, линтеры и тесты (`npm run lint`, `npm run test`) добавляются в CI.
