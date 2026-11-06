from __future__ import annotations

from fastapi import Request


def client_ip(request: Request) -> str | None:
    """Client address as seen by uvicorn.

    Behind a reverse proxy, run uvicorn with `--proxy-headers
    --forwarded-allow-ips=<proxy ip>` so this reflects the real client and
    cannot be spoofed via X-Forwarded-For by arbitrary callers.
    """
    return request.client.host if request.client else None


def user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    return value[:255] if value else None
