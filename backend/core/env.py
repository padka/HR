from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def load_env(path: Path | None = None) -> None:
    """Load key=value pairs from a .env file into os.environ."""
    env_path = path or _default_env_path()
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if key in os.environ:
            continue
        os.environ[key] = _strip_quotes(value.strip())


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
        return value[1:-1]
    return value


__all__ = ["load_env"]
