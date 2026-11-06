from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import ADMIN, Client


def test_csrf_token_required(app, client: Client):
    raw = TestClient(app)
    raw.get("/api/auth/status")
    r = raw.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12})
    assert r.status_code == 403
    assert r.json()["detail"] == "csrf_failed"


def test_cross_origin_blocked(client: Client):
    r = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "x" * 12},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_csrf_token_bound_to_session(admin_client: Client):
    # The pre-login token must not work after login (token rotates).
    r = admin_client.patch("/api/me", json={"name": "Renamed"}, headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403
    assert admin_client.patch("/api/me", json={"name": "Renamed"}).status_code == 200


def test_security_headers(client: Client):
    r = client.get("/api/health/live")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"


def test_untrusted_host_rejected(app):
    client = TestClient(app)
    assert client.get("/api/auth/status", headers={"Host": "attacker.example"}).status_code == 400
    # Health probes from the container itself are allowed.
    assert client.get("/api/health/live", headers={"Host": "127.0.0.1:8080"}).status_code == 200


def test_body_size_limit(client: Client):
    r = client.post(
        "/api/auth/login",
        content=b"x" * (get_settings().max_body_bytes + 1),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413


def test_auth_bypass_requires_sentinel_file(client: Client):
    settings = get_settings()
    settings.auth_enabled = False
    # Flag alone is not enough.
    assert client.get("/api/auth/status").json()["auth_bypass"] is False
    assert client.get("/api/dashboard/summary").status_code == 401

    settings.auth_bypass_file.touch()
    status = client.get("/api/auth/status").json()
    assert status["auth_bypass"] is True
    assert status["permissions"]["users"] == {"read": True, "write": True}
    assert client.get("/api/users").status_code == 200

    # Removing the file re-enables auth immediately, without restart.
    settings.auth_bypass_file.unlink()
    assert client.get("/api/users").status_code == 401


def test_auth_bypass_never_in_production(client: Client, monkeypatch):
    settings = get_settings()
    settings.auth_enabled = False
    settings.auth_bypass_file.touch()
    monkeypatch.setattr(settings, "app_env", "production")
    assert client.get("/api/users").status_code == 401


def test_production_refuses_unsafe_config(monkeypatch):
    import pytest

    from app.core.config import Settings, UnsafeConfiguration

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "short-but-secret-value")
    with pytest.raises(UnsafeConfiguration) as info:
        Settings().enforce_production_safety()
    assert "short-but-secret-value" not in str(info.value)


def test_validation_errors_do_not_echo_input(client: Client):
    r = client.post("/api/auth/setup", json={**ADMIN, "email": "not-an-email-<script>"})
    assert r.status_code == 422
    assert "<script>" not in r.text


def test_spa_fallback_and_api_404(client: Client):
    dist = get_settings().frontend_dist
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    assert "id=root" in client.get("/users/123").text
    assert client.get("/api/nope").status_code == 404
    assert client.get("/../../etc/passwd").status_code in (200, 404)
    assert "root:" not in client.get("/..%2F..%2Fetc%2Fpasswd").text
