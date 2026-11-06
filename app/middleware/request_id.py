"""X-Request-ID: one id per request, for tracing a problem across logs.

* Accepts the caller's / proxy's `X-Request-ID` if it is a safe token
  (8–64 chars of [A-Za-z0-9._-]); otherwise generates one. A strict format
  keeps attacker-supplied values from injecting into log lines.
* Echoes it on every response and stores it in a context variable so every
  log line can include it (see app.core.logging).
* Unhandled exceptions are caught HERE (not by Starlette's outer error
  handler, which runs after the id is gone): logged with the id, and answered
  with a generic 500 that includes the id so users can quote it to support.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger("app.errors")

HEADER = "X-Request-ID"
_VALID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    return request_id_var.get()


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get(HEADER.lower(), "")
        request_id = incoming if _VALID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)

        started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            log.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:  # too late to send a clean error; let the server close the connection
                raise
            body = json.dumps({"detail": "Internal server error", "request_id": request_id}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (HEADER.lower().encode(), request_id.encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            request_id_var.reset(token)
