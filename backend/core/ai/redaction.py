from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_RE = re.compile(r"(https?://\S+|\bwww\.[^\s]+)", re.IGNORECASE)
_USERNAME_RE = re.compile(r"@[A-Z0-9_]{3,}", re.IGNORECASE)
_LONG_DIGITS_RE = re.compile(r"\b\d{6,}\b")

# Rough phone matcher: "+7 900 000-00-00", "89000000000", "(900) 000-00-00", etc.
_PHONE_RE = re.compile(r"(\+?\d[\d\s()\-\.\u00A0]{7,}\d)")


@dataclass(frozen=True)
class RedactionResult:
    text: str
    safe_to_send: bool
    replacements: int


def _replace_known_name(text: str, name: Optional[str], placeholder: str) -> tuple[str, int]:
    if not name:
        return text, 0
    clean = (name or "").strip()
    if not clean:
        return text, 0
    parts = [p for p in re.split(r"\s+", clean) if len(p) >= 3]
    count = 0
    # Replace full name first.
    pattern_full = re.compile(re.escape(clean), re.IGNORECASE)
    text, n = pattern_full.subn(placeholder, text)
    count += n
    # Replace individual parts to reduce leakage (best-effort).
    for part in parts:
        pattern = re.compile(rf"\b{re.escape(part)}\b", re.IGNORECASE)
        text, n = pattern.subn(placeholder, text)
        count += n
    return text, count


def redact_text(
    text: str,
    *,
    candidate_fio: Optional[str] = None,
    recruiter_name: Optional[str] = None,
    max_len: int = 2000,
) -> RedactionResult:
    """Best-effort PII redaction for AI prompts.

    This function is intentionally conservative. If we are not confident that
    sensitive tokens are removed, safe_to_send will be False.
    """

    if text is None:
        return RedactionResult(text="", safe_to_send=True, replacements=0)

    original = str(text)
    clipped = original[:max_len]
    replacements = 0

    clipped, n = _replace_known_name(clipped, candidate_fio, "CANDIDATE_NAME")
    replacements += n
    clipped, n = _replace_known_name(clipped, recruiter_name, "RECRUITER_NAME")
    replacements += n

    clipped, n = _EMAIL_RE.subn("EMAIL", clipped)
    replacements += n
    clipped, n = _URL_RE.subn("URL", clipped)
    replacements += n
    clipped, n = _USERNAME_RE.subn("USERNAME", clipped)
    replacements += n
    clipped, n = _PHONE_RE.subn("PHONE", clipped)
    replacements += n
    clipped, n = _LONG_DIGITS_RE.subn("ID", clipped)
    replacements += n

    # Safety check: ensure no obvious PII patterns remain after redaction.
    unsafe = False
    if _EMAIL_RE.search(clipped) or _URL_RE.search(clipped) or _PHONE_RE.search(clipped):
        unsafe = True
    # If there is too much digit density, consider unsafe.
    digits = sum(ch.isdigit() for ch in clipped)
    if len(clipped) > 0 and (digits / max(1, len(clipped))) > 0.25:
        unsafe = True

    return RedactionResult(text=clipped, safe_to_send=not unsafe, replacements=replacements)
