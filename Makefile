.PHONY: setup bootstrap doctor dev-db test ui demo previews screens kpi-weekly run

VENV ?= .venv
PYTHON ?= python3

setup: $(VENV)/bin/python
	. $(VENV)/bin/activate && python -m pip install --upgrade pip
	. $(VENV)/bin/activate && python -m pip install -e ".[dev]"
	npm install
	. $(VENV)/bin/activate && playwright install
	$(MAKE) doctor

bootstrap: setup

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

doctor: $(VENV)/bin/python
	. $(VENV)/bin/activate && python scripts/dev_doctor.py

run: $(VENV)/bin/python
	. $(VENV)/bin/activate && \
	if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000

dev-db: $(VENV)/bin/python
	. $(VENV)/bin/activate && python -c "import asyncio; from backend.core.bootstrap import ensure_database_ready; asyncio.run(ensure_database_ready())"

test: dev-db
	. $(VENV)/bin/activate && pytest

ui:
	npm run build:css

demo: $(VENV)/bin/python
	. $(VENV)/bin/activate && uvicorn app_demo:app --reload

previews: $(VENV)/bin/python
	. $(VENV)/bin/activate && python tools/render_previews.py

screens: $(VENV)/bin/python
	. $(VENV)/bin/activate && pytest tests/test_ui_screenshots.py

kpi-weekly: $(VENV)/bin/python
	. $(VENV)/bin/activate && python tools/recompute_weekly_kpis.py --weeks 8
