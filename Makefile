.PHONY: install test ui codex setup bootstrap doctor dev-db demo previews screens kpi-weekly run

PYTHON ?= python3

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt
	npm ci

test:
	$(PYTHON) -m pytest

ui:
	npm run build

codex:
	bash scripts/codex.sh

# Legacy developer workflow targets kept for compatibility
setup: install
	$(PYTHON) -m pip install -e ".[dev]"
	$(PYTHON) -m playwright install
	$(MAKE) doctor

bootstrap: setup

doctor:
	$(PYTHON) scripts/dev_doctor.py

run:
	if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	$(PYTHON) -m uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000

dev-db:
	$(PYTHON) -c "import asyncio; from backend.core.bootstrap import ensure_database_ready; asyncio.run(ensure_database_ready())"

demo:
	$(PYTHON) -m uvicorn app_demo:app --reload

previews:
	$(PYTHON) tools/render_previews.py

screens:
	$(PYTHON) -m pytest tests/test_ui_screenshots.py

kpi-weekly:
	$(PYTHON) tools/recompute_weekly_kpis.py --weeks 8
