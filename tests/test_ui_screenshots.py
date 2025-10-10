from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.sync_api import Error, Page, sync_playwright

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

DEFAULT_VIEWPORTS = [(None, {"width": 1440, "height": 900})]
CITY_VIEWPORTS = [
    ("desktop", {"width": 1440, "height": 900}),
    ("tablet", {"width": 1024, "height": 768}),
    ("mobile", {"width": 414, "height": 896}),
]
SPECIAL_VIEWPORTS = {
    "cities": CITY_VIEWPORTS,
    "city-edit": CITY_VIEWPORTS,
}


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


@contextmanager
def _launch_browser():
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Error as exc:
            if "missing dependencies" in str(exc):
                pytest.skip("Playwright browser dependencies are not available in the CI image")
            raise
        try:
            yield browser
        finally:
            browser.close()


def _wait_for_city_table_render(page: Page, expected: int) -> None:
    page.wait_for_function(
        "(expected) => document.querySelector('[data-cities-table] tbody').children.length === expected",
        arg=expected,
    )


def test_ui_screenshots(demo_server: str) -> None:
    with _launch_browser() as browser:
        for route in DEMO_ROUTES:
            viewports = SPECIAL_VIEWPORTS.get(route.slug, DEFAULT_VIEWPORTS)
            for label, viewport in viewports:
                page = browser.new_page(viewport=viewport)
                try:
                    page.goto(f"{demo_server}{route.path}")
                    page.wait_for_load_state("networkidle")
                    slug = _slug(route.path, route.slug)
                    suffix = f"--{label}" if label else ""
                    screenshot_path = SCREEN_DIR / f"{slug}{suffix}.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                finally:
                    page.close()


def test_cities_table_interactions(demo_server: str) -> None:
    with _launch_browser() as browser:
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{demo_server}/cities")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector('[data-city-row]')
        initial_count = int(page.locator('[data-visible-count]').inner_text())
        assert initial_count >= 180
        _wait_for_city_table_render(page, expected=initial_count)

        page.click('[data-cities-filter="assigned"]')
        page.wait_for_function(
            "() => Number(document.querySelector('[data-visible-count]').textContent) === 1"
        )
        page.click('[data-cities-filter="all"]')
        page.wait_for_function(
            "(expected) => Number(document.querySelector('[data-visible-count]').textContent) === expected",
            arg=initial_count,
        )

        page.click('[data-density-option="compact"]')
        page.wait_for_function(
            "() => document.querySelector('[data-cities-table]').dataset.density === 'compact'"
        )

        page.fill('[data-cities-search]', 'моск')
        page.wait_for_function(
            "() => Number(document.querySelector('[data-visible-count]').textContent) === 1"
        )
        _wait_for_city_table_render(page, expected=1)
        assert page.locator('[data-clear-search]').is_visible()

        page.locator('[data-city-row]').first.focus()
        page.keyboard.press('Enter')
        page.wait_for_url(f"{demo_server}/cities/1/edit")


def test_city_editor_interactions(demo_server: str) -> None:
    with _launch_browser() as browser:
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(f"{demo_server}/cities/1/edit")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector('#city_form')

        page.fill('#city_name', 'Екатеринбург')
        page.fill('#city_tz', 'Asia/Yekaterinburg')
        page.wait_for_function(
            "() => document.querySelector('[data-city-chip]').textContent.includes('Екатеринбург · Asia/Yekaterinburg')"
        )

        page.click('#city_active')
        page.wait_for_function(
            "() => document.querySelector('[data-active-label]').textContent.includes('Выключен')"
        )

        page.fill('[data-stage-input="stage1_invite"]', 'Кастомный текст')
        page.click('[data-stage-default="stage1_invite"]')
        page.wait_for_function(
            "() => document.querySelector('[data-stage-item=\\'stage1_invite\\'] textarea').value.length > 0"
        )

        dialog_handled = {}

        def _handle_dialog(dialog) -> None:
            dialog_handled['seen'] = True
            dialog.accept()

        page.on('dialog', _handle_dialog)
        page.click('[data-cancel]')
        page.wait_for_url(f"{demo_server}/cities")
        assert dialog_handled.get('seen', False)
