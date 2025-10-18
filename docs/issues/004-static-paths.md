# Issue 004 — Жёсткие пути /static в шаблонах

## Симптомы
Шаблоны используют абсолютные пути `/static/...` вместо `url_for` или manifest-helper:
- `backend/apps/admin_ui/templates/candidates_list.html` (стр. 187)
- `backend/apps/admin_ui/templates/recruiters_list.html` (стр. 170)
- `backend/apps/admin_ui/templates/templates_edit.html` (стр. 124)
- `backend/apps/admin_ui/templates/cities_new.html` (стр. 58)

При развёртывании за обратным прокси или с префиксом (`/admin`) ассеты не находятся, UI ломается.

## Как воспроизвести
1. Запустить приложение под префиксом (`root_path='/admin'`).
2. Открыть `/admin/candidates` — Network выдаёт 404 для `/static/js/...`.

## Предлагаемое решение
- После миграции на Vite использовать `{% vite_asset 'entries/candidates.ts' %}`.
- Для серверных страниц на Tailwind CLI временно использовать `url_for('static', path=...)`.

## Ссылки
- `codex/context/audit.md` — раздел «Маппинг статических путей».
