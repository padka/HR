from __future__ import annotations

import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.sync_api import Error, sync_playwright

from app_demo import DEMO_ROUTES, app


@pytest.fixture(scope="session", autouse=True)
def configure_backend():
    """Override heavy backend fixture from the main test suite."""
    yield


@pytest.fixture(autouse=True)
def clean_database():
    yield

TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_PORT = 8055
BASE_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}"
SCREEN_DIR = Path("ui_screenshots")
SCREEN_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def demo_server() -> str:
    config = uvicorn.Config(app, host=TEST_SERVER_HOST, port=TEST_SERVER_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            response = httpx.get(BASE_URL)
            if response.status_code < 500:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:  # pragma: no cover - timeout
        raise RuntimeError("demo server failed to start")

    yield BASE_URL

    server.should_exit = True
    thread.join(timeout=5)


def _slug(path: str, fallback: str) -> str:
    slug = path.strip("/").replace("/", "-")
    return slug or fallback


def test_ui_screenshots(demo_server: str) -> None:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Error as exc:
            if "missing dependencies" in str(exc):
                pytest.skip("Playwright browser dependencies are not available in the CI image")
            raise
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        for route in DEMO_ROUTES:
            url = f"{demo_server}{route.path}"
            page.goto(url)
            page.wait_for_load_state("networkidle")
            slug = _slug(route.path, route.slug)
            screenshot_path = SCREEN_DIR / f"{slug}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()
