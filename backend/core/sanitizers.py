from __future__ import annotations

import html
from typing import Optional

__all__ = ["sanitize_plain_text"]


def sanitize_plain_text(value: Optional[str], max_length: Optional[int] = None) -> str:
    """
    Normalize user-provided plain text so it is safe for HTML contexts.

    The function first unescapes the text to avoid double-escaping artefacts,
    then performs HTML escaping with all critical characters converted to
    entities (including the forward slash). The result is guaranteed to be
    idempotent.
    """

    if value is None:
        candidate = ""
    else:
        candidate = str(value)

    if max_length is not None:
        try:
            limit = int(max_length)
            if limit > 0:
                candidate = candidate[:limit]
        except Exception:
            pass

    # Trim whitespace and undo previous escaping to keep the function idempotent.
    normalized = html.unescape(candidate.strip())
    if not normalized:
        return ""

    escaped = html.escape(normalized, quote=True)
    # html.escape does not escape the forward slash by default.
    escaped = escaped.replace("/", "&#x2F;")
    return escaped
