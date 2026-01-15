from __future__ import annotations

import html
from typing import Optional

__all__ = ["escape_html"]


def escape_html(value: Optional[str]) -> str:
    """Escape text for safe insertion into HTML/Telegram messages."""
    return html.escape(value or "", quote=True)
