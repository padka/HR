## Контекст
После фикса ошибки сериализации на /slots необходимо подтвердить корректность передачи данных в остальные шаблоны и вернуть зелёные тесты/CI.

## Что сделать
1. Найти все использования `|tojson` в шаблонах (`backend/apps/admin_ui/templates/**`), убедиться, что в контекст передаются dict/Pydantic, а не ORM.
2. Где нужно — применить `fastapi.encoders.jsonable_encoder` в роутерах/сервисах до рендера.
3. Восстановить pytest:
   - добавить `tests/conftest.py` с `event_loop_policy()` на uvloop,
   - включить `asyncio_mode = auto` в pytest-конфиге.
4. Подготовить Playwright smoke (если используется) и установить браузеры в CI.
5. Обновить CI: build → playwright install → e2e (если есть) → pytest.
6. Ручной smoke UI: /slots, /candidates, /recruiters (скриншоты).
7. Отчёт с grep-результатами и статусом тестов: codex/reports/serialization_validation.md.

## Критерии приёмки
- Все шаблоны с `|tojson` рендерятся без 500.
- pytest и (если есть) Playwright проходят в CI.
- Скриншоты/логи приложены в отчёт.
