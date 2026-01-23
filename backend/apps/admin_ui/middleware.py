"""Custom middleware for admin UI HTTP security headers and degraded mode."""

from __future__ import annotations

import logging
import secrets
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, HTMLResponse, JSONResponse

from backend.core.logging import set_request_id, reset_request_id

logger = logging.getLogger(__name__)


class DegradedDatabaseMiddleware(BaseHTTPMiddleware):
    """Short-circuit requests when DB is unavailable to avoid noisy 500s."""

    _allow_prefixes = ("/static", "/health", "/metrics", "/docs", "/redoc", "/openapi.json")
    _allow_paths = (
        "/",
        "/favicon.ico",
        "/.well-known/appspecific/com.chrome.devtools.json",
        "/api/notifications/feed",
    )

    async def dispatch(self, request: Request, call_next):
        db_available = getattr(request.app.state, "db_available", True)
        path = request.url.path
        if not db_available:
            if path in self._allow_paths or path.startswith(self._allow_prefixes):
                return await call_next(request)
            accepts = (request.headers.get("accept") or "").lower()
            payload = {"status": "degraded", "reason": "database_unavailable"}
            if "application/json" in accepts:
                return JSONResponse(payload, status_code=503)
            return HTMLResponse(
                "<h1>Service temporarily degraded</h1>"
                "<p>Database is unavailable. Please try again позже.</p>",
                status_code=503,
            )
        return await call_next(request)


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """Apply a baseline of security headers for every response."""

    async def dispatch(self, request: Request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response: Response = await call_next(request)

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
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add X-Request-ID header for request tracing and correlation."""

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        # Use existing request ID from header or generate new one
        request_id = request.headers.get(self.HEADER_NAME)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in request state for use in logging/error reporting
        request.state.request_id = request_id

        # Set context variable for automatic inclusion in all logs
        token = set_request_id(request_id)
        try:
            response: Response = await call_next(request)
            # Add to response headers
            response.headers[self.HEADER_NAME] = request_id
            return response
        finally:
            reset_request_id(token)


__all__ = ["SecureHeadersMiddleware", "DegradedDatabaseMiddleware", "RequestIDMiddleware"]
