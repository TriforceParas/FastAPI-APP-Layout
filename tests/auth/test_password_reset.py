from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import update

from app.core.config import get_settings
from app.db.base import utcnow
from app.db.session import new_session
from app.features.auth.models import PasswordReset
from app.integrations.mail import console_mailer
from tests.conftest import ADMIN, Client, last_email


def reset_token(to: str) -> str:
    match = re.search(r"reset-password\?token=([\w-]+)", last_email(to).text)
    assert match, "no reset link in the email"
    return match.group(1)


def forgot(client: Client, email: str):
    return client.post("/api/auth/password/forgot", json={"email": email})


def test_status_advertises_mail(client: Client):
    assert client.get("/api/auth/status").json()["mail_enabled"] is True


def test_reply_is_identical_for_known_and_unknown_addresses(admin_client: Client):
    known = forgot(admin_client, ADMIN["email"])
    unknown = forgot(admin_client, "nobody@example.com")
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [m.to for m in console_mailer.outbox] == [ADMIN["email"]]


def test_full_reset_flow_signs_out_everywhere(admin_client: Client, app):
    forgot(admin_client, ADMIN["email"])
    token = reset_token(ADMIN["email"])
    assert last_email().subject.startswith("Reset your password")
    assert "http://testserver/reset-password?token=" in last_email().text

    anon = Client(app)
    anon.bootstrap()
    r = anon.post("/api/auth/password/reset", json={"token": token, "new_password": "brand new passphrase 9"})
    assert r.status_code == 200
    assert admin_client.get("/api/me").status_code == 401  # old sessions revoked
    assert (
        anon.post("/api/auth/login", json={"email": ADMIN["email"], "password": "brand new passphrase 9"}).status_code
        == 200
    )
    assert "Security change" in last_email().subject


def test_links_are_single_use(admin_client: Client):
    forgot(admin_client, ADMIN["email"])
    token = reset_token(ADMIN["email"])
    body = {"token": token, "new_password": "brand new passphrase 9"}
    assert admin_client.post("/api/auth/password/reset", json=body).status_code == 200
    assert (
        admin_client.post(
            "/api/auth/password/reset", json={**body, "new_password": "another passphrase 22"}
        ).status_code
        == 400
    )


def test_only_the_newest_link_works(admin_client: Client):
    forgot(admin_client, ADMIN["email"])
    first = reset_token(ADMIN["email"])
    with new_session() as db:  # step past the one-per-minute throttle
        db.execute(update(PasswordReset).values(created_at=utcnow() - timedelta(minutes=5)))
        db.commit()
    forgot(admin_client, ADMIN["email"])
    second = reset_token(ADMIN["email"])
    assert first != second
    r = admin_client.post("/api/auth/password/reset", json={"token": first, "new_password": "brand new passphrase 9"})
    assert r.status_code == 400


def test_one_email_per_minute_per_account(admin_client: Client):
    forgot(admin_client, ADMIN["email"])
    forgot(admin_client, ADMIN["email"])
    assert len([m for m in console_mailer.outbox if m.to == ADMIN["email"]]) == 1


def test_expired_links_are_rejected(admin_client: Client):
    forgot(admin_client, ADMIN["email"])
    token = reset_token(ADMIN["email"])
    with new_session() as db:
        db.execute(update(PasswordReset).values(expires_at=utcnow() - timedelta(minutes=1)))
        db.commit()
    r = admin_client.post("/api/auth/password/reset", json={"token": token, "new_password": "brand new passphrase 9"})
    assert r.status_code == 400


def test_reset_enforces_password_policy_and_unlocks(admin_client: Client, app):
    fresh = Client(app)
    fresh.bootstrap()
    for _ in range(get_settings().login_max_attempts):
        fresh.post("/api/auth/login", json={"email": ADMIN["email"], "password": "wrong password!!"})
    forgot(fresh, ADMIN["email"])
    token = reset_token(ADMIN["email"])
    assert fresh.post("/api/auth/password/reset", json={"token": token, "new_password": "short"}).status_code == 422
    assert (
        fresh.post(
            "/api/auth/password/reset", json={"token": token, "new_password": "brand new passphrase 9"}
        ).status_code
        == 200
    )
    assert (
        fresh.post("/api/auth/login", json={"email": ADMIN["email"], "password": "brand new passphrase 9"}).status_code
        == 200
    )


def test_forgot_password_is_unavailable_without_email(admin_client: Client):
    get_settings().mail_provider = "disabled"
    assert admin_client.get("/api/auth/status").json()["mail_enabled"] is False
    assert forgot(admin_client, ADMIN["email"]).status_code == 404


def test_forgot_password_is_rate_limited(client: Client):
    codes = [forgot(client, f"x{i}@example.com").status_code for i in range(7)]
    assert 429 in codes
