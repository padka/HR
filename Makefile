.PHONY: setup bootstrap doctor dev-db test ui demo previews screens kpi-weekly run lint pw-install pw-deps pw-setup

VENV ?= .venv
PYTHON ?= python3

setup: $(VENV)/bin/python
	. $(VENV)/bin/activate && python -m pip install --upgrade pip
	. $(VENV)/bin/activate && python -m pip install -e ".[dev]"
	npm install
	$(MAKE) doctor

pw-install: $(VENV)/bin/python
	. $(VENV)/bin/activate && playwright install chromium

pw-deps: $(VENV)/bin/python
	if [ "$(shell uname -s)" = "Linux" ]; then \
	        if ! (. $(VENV)/bin/activate && playwright install-deps chromium); then \
	                echo "Playwright Linux dependencies require administrator privileges. Re-run with sudo: playwright install-deps chromium"; \
	                exit 1; \
	        fi; \
	else \
	        echo "Skipping Playwright system dependency install (non-Linux host)"; \
	fi

pw-setup: pw-deps pw-install

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

ui: $(VENV)/bin/python
	npm run build:css
	. $(VENV)/bin/activate && python tools/report_css_size.py

demo: $(VENV)/bin/python
	. $(VENV)/bin/activate && uvicorn app_demo:app --reload

previews: $(VENV)/bin/python
	. $(VENV)/bin/activate && python tools/render_previews.py

screens: $(VENV)/bin/python
	if ! (. $(VENV)/bin/activate && playwright install --check chromium >/dev/null 2>&1); then \
	        $(MAKE) pw-setup; \
	fi
	rm -rf ui_screenshots
	. $(VENV)/bin/activate && pytest tests/test_ui_screenshots.py

kpi-weekly: $(VENV)/bin/python
	. $(VENV)/bin/activate && python tools/recompute_weekly_kpis.py --weeks 8
lint: $(VENV)/bin/python
	. $(VENV)/bin/activate && ruff check tests/test_ui_screenshots.py tools/report_css_size.py
	npm run lint:deps
	npm run lint:cssjs
