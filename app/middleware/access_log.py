"""One log line per request: method, path, status, duration, client IP.

* The query string is NOT logged (password-reset links carry their token there).
* Health probes and static files (/assets/*, favicon, …) are logged at DEBUG so they
  do not drown API traffic.
* Runs inside RequestIdMiddleware, so each line carries the request id.
uvicorn's own access log is turned off (main.py / Dockerfile) to avoid duplicates.
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("app.access")


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            client = scope.get("client")
            is_static = not path.startswith("/api/") and "." in path.rsplit("/", 1)[-1]
            level = logging.DEBUG if path.startswith("/api/health/") or is_static else logging.INFO
            log.log(
                level,
                "%s %s %s %sms",
                scope.get("method"),
                path,
                status,
                duration_ms,
                extra={
                    "method": scope.get("method"),
                    "path": path,
                    "status": status,
                    "duration_ms": duration_ms,
                    "client_ip": client[0] if client else None,
                },
            )
