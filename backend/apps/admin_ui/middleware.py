"""Custom middleware for admin UI HTTP security headers and degraded mode."""

from __future__ import annotations

import secrets
import uuid
from typing import Any, Callable

from backend.apps.admin_ui.perf.degraded.middleware import DegradedDatabaseMiddleware
from backend.core.logging import reset_request_id, set_request_id


def _setdefault_header(headers: list[tuple[bytes, bytes]], name: bytes, value: str) -> None:
    lower = name.lower()
    if any(k.lower() == lower for k, _ in headers):
        return
    headers.append((name, value.encode("latin-1", "ignore")))


class SecureHeadersMiddleware:
    """Apply a baseline of security headers for every response."""

    # SPA routes don't use nonce-based CSP (Vite build doesn't support it).
    _spa_prefixes = ("/app", "/assets")

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        nonce = secrets.token_urlsafe(16)
        scope.setdefault("state", {})["csp_nonce"] = nonce

        path = str(scope.get("path") or "")
        is_spa = any(path.startswith(prefix) for prefix in self._spa_prefixes)
        is_https = str(scope.get("scheme") or "").lower() == "https"

        if is_spa:
            # SPA uses module scripts from Vite build - allow without nonce.
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'; "
                "base-uri 'self'; "
                "object-src 'none';"
            )
        else:
            csp = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'; "
                "base-uri 'self'; "
                "object-src 'none';"
            )

        headers_to_set: list[tuple[bytes, str]] = [
            (b"Content-Security-Policy", csp),
            (b"X-Frame-Options", "DENY"),
            (b"X-Content-Type-Options", "nosniff"),
            (b"X-XSS-Protection", "1; mode=block"),
            (b"Referrer-Policy", "strict-origin-when-cross-origin"),
            (
                b"Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()",
            ),
            (b"Cross-Origin-Opener-Policy", "same-origin"),
            (b"Cross-Origin-Resource-Policy", "same-origin"),
        ]
        if is_https:
            headers_to_set.append(
                (b"Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            )

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers") or [])
                for name, value in headers_to_set:
                    _setdefault_header(headers, name, value)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestIDMiddleware:
    """Add X-Request-ID header for request tracing and correlation."""

    HEADER_NAME = "X-Request-ID"
    _header_name = b"x-request-id"

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = ""
        for k, v in (scope.get("headers") or []):
            if k.lower() == self._header_name:
                request_id = v.decode("latin-1", "ignore")
                break
        if not request_id:
            request_id = str(uuid.uuid4())

        scope.setdefault("state", {})["request_id"] = request_id

        token = set_request_id(request_id)
        try:
            async def send_wrapper(message: dict[str, Any]) -> None:
                if message.get("type") == "http.response.start":
                    headers = [
                        (k, v)
                        for (k, v) in list(message.get("headers") or [])
                        if k.lower() != self._header_name
                    ]
                    headers.append((self._header_name, request_id.encode("latin-1", "ignore")))
                    message["headers"] = headers
                await send(message)

            await self.app(scope, receive, send_wrapper)
        finally:
            reset_request_id(token)


__all__ = [
    "SecureHeadersMiddleware",
    "DegradedDatabaseMiddleware",
    "RequestIDMiddleware",
]

