from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path
from typing import Optional


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

    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "formatter": formatter_name,
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "json",
            "filename": str(log_file),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        },
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": formatters,
            "handlers": handlers,
            "root": {
                "level": log_level,
                "handlers": ["console", "file"],
            },
        }
    )
    logging.captureWarnings(True)
    _configured = True


__all__ = ["configure_logging"]
