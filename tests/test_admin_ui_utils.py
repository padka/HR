from datetime import datetime, timezone
import importlib.util
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "admin_ui_utils_for_tests",
    Path(__file__).resolve().parents[1] / "backend" / "apps" / "admin_ui" / "utils.py",
)
_utils = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_utils)  # type: ignore[attr-defined]
fmt_local = _utils.fmt_local


def test_fmt_local_default_format():
    dt = datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc)
    assert fmt_local(dt, "Europe/Moscow") == "02.01 06:04"


def test_fmt_local_custom_format():
    dt = datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc)
    assert fmt_local(dt, "Europe/Moscow", fmt="%Y-%m-%d %H:%M") == "2024-01-02 06:04"


@pytest.mark.parametrize("tz", ["", "Invalid/Zone"])
def test_fmt_local_safe_zone_fallback(tz: str):
    dt = datetime(2024, 1, 2, 3, 4, tzinfo=timezone.utc)
    assert fmt_local(dt, tz) == "02.01 06:04"
