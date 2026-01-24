from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Tuple

PBKDF2_ITERATIONS = 120_000
SALT_BYTES = 16


def _pbkdf2_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)


def hash_password(password: str) -> str:
    """Return salted PBKDF2 hash in the format pbkdf2$<iters>$<salt_b64>$<hash_b64>."""
    salt = os.urandom(SALT_BYTES)
    digest = _pbkdf2_hash(password, salt)
    return "pbkdf2${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        if not stored.startswith("pbkdf2$"):
            return False
        _, iter_s, salt_b64, hash_b64 = stored.split("$", 3)
        iterations = int(iter_s)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
        computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected))
        return hmac.compare_digest(expected, computed)
    except Exception:
        return False


def make_legacy_hash(password: str) -> str:
    """Compat helper if we need to provision accounts from env quickly."""
    return hash_password(password)

