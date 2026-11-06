"""Pure-ASGI security middleware.

- SecurityHeadersMiddleware: CSP, HSTS, anti-framing, nosniff, etc. (OWASP A05)
- CSRFMiddleware: Origin / Fetch-Metadata check + double-submit token (A01)
- BodySizeLimitMiddleware: rejects oversized request bodies (A04 / DoS)
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import cookie_parser
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.security import safe_equals

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

TURNSTILE_ORIGIN = "https://challenges.cloudflare.com"


def build_csp(*, turnstile: bool, upgrade_insecure: bool) -> str:
    """Strict CSP: no inline script/style. Turnstile needs its script, iframe and API origin."""
    script = "script-src 'self'" + (f" {TURNSTILE_ORIGIN}" if turnstile else "")
    connect = "connect-src 'self'" + (f" {TURNSTILE_ORIGIN}" if turnstile else "")
    parts = [
        "default-src 'self'",
        script,
        "style-src 'self'",
        "img-src 'self' data: blob:",
        "font-src 'self'",
        connect,
        *([f"frame-src {TURNSTILE_ORIGIN}"] if turnstile else []),
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    if upgrade_insecure:
        parts.append("upgrade-insecure-requests")
    return "; ".join(parts)


CONTENT_SECURITY_POLICY = build_csp(turnstile=False, upgrade_insecure=False)

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=(), interest-cohort=()"
)


async def _send_json(send: Send, status: int, detail: str, headers: Iterable[tuple[bytes, bytes]] = ()) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"cache-control", b"no-store"),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        settings = get_settings()
        self.hsts = bool(settings.cookie_secure)
        self.docs_enabled = bool(settings.enable_api_docs)
        # Only upgrade sub-resources when the site is served over HTTPS.
        self.csp = build_csp(turnstile=settings.turnstile_enabled, upgrade_insecure=self.hsts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        # Swagger UI needs inline scripts / a CDN; it is disabled in production.
        relax_csp = self.docs_enabled and path.startswith(("/api/docs", "/api/redoc"))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if not relax_csp:
                    headers.setdefault("Content-Security-Policy", self.csp)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
                headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
                if self.hsts:
                    headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
                if path.startswith("/api"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_wrapper)


class CSRFMiddleware:
    """Protects every state-changing /api request.

    1. If the browser sends Origin, it must be this site's own origin or one
       of ALLOWED_ORIGINS.
       Otherwise Sec-Fetch-Site must not be "cross-site".
    2. X-CSRF-Token header must equal the CSRF cookie (double submit).
    Authenticated routes additionally bind the token to the session
    (see app.api.deps.require_session).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        if origin is not None:
            # Same-origin is always fine: Host was already validated by
            # TrustedHostMiddleware, and a cross-site page cannot make the
            # browser send a matching Origin.
            own_origin = f"{scope.get('scheme', 'http')}://{headers.get('host', '')}"
            origin = origin.rstrip("/")
            if origin != own_origin and origin not in settings.allowed_origins:
                await _send_json(send, 403, "Cross-origin request blocked")
                return
        elif headers.get("sec-fetch-site") == "cross-site":
            await _send_json(send, 403, "Cross-origin request blocked")
            return

        cookies = cookie_parser(headers.get("cookie", ""))
        if not safe_equals(headers.get("x-csrf-token"), cookies.get(settings.csrf_cookie_name)):
            await _send_json(send, 403, "csrf_failed")
            return

        await self.app(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.max_bytes = get_settings().max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = Headers(scope=scope).get("content-length")
        if length is not None:
            if not length.isdigit() or int(length) > self.max_bytes:
                await _send_json(send, 413, "Request body too large")
                return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await _send_json(send, 413, "Request body too large")


class HostValidationMiddleware(TrustedHostMiddleware):
    """TrustedHostMiddleware that lets container/orchestrator health probes
    (which call 127.0.0.1 directly) through. Health endpoints expose nothing."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith("/api/health/"):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
