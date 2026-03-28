from __future__ import annotations

from typing import Any


def normalize_candidate_phone(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return digits


def format_candidate_phone_display(value: Any) -> str | None:
    normalized = normalize_candidate_phone(value)
    if not normalized:
        return None
    return f"+{normalized}"


def require_candidate_phone(value: Any) -> str:
    normalized = normalize_candidate_phone(value)
    if not normalized:
        raise ValueError("Укажите телефон в формате +7XXXXXXXXXX.")
    return normalized
