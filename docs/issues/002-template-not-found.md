# Issue 002 — TemplateNotFound на /questions/{id}/edit

## Симптомы
При переходе на страницу редактирования вопроса через `/questions/{question_id}/edit` сервер возвращает 500 с ошибкой `TemplateNotFound: questions_edit.html`. Ошибка воспроизводится на стенде, где шаблоны собираются отдельным образом (контейнер `app_demo`).

Причина — приложение `app_demo.py` не регистрирует шаблонные глобалы и использует отдельный `Jinja2Templates`. При сборке контейнера папка `backend/apps/admin_ui/templates` не копируется полностью (отсутствуют `questions_edit.html`, `partials/form_shell.html`).

## Как воспроизвести
1. Собрать контейнер `app_demo` из корня проекта (`docker build -f admin.Dockerfile` — текущая инструкция).
2. Запустить контейнер и открыть `/questions/1/edit`.
3. В логах увидеть `jinja2.exceptions.TemplateNotFound: questions_edit.html`.

## Ожидаемое поведение
Страница должна открываться и отображать форму редактирования вопроса.

## Предлагаемое решение
- Обновить Dockerfile/compose чтобы копировались все шаблоны.
- Удалить дублирующий `app_demo` или использовать основную фабрику `backend.apps.admin_ui.app:app`.
- Добавить тест `pytest` с загрузкой `/questions/1/edit`.

## Ссылки
- `codex/context/audit.md` — раздел «Проблемы и риски».
