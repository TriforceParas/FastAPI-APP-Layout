"""Outbound email.

Providers (MAIL_PROVIDER):
  console    development only: the message (including reset links and codes) is
             written to the log and kept in `outbox` for tests.
  microsoft  Microsoft 365 / Outlook through the Microsoft Graph API, using an
             Entra ID app registration with the *Mail.Send* application permission
             (client-credentials flow). Settings: AZURE_TENANT_ID, AZURE_CLIENT_ID,
             AZURE_CLIENT_SECRET, SENDER_EMAIL.
  disabled   nothing is sent; features that need email are hidden.

Send from request handlers with `background.add_task(send_safely, message)`:
response time then does not depend on whether an email was sent, which keeps
"forgot password" from revealing which addresses have accounts.
"""

from __future__ import annotations

import html
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str
    html: str


class MailError(RuntimeError):
    pass


def _post(url: str, **kwargs: Any) -> httpx.Response:  # indirection for tests
    return httpx.post(url, timeout=10.0, **kwargs)


class ConsoleMailer:
    def __init__(self) -> None:
        self.outbox: list[Email] = []

    def send(self, email: Email) -> None:
        self.outbox = [*self.outbox[-49:], email]
        log.warning("DEV EMAIL (MAIL_PROVIDER=console) to=%s subject=%r\n%s", email.to, email.subject, email.text)


class MicrosoftGraphMailer:
    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _access_token(self, *, force: bool = False) -> str:
        settings = get_settings()
        with self._lock:
            if not force and self._token and time.monotonic() < self._expires_at - 60:
                return self._token
            response = _post(
                f"https://login.microsoftonline.com/{quote(settings.azure_tenant_id)}/oauth2/v2.0/token",
                data={
                    "client_id": settings.azure_client_id,
                    "client_secret": settings.azure_client_secret,
                    "scope": GRAPH_SCOPE,
                    "grant_type": "client_credentials",
                },
            )
            if response.status_code != 200:
                raise MailError(f"Microsoft token request failed ({response.status_code})")
            body = response.json()
            self._token = str(body["access_token"])
            self._expires_at = time.monotonic() + int(body.get("expires_in", 3600))
            return self._token

    def send(self, email: Email) -> None:
        settings = get_settings()
        payload = {
            "message": {
                "subject": email.subject,
                "body": {"contentType": "HTML", "content": email.html},
                "toRecipients": [{"emailAddress": {"address": email.to}}],
            },
            "saveToSentItems": False,
        }
        url = f"https://graph.microsoft.com/v1.0/users/{quote(settings.sender_email)}/sendMail"
        for attempt in (0, 1):
            response = _post(
                url, json=payload, headers={"Authorization": f"Bearer {self._access_token(force=attempt == 1)}"}
            )
            if response.status_code == 202:
                return
            if response.status_code != 401:
                break
        raise MailError(f"Microsoft Graph sendMail failed ({response.status_code})")


class DisabledMailer:
    def send(self, email: Email) -> None:
        raise MailError("Email is disabled (MAIL_PROVIDER=disabled)")


console_mailer = ConsoleMailer()
_graph_mailer = MicrosoftGraphMailer()
_disabled_mailer = DisabledMailer()


def get_mailer() -> ConsoleMailer | MicrosoftGraphMailer | DisabledMailer:
    provider = get_settings().mail_provider
    if provider == "microsoft":
        return _graph_mailer
    if provider == "disabled":
        return _disabled_mailer
    return console_mailer


def send_safely(email: Email) -> None:
    """For background tasks: never raises, never logs the message body."""
    try:
        get_mailer().send(email)
    except Exception:  # noqa: BLE001
        log.exception("Failed to send email %r", email.subject)


# --- Templates -------------------------------------------------------------------


def render(
    to: str,
    subject: str,
    *,
    greeting: str,
    lines: list[str],
    action: tuple[str, str] | None = None,
    code: str | None = None,
    footer: str = "If you did not request this, you can ignore this email and your account stays unchanged.",
) -> Email:
    """A small, dependency-free transactional template. All dynamic values are escaped."""
    app_name = get_settings().app_name
    e = html.escape
    parts = [f'<p style="margin:0 0 16px">{e(greeting)}</p>']
    parts += [f'<p style="margin:0 0 16px">{e(line)}</p>' for line in lines]
    text = [greeting, "", *lines, ""]
    if code:
        parts.append(
            '<p style="margin:24px 0;font-size:28px;letter-spacing:6px;font-weight:600;font-family:monospace">'
            f"{e(code)}</p>"
        )
        text += [code, ""]
    if action:
        label, url = action
        parts.append(
            f'<p style="margin:24px 0"><a href="{e(url, quote=True)}" '
            'style="background:#34d399;color:#06291c;padding:10px 16px;border-radius:6px;'
            f'text-decoration:none;font-weight:600">{e(label)}</a></p>'
            '<p style="margin:0 0 16px;font-size:12px;color:#666">Or paste this link into your browser:<br>'
            f"{e(url)}</p>"
        )
        text += [f"{label}: {url}", ""]
    parts.append(f'<p style="margin:24px 0 0;font-size:12px;color:#666">{e(footer)}</p>')
    text += [footer, "", f"— {app_name}"]
    body = (
        '<!doctype html><html><body style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'color:#172033;background:#f6f7f8;padding:24px"><div style="max-width:520px;margin:auto;'
        'background:#fff;border:1px solid #e3e7ec;border-radius:10px;padding:28px">'
        f'<p style="margin:0 0 20px;font-weight:600">{e(app_name)}</p>{"".join(parts)}</div></body></html>'
    )
    return Email(to=to, subject=f"{subject} · {app_name}", text="\n".join(text), html=body)
