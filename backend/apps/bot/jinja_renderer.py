"""Jinja2-based message template renderer for bot messages.

This module provides a modern, component-based approach to message templating
using Jinja2, replacing the simple .format() approach.

Features:
- Component-based templates (blocks, macros)
- Custom filters for datetime formatting
- Caching of compiled templates
- Backward compatibility with existing TemplateProvider
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

# Template directory path
TEMPLATES_DIR = Path(__file__).parent / "templates_jinja"

# Month names in Russian (short format)
MONTH_NAMES_SHORT = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "мая",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}

# Day names in Russian (short format)
DAY_NAMES_SHORT = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}

# Timezone display names
TZ_DISPLAY_NAMES = {
    "Europe/Moscow": "МСК",
    "Asia/Novosibirsk": "НСК",
    "Asia/Yekaterinburg": "ЕКТ",
    "UTC": "UTC",
}


def _safe_zone(name: Optional[str]) -> ZoneInfo:
    """Get ZoneInfo object, fallback to UTC on error."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s', falling back to UTC", name)
        return ZoneInfo("UTC")


def _get_tz_display_name(tz_name: Optional[str], is_fallback: bool = False) -> str:
    """Get display name for timezone (e.g., 'МСК' for 'Europe/Moscow').

    Args:
        tz_name: Timezone name
        is_fallback: True if fallback to UTC was used

    Returns:
        Display name like 'МСК', 'UTC', or 'по вашему времени'
    """
    if not tz_name or is_fallback:
        return "UTC"
    return TZ_DISPLAY_NAMES.get(tz_name, "по вашему времени")


def filter_format_datetime(dt_utc: datetime, tz_name: Optional[str] = None) -> str:
    """Format datetime in full format: Пн, 12 дек • 14:30 (МСК)

    Args:
        dt_utc: UTC datetime object
        tz_name: Target timezone name (e.g., 'Europe/Moscow')

    Returns:
        Formatted string like "Пн, 12 дек • 14:30 (МСК)"
    """
    zone = _safe_zone(tz_name)
    is_fallback = (not tz_name) or (zone.key == "UTC" and tz_name != "UTC")
    local_dt = dt_utc.astimezone(zone)

    day_name = DAY_NAMES_SHORT[local_dt.weekday()]
    month_name = MONTH_NAMES_SHORT[local_dt.month]
    tz_display = _get_tz_display_name(tz_name, is_fallback)

    return f"{day_name}, {local_dt.day} {month_name} • {local_dt.hour:02d}:{local_dt.minute:02d} ({tz_display})"


def filter_format_date(dt_utc: datetime, tz_name: Optional[str] = None) -> str:
    """Format date only: Пн, 12 дек

    Args:
        dt_utc: UTC datetime object
        tz_name: Target timezone name

    Returns:
        Formatted string like "Пн, 12 дек"
    """
    zone = _safe_zone(tz_name)
    local_dt = dt_utc.astimezone(zone)

    day_name = DAY_NAMES_SHORT[local_dt.weekday()]
    month_name = MONTH_NAMES_SHORT[local_dt.month]

    return f"{day_name}, {local_dt.day} {month_name}"


def filter_format_time(dt_utc: datetime, tz_name: Optional[str] = None) -> str:
    """Format time only: 14:30 (МСК)

    Args:
        dt_utc: UTC datetime object
        tz_name: Target timezone name

    Returns:
        Formatted string like "14:30 (МСК)"
    """
    zone = _safe_zone(tz_name)
    is_fallback = (not tz_name) or (zone.key == "UTC" and tz_name != "UTC")
    local_dt = dt_utc.astimezone(zone)
    tz_display = _get_tz_display_name(tz_name, is_fallback)

    return f"{local_dt.hour:02d}:{local_dt.minute:02d} ({tz_display})"


def filter_format_short(dt_utc: datetime, tz_name: Optional[str] = None) -> str:
    """Format in short format: 12.12 • 14:30

    Args:
        dt_utc: UTC datetime object
        tz_name: Target timezone name

    Returns:
        Formatted string like "12.12 • 14:30"
    """
    zone = _safe_zone(tz_name)
    local_dt = dt_utc.astimezone(zone)

    return f"{local_dt.day:02d}.{local_dt.month:02d} • {local_dt.hour:02d}:{local_dt.minute:02d}"


class JinjaRenderer:
    """Jinja2-based template renderer for bot messages."""

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        """Initialize Jinja2 renderer.

        Args:
            templates_dir: Path to templates directory (default: backend/apps/bot/templates_jinja)
        """
        self._templates_dir = templates_dir or TEMPLATES_DIR

        if not self._templates_dir.exists():
            logger.warning(
                "Templates directory does not exist: %s. Creating it.",
                self._templates_dir,
            )
            self._templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        # IMPORTANT: autoescape=True prevents HTML injection from user input
        # (e.g., candidate_name with malicious HTML) when using parse_mode=HTML
        # Templates can still use {{ some_html|safe }} for intentional HTML
        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            autoescape=True,  # Escape HTML by default for security
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=False,
        )

        # Register custom filters
        self._env.filters["format_datetime"] = filter_format_datetime
        self._env.filters["format_date"] = filter_format_date
        self._env.filters["format_time"] = filter_format_time
        self._env.filters["format_short"] = filter_format_short

        logger.info("JinjaRenderer initialized with templates dir: %s", self._templates_dir)

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template with the given context.

        Args:
            template_name: Template name (e.g., 'messages/interview_confirmed.j2')
            context: Template context variables

        Returns:
            Rendered message text

        Raises:
            TemplateNotFound: If template file doesn't exist
            Exception: If rendering fails
        """
        try:
            # Ensure .j2 extension
            if not template_name.endswith(".j2"):
                template_name = f"{template_name}.j2"

            template = self._env.get_template(template_name)
            rendered = template.render(**context)

            # Strip excessive whitespace
            lines = [line.rstrip() for line in rendered.split("\n")]
            # Remove leading/trailing empty lines
            while lines and not lines[0]:
                lines.pop(0)
            while lines and not lines[-1]:
                lines.pop()

            return "\n".join(lines)

        except TemplateNotFound:
            logger.error("Template not found: %s", template_name)
            raise
        except Exception:
            logger.exception("Failed to render template %s", template_name)
            raise

    def render_safe(
        self, template_name: str, context: Dict[str, Any], fallback: str = ""
    ) -> str:
        """Render template with safe fallback on error.

        Args:
            template_name: Template name
            context: Template context
            fallback: Fallback message if rendering fails

        Returns:
            Rendered message or fallback
        """
        try:
            return self.render(template_name, context)
        except Exception:
            logger.exception("Failed to render template %s, using fallback", template_name)
            return fallback


# Global renderer instance
_renderer: Optional[JinjaRenderer] = None


def get_renderer() -> JinjaRenderer:
    """Get global JinjaRenderer instance (singleton)."""
    global _renderer
    if _renderer is None:
        _renderer = JinjaRenderer()
    return _renderer


def reset_renderer() -> None:
    """Reset global renderer instance (useful for testing)."""
    global _renderer
    _renderer = None


__all__ = [
    "JinjaRenderer",
    "get_renderer",
    "reset_renderer",
    "filter_format_datetime",
    "filter_format_date",
    "filter_format_time",
    "filter_format_short",
]
