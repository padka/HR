.PHONY: setup ui demo previews screens dev-db smoke

setup:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"
	npm install
	python -m playwright install --with-deps

smoke:
	python audit/run_smoke_checks.py --with-db

ui:
	npm run build:css

demo:
	uvicorn app_demo:app --reload

previews:
	python tools/render_previews.py

screens:
	pytest tests/test_ui_screenshots.py

dev-db:
	python audit/run_smoke_checks.py --with-db
