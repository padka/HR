from __future__ import annotations

import json
import logging
import logging.config
import hashlib
from pathlib import Path
from typing import Any, Iterable, Optional


class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info
        return json.dumps(payload, ensure_ascii=False)


def _default_log_file(data_dir: Path) -> Path:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "app.log"


def pseudonymize(value: Any) -> str:
    """Return a deterministic hash for PII values."""
    try:
        raw = str(value)
    except Exception:
        return "redacted"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class PIIFilter(logging.Filter):
    """Pseudonymize known PII fields added via `extra`."""

    PII_FIELDS = {
        "user_id",
        "telegram_id",
        "telegram_user_id",
        "username",
        "telegram_username",
        "first_name",
        "last_name",
        "fio",
        "phone",
        "email",
        "candidate_tg_id",
        "candidate_fio",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        for field in self.PII_FIELDS:
            if field in record.__dict__:
                record.__dict__[field] = pseudonymize(record.__dict__[field])
        return True


class SecretsFilter(logging.Filter):
    """Mask known secrets if they accidentally end up in logs."""

    def __init__(self, secrets: Iterable[str] | None = None):
        super().__init__()
        self._secrets = [value for value in secrets or [] if value]

    def _mask(self, text: str) -> str:
        masked = text
        for secret in self._secrets:
            if secret and secret in masked:
                masked = masked.replace(secret, "***")
        return masked

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._mask(record.msg)
        if getattr(record, "args", None):
            record.args = tuple(self._mask(arg) if isinstance(arg, str) else arg for arg in record.args)

        for key, value in list(record.__dict__.items()):
            if isinstance(value, str):
                record.__dict__[key] = self._mask(value)
        return True


_configured = False


def configure_logging(settings=None) -> None:
    """Configure application logging once per process."""

    global _configured
    if _configured:
        return

    if settings is None:
        from backend.core.settings import get_settings

        settings = get_settings()

    log_level = getattr(settings, "log_level", "INFO") or "INFO"
    log_json = bool(getattr(settings, "log_json", False))
    log_file_value = getattr(settings, "log_file", "") or ""
    log_file = Path(log_file_value) if log_file_value else _default_log_file(settings.data_dir)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter_name = "json" if log_json else "standard"
    formatters = {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
        "json": {
            "()": "backend.core.logging.JsonFormatter",
        },
    }

    sensitive_values = [
        getattr(settings, "bot_token", ""),
        getattr(settings, "session_secret", ""),
        getattr(settings, "admin_password", ""),
        getattr(settings, "bot_callback_secret", ""),
    ]

    filters = {
        "pii": {"()": "backend.core.logging.PIIFilter"},
        "secrets": {"()": "backend.core.logging.SecretsFilter", "secrets": sensitive_values},
    }

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": formatter_name,
            "filters": ["pii", "secrets"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "json",
            "filename": str(log_file),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "filters": ["pii", "secrets"],
        },
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "filters": filters,
            "handlers": handlers,
            "root": {
                "level": log_level,
                "handlers": ["console", "file"],
            },
        }
    )
    logging.captureWarnings(True)
    _configured = True


__all__ = [
    "configure_logging",
    "PIIFilter",
    "SecretsFilter",
    "pseudonymize",
]
