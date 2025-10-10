.PHONY: setup ui demo previews screens

setup:
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
npm install
playwright install

ui:
npm run build:css

demo:
uvicorn app_demo:app --reload

previews:
python tools/render_previews.py

screens:
pytest tests/test_ui_screenshots.py
