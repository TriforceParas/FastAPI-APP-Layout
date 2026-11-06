from __future__ import annotations

import pytest

from app.core.config import Settings, UnsafeConfiguration, get_settings
from app.integrations import turnstile
from app.middleware.security import build_csp
from tests.conftest import ADMIN, Client

TEST_SITE = "1x00000000000000000000AA"
TEST_SECRET = "1x0000000000000000000000000000000AA"


@pytest.fixture
def enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "turnstile_enabled", True)
    monkeypatch.setattr(settings, "turnstile_site_key", TEST_SITE)
    monkeypatch.setattr(settings, "turnstile_secret_key", TEST_SECRET)
    return settings


def fake_siteverify(monkeypatch, success: bool, calls: list | None = None, **extra):
    """Mimics Cloudflare. By default it answers like the TEST keys do (dummy
    hostname, no action, result_with_testing_key=true)."""

    def fake(secret, token, remote_ip):
        if calls is not None:
            calls.append((secret, token))
        result = {"success": success, "error-codes": [] if success else ["invalid-input-response"]}
        result.update(extra or {"hostname": "example.com", "metadata": {"result_with_testing_key": True}})
        return result

    monkeypatch.setattr(turnstile, "_post_siteverify", fake)


def test_status_exposes_only_the_site_key(client: Client, enabled):
    data = client.get("/api/auth/status").json()
    assert data["turnstile_enabled"] is True and data["turnstile_site_key"] == TEST_SITE
    assert TEST_SECRET not in client.get("/api/auth/status").text


def test_disabled_by_default_in_tests(client: Client):
    data = client.get("/api/auth/status").json()
    assert data["turnstile_enabled"] is False and data["turnstile_site_key"] is None


def test_setup_requires_a_token_when_enabled(client: Client, enabled, monkeypatch):
    fake_siteverify(monkeypatch, True)
    r = client.post("/api/auth/setup", json=ADMIN)
    assert r.status_code == 400 and "verification" in r.json()["detail"].lower()


def test_login_rejects_a_failed_challenge_before_checking_the_password(client: Client, enabled, monkeypatch):
    calls: list = []
    fake_siteverify(monkeypatch, False, calls)
    r = client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "whatever 123456", "turnstile_token": "bad"}
    )
    assert r.status_code == 400 and r.json()["detail"] == "Verification failed. Please try again."
    assert calls == [(TEST_SECRET, "bad")]


def test_a_passing_challenge_allows_setup_and_login(client: Client, enabled, monkeypatch):
    fake_siteverify(monkeypatch, True)
    r = client.post("/api/auth/setup", json={**ADMIN, "turnstile_token": "ok"})
    assert r.status_code == 201
    client.post("/api/auth/logout")
    r = client.post(
        "/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"], "turnstile_token": "ok"}
    )
    assert r.status_code == 200


def test_fails_closed_when_cloudflare_is_unreachable(client: Client, enabled, monkeypatch):
    import httpx

    def boom(*args):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(turnstile, "_post_siteverify", boom)
    r = client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "whatever 123456", "turnstile_token": "t"}
    )
    assert r.status_code == 503


def test_bypass_mode_skips_turnstile(client: Client, enabled, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", False)
    settings.auth_bypass_file.touch()
    assert client.get("/api/auth/status").json()["turnstile_enabled"] is False


def test_csp_allows_cloudflare_only_when_enabled():
    off = build_csp(turnstile=False, upgrade_insecure=False)
    on = build_csp(turnstile=True, upgrade_insecure=True)
    assert "challenges.cloudflare.com" not in off
    assert "script-src 'self' https://challenges.cloudflare.com" in on
    assert "frame-src https://challenges.cloudflare.com" in on
    assert "'unsafe-inline'" not in on and "'unsafe-eval'" not in on


def test_enabled_requires_both_keys(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "")
    with pytest.raises(UnsafeConfiguration):
        Settings().validate_turnstile()


def test_production_refuses_cloudflare_test_keys(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("MAIL_PROVIDER", "disabled")
    monkeypatch.setenv("PUBLIC_URL", "https://app.example.com")
    monkeypatch.setenv("ALLOWED_HOSTS", "app.example.com")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("TURNSTILE_SITE_KEY", TEST_SITE)
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", TEST_SECRET)
    with pytest.raises(UnsafeConfiguration, match="TEST keys") as info:
        Settings().enforce_production_safety()
    assert TEST_SECRET not in str(info.value)
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "0x4AAAAAAAreal-site-key")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "0x4AAAAAAAreal-secret-key")
    Settings().enforce_production_safety()  # real-looking keys are accepted


# --- token binding (real keys) ---------------------------------------------------------


@pytest.fixture
def real_keys(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "turnstile_enabled", True)
    monkeypatch.setattr(settings, "turnstile_site_key", "0x4AAAAAAAreal-site-key")
    monkeypatch.setattr(settings, "turnstile_secret_key", "0x4AAAAAAAreal-secret-key")
    return settings


def login_with_token(client: Client):
    return client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "whatever 123456", "turnstile_token": "t"}
    )


def test_token_for_another_form_is_rejected(client: Client, real_keys, monkeypatch):
    fake_siteverify(monkeypatch, True, action="forgot", hostname="testserver")
    assert login_with_token(client).status_code == 400


def test_token_for_another_site_is_rejected(client: Client, real_keys, monkeypatch):
    fake_siteverify(monkeypatch, True, action="login", hostname="evil.example")
    assert login_with_token(client).status_code == 400


def test_matching_action_and_hostname_is_accepted(client: Client, real_keys, monkeypatch):
    fake_siteverify(monkeypatch, True, action="login", hostname="testserver")
    assert login_with_token(client).status_code == 401  # passed Turnstile, then wrong password


def test_testing_metadata_is_ignored_with_real_keys(client: Client, real_keys, monkeypatch):
    # An attacker cannot claim "testing" to skip the checks once real keys are configured.
    fake_siteverify(monkeypatch, True, hostname="example.com", metadata={"result_with_testing_key": True})
    assert login_with_token(client).status_code == 400
