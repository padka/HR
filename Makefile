.PHONY: setup bootstrap dev-db test ui demo previews screens

setup: bootstrap

bootstrap:
	python -m pip install --upgrade pip
	@if command -v poetry >/dev/null 2>&1; then \
		poetry install --with dev; \
	else \
		python -m pip install -e ".[dev]"; \
	fi
	npm install
	playwright install

dev-db:
	python - <<'PY'
import asyncio
from backend.core.bootstrap import ensure_database_ready

asyncio.run(ensure_database_ready())
PY

test: dev-db
	pytest

ui:
	npm run build:css

demo:
	uvicorn app_demo:app --reload

previews:
	python tools/render_previews.py

screens:
	pytest tests/test_ui_screenshots.py
