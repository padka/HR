# Проверка сериализации Jinja `|tojson`

## Результаты grep-аудита
```text
$ ./scripts/audit_tojson.sh
Searching |tojson usages...
backend/apps/admin_ui/templates/index.html:218:<script type="application/json" id="weekly_kpi_data">{{ weekly_kpis|tojson }}</script>
```

## Верификация контекста
- `backend/apps/admin_ui/templates/index.html` получает `weekly_kpis` из `backend.apps.admin_ui.services.kpis.get_weekly_kpis()`, который возвращает чистый `dict` без ORM-объектов.

## Статус тестов и проверок
- `pytest -q` — ❌ `ModuleNotFoundError: No module named 'uvloop'` (не установлен в среде). Требуется установить зависимость перед запуском.
- Playwright smoke и ручной UI-smoke не выполнялись в офлайн-окружении.
