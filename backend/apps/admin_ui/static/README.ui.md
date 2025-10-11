# UI foundation quickstart

- `css/tokens.css` объявляет базовые переменные и ui-* токены для цветовой палитры (SF Pro, Apple primary #0A84FF, dark background #0B1220).
- `css/ui.css` подключается после сборки и даёт базовые компоненты (`.btn`, `.input`, `.chip`, `.card`, `.table`, `.toolbar`, `.modal`).
- Размеры контролов регулируются через `data-density="compact|comfy"`, переключение хранится в `localStorage`.
- `js/theme.js` синхронизирует prefers-color-scheme, dataset `data-theme`, плотность и интегрируется с существующим `window.TGTheme`.
- Используйте токены `--ui-color-*`, `--ui-space-*`, `--ui-border` и класс `.card` для адаптации существующих шаблонов.
- Для таблиц прокидывайте `table_class='table ...'` в макросы, для фильтров оборачивайте в `<div class="toolbar">`.
- Новые состояния кнопок: добавляйте модификаторы `.btn--primary`, `.btn--ghost`, `.btn--danger`, размеры `.btn--sm|lg`.
- Формы и селекты: добавьте класс `.input` / `.select` или используйте `input-pill__control input`.

## Тестирование
1. Перезапустите сервер (`make ui` или `npm run dev` при необходимости).
2. Проверьте переключение темы и плотности на странице `/candidates`.
