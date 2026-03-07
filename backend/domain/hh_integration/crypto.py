"""Encryption helpers for HH OAuth tokens."""

from __future__ import annotations

import base64
import hashlib

from backend.core.settings import get_settings
from cryptography.fernet import Fernet


class HHSecretCipher:
    def __init__(self, *, secret: str | None = None):
        base_secret = secret or get_settings().session_secret
        digest = hashlib.sha256((base_secret + "|hh-integration").encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        if not value:
            return ""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        if not token:
            return ""
        return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")
