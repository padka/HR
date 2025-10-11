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

THEMES = ("light", "dark")
VIEWPORTS = (
    ("desktop", {"width": 1440, "height": 900}),
    ("tablet", {"width": 1024, "height": 768}),
    ("mobile", {"width": 390, "height": 844}),
)


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


def _launch_browser():
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch()
    except Error as exc:
        playwright.stop()
        if "missing dependencies" in str(exc):
            pytest.skip("Playwright browser dependencies are not available in the CI image")
        raise
    return playwright, browser


def _close_browser(playwright, browser) -> None:
    browser.close()
    playwright.stop()


def test_ui_screenshots(demo_server: str) -> None:
    playwright, browser = _launch_browser()
    try:
        for theme in THEMES:
            for viewport_slug, viewport in VIEWPORTS:
                page = browser.new_page(viewport=viewport)
                page.add_init_script(
                    f"try {{ localStorage.setItem('tg-admin-theme', '{theme}'); }} catch (e) {{}}"
                )
                page.emulate_media(color_scheme=theme)
                for route in DEMO_ROUTES:
                    url = f"{demo_server}{route.path}"
                    page.goto(url)
                    page.wait_for_load_state("networkidle")
                    slug = _slug(route.path, route.slug)
                    screenshot_path = SCREEN_DIR / f"{slug}__{viewport_slug}__{theme}.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                page.close()
    finally:
        _close_browser(playwright, browser)


def test_theme_preference_persists(demo_server: str) -> None:
    playwright, browser = _launch_browser()
    context = browser.new_context()
    page = context.new_page()
    page.emulate_media(color_scheme="light")
    try:
        page.goto(f"{demo_server}/")
        page.wait_for_load_state("networkidle")
        page.evaluate("window.localStorage.clear()")

        toggle = page.locator("[data-theme-toggle]").first
        toggle.click()
        page.wait_for_function("document.documentElement.dataset.themeMode === 'light'")
        assert page.evaluate("window.localStorage.getItem('tg-admin-theme')") == "light"

        page.goto(f"{demo_server}/recruiters")
        page.wait_for_load_state("networkidle")
        page.wait_for_function("document.documentElement.dataset.themeMode === 'light'")

        toggle.click()
        page.wait_for_function("document.documentElement.dataset.themeMode === 'dark'")
        assert page.evaluate("window.localStorage.getItem('tg-admin-theme')") == "dark"

        second_page = context.new_page()
        second_page.emulate_media(color_scheme="light")
        second_page.goto(f"{demo_server}/cities")
        second_page.wait_for_load_state("networkidle")
        second_page.wait_for_function("document.documentElement.dataset.themeMode === 'dark'")
        assert second_page.evaluate("window.localStorage.getItem('tg-admin-theme')") == "dark"
        second_page.close()

        toggle.click()
        page.wait_for_function("document.documentElement.dataset.themeMode === 'auto'")
        assert page.evaluate("window.localStorage.getItem('tg-admin-theme')") == "auto"
        assert page.evaluate("document.documentElement.hasAttribute('data-theme')") is False

        page.emulate_media(color_scheme="dark")
        page.reload()
        page.wait_for_load_state("networkidle")
        page.wait_for_function("document.documentElement.dataset.themeMode === 'auto'")
        assert page.evaluate("document.documentElement.hasAttribute('data-theme')") is False
        assert page.evaluate("document.documentElement.style.colorScheme") == "dark"
    finally:
        context.close()
        _close_browser(playwright, browser)


def test_recruiter_card_keyboard_accessibility(demo_server: str) -> None:
    playwright, browser = _launch_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 768})
    try:
        page.goto(f"{demo_server}/recruiters")
        page.wait_for_load_state("networkidle")

        card = page.locator("[data-rec-card]").first
        card.focus()
        page.keyboard.press("Enter")
        page.wait_for_url("**/recruiters/10/edit", wait_until="networkidle")
        assert "/recruiters/10/edit" in page.url

        page.go_back()
        page.wait_for_load_state("networkidle")
        card = page.locator("[data-rec-card]").first
        card.focus()
        page.keyboard.press("Space")
        page.wait_for_url("**/recruiters/10/edit", wait_until="networkidle")
        assert "/recruiters/10/edit" in page.url
    finally:
        _close_browser(playwright, browser)
