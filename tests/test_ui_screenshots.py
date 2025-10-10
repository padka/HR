from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from playwright.sync_api import Error, sync_playwright

from app_demo import app


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
DEFAULT_TIMEOUT_MS = 45_000

os.environ.setdefault("HEADLESS", "1")
os.environ.setdefault("PLAYWRIGHT_HEADLESS", "1")

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 834, "height": 1112},
    "mobile": {"width": 390, "height": 844},
}

SCREEN_ROOT = Path("ui_screenshots")
SCREEN_ROOT.mkdir(exist_ok=True)

ROUTE_SLUGS = {
    "/": "home",
    "/slots": "slots",
    "/candidates": "candidates",
    "/recruiters": "recruiters",
    "/cities": "cities",
    "/templates": "templates",
}


@pytest.fixture(scope="session")
def demo_server() -> str:
    config = uvicorn.Config(
        app,
        host=TEST_SERVER_HOST,
        port=TEST_SERVER_PORT,
        log_level="warning",
    )
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


def _launch_browser():
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(headless=True)
    except Error as exc:
        playwright.stop()
        message = str(exc)
        lowered = message.lower()
        if "dependencies" in lowered or "executable doesn't exist" in lowered:
            hint = (
                "Playwright Chromium dependencies are missing. "
                "Install them via: playwright install --with-deps chromium"
            )
            pytest.fail(hint, pytrace=False)
        raise
    return playwright, browser


def _close_browser(playwright, browser) -> None:
    browser.close()
    playwright.stop()


@pytest.mark.parametrize(
    "route",
    [
        pytest.param(path, id=slug)
        for path, slug in ROUTE_SLUGS.items()
    ],
)
def test_ui_screenshots(route: str, demo_server: str) -> None:
    playwright, browser = _launch_browser()
    try:
        for viewport_name, viewport in VIEWPORTS.items():
            page = browser.new_page(viewport=viewport)
            try:
                url = f"{demo_server}{route}"
                page.goto(url, wait_until="networkidle", timeout=DEFAULT_TIMEOUT_MS)
                page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT_MS)
                target_dir = SCREEN_ROOT / ROUTE_SLUGS[route]
                target_dir.mkdir(exist_ok=True, parents=True)
                screenshot_path = target_dir / f"{viewport_name}.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
            finally:
                page.close()
    finally:
        _close_browser(playwright, browser)


def test_recruiter_card_keyboard_accessibility(demo_server: str) -> None:
    playwright, browser = _launch_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 768})
    try:
        page.goto(
            f"{demo_server}/recruiters",
            wait_until="networkidle",
            timeout=DEFAULT_TIMEOUT_MS,
        )
        page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT_MS)

        card = page.locator("[data-rec-card]").first
        card.focus()
        page.keyboard.press("Enter")
        page.wait_for_url(
            "**/recruiters/10/edit",
            wait_until="networkidle",
            timeout=DEFAULT_TIMEOUT_MS,
        )
        assert "/recruiters/10/edit" in page.url

        page.go_back()
        page.wait_for_load_state("networkidle")
        card = page.locator("[data-rec-card]").first
        card.focus()
        page.keyboard.press("Space")
        page.wait_for_url(
            "**/recruiters/10/edit",
            wait_until="networkidle",
            timeout=DEFAULT_TIMEOUT_MS,
        )
        assert "/recruiters/10/edit" in page.url
    finally:
        _close_browser(playwright, browser)
