from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings, UnsafeConfiguration, get_settings
from app.integrations import mail


def resp(status: int, body: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json=body or {}, request=httpx.Request("POST", "https://x"))


@pytest.fixture
def microsoft(monkeypatch):
    settings = get_settings()
    for key, value in {
        "mail_provider": "microsoft",
        "azure_tenant_id": "tenant-id",
        "azure_client_id": "client-id",
        "azure_client_secret": "client-secret",
        "sender_email": "noreply@contoso.com",
    }.items():
        monkeypatch.setattr(settings, key, value)
    graph = mail.MicrosoftGraphMailer()
    monkeypatch.setattr(mail, "_graph_mailer", graph)
    return graph


def test_graph_mailer_uses_client_credentials_and_send_mail(microsoft, monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if "oauth2" in url:
            return resp(200, {"access_token": "tok", "expires_in": 3600})
        return resp(202)

    monkeypatch.setattr(mail, "_post", fake_post)
    msg = mail.render("ada@example.com", "Hello", greeting="Hi", lines=["<b>escaped</b>"])
    mail.get_mailer().send(msg)
    mail.get_mailer().send(msg)  # token is cached

    token_calls = [c for c in calls if "oauth2" in c[0]]
    send_calls = [c for c in calls if "sendMail" in c[0]]
    assert len(token_calls) == 1 and len(send_calls) == 2
    assert "login.microsoftonline.com/tenant-id/oauth2/v2.0/token" in token_calls[0][0]
    assert token_calls[0][1]["data"]["scope"] == "https://graph.microsoft.com/.default"
    assert token_calls[0][1]["data"]["grant_type"] == "client_credentials"
    url, kwargs = send_calls[0]
    assert url.endswith("/users/noreply%40contoso.com/sendMail")
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert kwargs["json"]["message"]["toRecipients"][0]["emailAddress"]["address"] == "ada@example.com"
    assert "&lt;b&gt;escaped&lt;/b&gt;" in kwargs["json"]["message"]["body"]["content"]


def test_graph_mailer_refreshes_an_expired_token_once(microsoft, monkeypatch):
    sends = []

    def fake_post(url, **kwargs):
        if "oauth2" in url:
            return resp(200, {"access_token": f"tok{len(sends)}", "expires_in": 3600})
        sends.append(kwargs["headers"]["Authorization"])
        return resp(401 if len(sends) == 1 else 202)

    monkeypatch.setattr(mail, "_post", fake_post)
    mail.get_mailer().send(mail.render("a@example.com", "S", greeting="Hi", lines=[]))
    assert len(sends) == 2


def test_send_failures_never_raise_from_background_tasks(microsoft, monkeypatch):
    monkeypatch.setattr(mail, "_post", lambda url, **kw: resp(500))
    mail.send_safely(mail.render("a@example.com", "S", greeting="Hi", lines=[]))  # logged, not raised


def test_microsoft_provider_requires_all_settings(monkeypatch):
    monkeypatch.setenv("MAIL_PROVIDER", "microsoft")
    monkeypatch.setenv("AZURE_TENANT_ID", "t")
    with pytest.raises(UnsafeConfiguration, match="AZURE_CLIENT_ID"):
        Settings().validate_mail()


def test_production_refuses_console_mail_and_http_links(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("ALLOWED_HOSTS", "app.example.com")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("TURNSTILE_ENABLED", "false")
    monkeypatch.setenv("MAIL_PROVIDER", "console")
    monkeypatch.setenv("PUBLIC_URL", "http://app.example.com")
    with pytest.raises(UnsafeConfiguration) as info:
        Settings().enforce_production_safety()
    assert "MAIL_PROVIDER=console" in str(info.value) and "PUBLIC_URL" in str(info.value)
    monkeypatch.setenv("MAIL_PROVIDER", "disabled")
    monkeypatch.setenv("PUBLIC_URL", "https://app.example.com")
    Settings().enforce_production_safety()
