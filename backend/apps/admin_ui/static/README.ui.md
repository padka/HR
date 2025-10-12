# UI layout quickstart

- `css/tokens.css` объявляет цветовые, типографические и теневые токены для светлой/тёмной темы. Переменные `--color-*` и `--shadow-*` используются поверх существующих `--ui-*` алиасов.
- `css/ui.css` содержит базовые примитивы интерфейса: кнопки, инпуты, панели, `.page-grid` и таблицы с прокруткой.
- `js/theme.js` синхронизирует `prefers-color-scheme`, обновляет `data-theme`/`data-density` и дружит с `window.TGTheme`.

## Layout helpers

- Страница состоит из `.page-grid` — два столбца (aside 300px + контент). На ширине <1024px aside переезжает наверх.
- Используйте `.page-aside.panel` для описаний и CTA, а `.page-main` — для основного контента.
- Таблицы: оборачивайте в `.panel.panel--compact` → `.table__wrap` → `<table class="table">`. Минимальные ширины колонок заданы через классы `.col-id`, `.col-name`, `.col-actions`.
- Фильтры и действия размещайте в `.toolbar` с зонами `.toolbar__primary` и `.toolbar__aside`; чипы сворачиваются в адаптивный ряд.

## Тестирование

1. Проверьте переключение темы/плотности (`[data-theme-toggle]`, `[data-density-toggle]`).
2. На узком экране таблицы должны прокручиваться внутри `.table__wrap`, а aside перемещается вверх.
