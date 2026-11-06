from __future__ import annotations

from app.core.config import get_settings
from tests.conftest import ADMIN, Client, role_ids


def test_status_reports_setup_required(client: Client):
    data = client.get("/api/auth/status").json()
    assert data["setup_required"] is True
    assert data["user"] is None
    assert data["auth_enabled"] is True


def test_setup_creates_admin_and_signs_in(admin_client: Client):
    data = admin_client.get("/api/auth/status").json()
    assert data["setup_required"] is False
    assert data["user"]["email"] == ADMIN["email"]
    assert [r["name"] for r in data["user"]["roles"]] == ["Administrator"]
    assert data["landing_path"] == "/dashboard"
    assert data["permissions"]["users"] == {"read": True, "write": True}


def test_setup_only_works_once(admin_client: Client):
    r = admin_client.post("/api/auth/setup", json={**ADMIN, "email": "other@example.com"})
    assert r.status_code == 409


def test_setup_rejects_weak_password_without_echoing_it(client: Client):
    r = client.post("/api/auth/setup", json={**ADMIN, "password": "short"})
    assert r.status_code == 422
    assert "short" not in r.text


def test_setup_token_enforced_when_required(client: Client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "setup_token_required", True)
    monkeypatch.setattr(settings, "setup_token", "the-one-time-token")
    assert client.post("/api/auth/setup", json=ADMIN).status_code == 403
    r = client.post("/api/auth/setup", json={**ADMIN, "setup_token": "the-one-time-token"})
    assert r.status_code == 201


def test_unknown_fields_are_rejected(client: Client):
    r = client.post("/api/auth/setup", json={**ADMIN, "role": "superuser"})
    assert r.status_code == 422


def test_login_logout_cycle(admin_client: Client, app):
    admin_client.post("/api/auth/logout")
    assert admin_client.get("/api/me").status_code == 401
    r = admin_client.post("/api/auth/login", json={"email": "ADA@example.com", "password": ADMIN["password"]})
    assert r.status_code == 200
    assert admin_client.get("/api/me").json()["email"] == ADMIN["email"]


def test_login_failure_is_generic(admin_client: Client, app):
    fresh = Client(app)
    fresh.bootstrap()
    wrong_pw = fresh.post("/api/auth/login", json={"email": ADMIN["email"], "password": "nope nope nope"})
    no_user = fresh.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope nope nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_account_lockout_after_repeated_failures(admin_client: Client, app):
    fresh = Client(app)
    fresh.bootstrap()
    for _ in range(get_settings().login_max_attempts):
        fresh.post("/api/auth/login", json={"email": ADMIN["email"], "password": "wrong password!!"})
    r = fresh.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    assert r.status_code == 401  # locked, even with the right password


def test_login_rate_limited_per_ip(client: Client):
    codes = [
        client.post("/api/auth/login", json={"email": "x@example.com", "password": "whatever123"}).status_code
        for _ in range(12)
    ]
    assert 429 in codes


def test_session_cookie_flags(client: Client):
    r = client.post("/api/auth/setup", json=ADMIN)
    cookie = [h for h in r.headers.get_list("set-cookie") if h.startswith("session=")][0].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie


def test_session_fixation_new_token_each_login(admin_client: Client):
    first = admin_client.cookies.get("session")
    admin_client.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    assert admin_client.cookies.get("session") != first


def test_password_change_revokes_other_sessions(admin_client: Client, app):
    other = Client(app)
    other.bootstrap()
    other.post("/api/auth/login", json={"email": ADMIN["email"], "password": ADMIN["password"]})
    assert other.get("/api/me").status_code == 200

    r = admin_client.post(
        "/api/me/password",
        json={"current_password": ADMIN["password"], "new_password": "a brand new passphrase"},
    )
    assert r.status_code == 204
    assert admin_client.get("/api/me").status_code == 200
    assert other.get("/api/me").status_code == 401


def test_must_change_password_blocks_other_endpoints(admin_client: Client, app):
    admin_client.post(
        "/api/users",
        json={
            "name": "New Person",
            "email": "new@example.com",
            "password": "temporary pass 99",
            "must_change_password": True,
            "role_ids": [role_ids(admin_client)["Member"]],
        },
    )
    user = Client(app)
    user.bootstrap()
    user.post("/api/auth/login", json={"email": "new@example.com", "password": "temporary pass 99"})
    assert user.get("/api/dashboard/summary").json()["detail"] == "password_change_required"
    user.post(
        "/api/me/password", json={"current_password": "temporary pass 99", "new_password": "my own secret phrase"}
    )
    assert user.get("/api/dashboard/summary").status_code == 200
