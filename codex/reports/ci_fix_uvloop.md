## CI fix: uvloop optionality on Python 3.12

- **Проблема:** pytest падал с `ModuleNotFoundError: No module named 'uvloop'` при прогоне на Python 3.12.
- **Решение:** добавлена мягкая интеграция uvloop в `tests/conftest.py` и установка `uvloop` в CI с фолбэком на `asyncio.DefaultEventLoopPolicy()`.
- **Артефакты CI:** workflow сохраняет `playwright-report` и `pytest-report.txt` как артефакты для проверки результата.
