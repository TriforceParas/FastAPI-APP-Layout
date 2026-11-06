"""Cloudflare Turnstile verification (server side).

The widget on the login / setup form produces a one-time token. We verify it
with Cloudflare before doing any password work, so bots are rejected cheaply.
Fails CLOSED: if Cloudflare cannot be reached, the request is refused.

Each form renders the widget with its own `action` ("login", "setup",
"forgot"). We check that the token was issued for that action and for one of
our hostnames, so a token solved on another form or another site is useless.
Cloudflare's public test keys report a dummy hostname and no action; those
checks are skipped only for test-key results (production refuses test keys).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from starlette.requests import Request

from app.core.auth_mode import auth_bypass_active
from app.core.config import get_settings
from app.core.errors import BadRequest, ServiceUnavailable
from app.core.request_info import client_ip

log = logging.getLogger(__name__)


def _post_siteverify(secret: str, token: str, remote_ip: str | None) -> dict[str, Any]:
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    with httpx.Client(timeout=5.0) as client:
        response = client.post(get_settings().turnstile_verify_url, data=data)
        response.raise_for_status()
        return response.json()


ACTIONS = frozenset({"login", "setup", "forgot"})


def _expected_hostnames() -> set[str]:
    return {host.split(":")[0].lower() for host in get_settings().allowed_hosts}


def verify_or_raise(request: Request, token: str | None, *, action: str) -> None:
    """No-op when Turnstile is disabled or auth is bypassed (dev)."""
    settings = get_settings()
    if not settings.turnstile_enabled or auth_bypass_active():
        return
    if not token:
        raise BadRequest("Please complete the verification challenge.")
    try:
        result = _post_siteverify(settings.turnstile_secret_key, token, client_ip(request))
    except (httpx.HTTPError, ValueError):
        log.exception("Turnstile verification request failed")
        raise ServiceUnavailable("Verification service unavailable. Please try again.") from None
    if result.get("success") is not True:
        log.warning("Turnstile rejected a token: %s", result.get("error-codes"))
        raise BadRequest("Verification failed. Please try again.")

    testing = (
        settings.turnstile_uses_test_keys and (result.get("metadata") or {}).get("result_with_testing_key") is True
    )
    if not testing:
        if result.get("action") != action:
            log.warning("Turnstile token for action %r used on %r", result.get("action"), action)
            raise BadRequest("Verification failed. Please try again.")
        if str(result.get("hostname", "")).lower() not in _expected_hostnames():
            log.warning("Turnstile token issued for unexpected hostname %r", result.get("hostname"))
            raise BadRequest("Verification failed. Please try again.")
