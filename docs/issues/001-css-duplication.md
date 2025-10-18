# Issue 001 — Дублирование CSS и конфликт тем

## Симптомы
`backend/apps/admin_ui/templates/base.html` подключает сразу три CSS-файла:
- `/static/css/tokens.css`
- `/static/build/main.css`
- `/static/css/ui.css`

`tokens.css` и `ui.css` содержат переменные и компоненты, которые уже попадают в Tailwind билд (`main.css`). Это приводит к конфликтам цветов (например, `--bg-base`) и увеличенному размеру страницы.

## Как воспроизвести
1. Открыть `/slots`.
2. Проверить вкладку Network в DevTools — три CSS-файла.
3. В Elements → Computed видно двойное объявление фонового цвета.

## Предлагаемое решение
- Мигрировать на Vite manifest-helper и загрузку одного бандла.
- Разделить стили на tokens/components/pages и подключать через JS.

## Ссылки
- `codex/tasks/sprint1_refactor.yaml` (шаг A1)
