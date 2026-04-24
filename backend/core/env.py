from __future__ import annotations

import os
from pathlib import Path


def load_env(path: Path | None = None) -> None:
    """
    Load key=value pairs from .env file(s) into os.environ.

    Loads in order:
    1. .env (base configuration)
    2. .env.local (local overrides, not committed to git)

    .env.local can override values from .env, but shell environment variables
    take precedence over both.
    """
    # Remember which variables were already set before loading any .env files
    original_env_keys = set(os.environ.keys())

    # Load base .env file first
    env_path = path or _default_env_path()
    if env_path.exists():
        _load_env_file(env_path, allow_override=False)

    # Load .env.local for local overrides (if not using custom path).
    # Production services must not be affected by local override files.
    if path is None:
        local_env_path = env_path.parent / ".env.local"
        environment = (os.environ.get("ENVIRONMENT") or "").strip().lower()
        allow_production_local = _truthy(os.environ.get("ALLOW_PRODUCTION_ENV_LOCAL"))
        if local_env_path.exists() and (environment != "production" or allow_production_local):
            _load_env_file(local_env_path, allow_override=True, protected_keys=original_env_keys)


def _load_env_file(env_path: Path, allow_override: bool = False, protected_keys: set[str] | None = None) -> None:
    """
    Load a single .env file into os.environ.

    Args:
        env_path: Path to the .env file
        allow_override: If True, can override existing values (except protected)
        protected_keys: Keys that should never be overridden (e.g., shell variables)
    """
    protected = protected_keys or set()

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

        # Never override shell environment variables
        if key in protected:
            continue

        # If override not allowed, skip if key already exists
        if not allow_override and key in os.environ:
            continue

        os.environ[key] = _strip_quotes(value.strip())


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
        return value[1:-1]
    return value


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = ["load_env"]
