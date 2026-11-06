from __future__ import annotations

import re
import time

from sqlalchemy import select

from app.core import totp
from app.core.config import get_settings
from app.db.session import new_session
from app.features.users.models import User
from tests.conftest import ADMIN, Client, last_email, make_user, role_ids

PW = ADMIN["password"]


def emailed_code(to: str) -> str:
    match = re.search(r"\b(\d{6})\b", last_email(to).text)
    assert match
    return match.group(1)


def enable_totp(client: Client) -> tuple[str, list[str]]:
    start = client.post("/api/me/mfa/totp/start", json={"current_password": PW}).json()
    assert start["otpauth_uri"].startswith("otpauth://totp/") and start["qr_code"].startswith("data:image/svg+xml")
    secret = start["secret"]
    code = totp.code_at(secret, totp.current_step())
    r = client.post("/api/me/mfa/confirm", json={"challenge_token": start["challenge_token"], "code": code})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"]


def login(app, password=PW, email=ADMIN["email"]) -> tuple[Client, dict]:
    c = Client(app)
    c.bootstrap()
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c, r.json()


def next_step_code(secret: str) -> str:
    # The code for the current step was just used; the next step is accepted (+1 drift window).
    return totp.code_at(secret, totp.current_step() + 1)


# --- unit: TOTP ---------------------------------------------------------------------


def test_totp_matches_rfc6238_reference_vector():
    # RFC 6238 appendix B, SHA1, T=59s -> 94287082 (8 digits); our 6-digit code is its last 6.
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32("12345678901234567890")
    assert totp.code_at(secret, 59 // 30) == "287082"


def test_totp_rejects_replay_and_old_codes():
    secret = totp.new_secret()
    now = time.time()
    step = totp.current_step(now)
    code = totp.code_at(secret, step)
    assert totp.verify(secret, code, now=now) == step
    assert totp.verify(secret, code, last_step=step, now=now) is None  # replay
    assert totp.verify(secret, totp.code_at(secret, step - 5), now=now) is None  # too old


# --- enrolment -----------------------------------------------------------------------


def test_mfa_is_off_by_default(admin_client: Client):
    status = admin_client.get("/api/me/mfa").json()
    assert status["method"] is None and status["email_available"] is True


def test_enrolment_requires_the_current_password(admin_client: Client):
    assert admin_client.post("/api/me/mfa/totp/start", json={"current_password": "wrong password!!"}).status_code == 400
    assert (
        admin_client.post("/api/me/mfa/email/start", json={"current_password": "wrong password!!"}).status_code == 400
    )


def test_totp_enrolment_needs_a_correct_code(admin_client: Client):
    start = admin_client.post("/api/me/mfa/totp/start", json={"current_password": PW}).json()
    r = admin_client.post("/api/me/mfa/confirm", json={"challenge_token": start["challenge_token"], "code": "000000"})
    assert r.status_code == 400
    assert admin_client.get("/api/me/mfa").json()["method"] is None


def test_totp_secret_is_encrypted_at_rest(admin_client: Client):
    secret, codes = enable_totp(admin_client)
    assert len(codes) == 10
    with new_session() as db:
        user = db.scalar(select(User).where(User.email == ADMIN["email"]))
        assert user.mfa_method == "totp" and secret not in (user.mfa_secret_encrypted or "")
        assert all(c not in str(user.mfa_recovery_hashes) for c in codes)


# --- sign-in with an authenticator app ----------------------------------------------------


def test_login_with_totp(admin_client: Client, app):
    secret, _ = enable_totp(admin_client)
    c, body = login(app)
    assert body == {"mfa_required": True, "mfa_method": "totp", "challenge_token": body["challenge_token"]}
    assert c.get("/api/me").status_code == 401  # no session yet
    r = c.post(
        "/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": next_step_code(secret)}
    )
    assert r.status_code == 200 and r.json()["user"]["mfa_method"] == "totp"
    assert c.get("/api/me").status_code == 200


def test_wrong_codes_count_towards_lockout(admin_client: Client, app):
    enable_totp(admin_client)
    for _ in range(get_settings().login_max_attempts):
        c, body = login(app)
        c.post("/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": "000000"})
    fresh = Client(app)
    fresh.bootstrap()
    r = fresh.post("/api/auth/login", json={"email": ADMIN["email"], "password": PW})
    assert r.status_code == 401  # locked, even with the right password


def test_challenge_dies_after_five_wrong_codes(admin_client: Client, app):
    secret, _ = enable_totp(admin_client)
    get_settings().login_max_attempts = 50  # isolate the per-challenge limit from the account lockout
    try:
        c, body = login(app)
        for _ in range(5):
            c.post("/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": "000000"})
        r = c.post(
            "/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": next_step_code(secret)}
        )
        assert r.status_code == 400
    finally:
        get_settings().login_max_attempts = 5


def test_recovery_codes_are_single_use(admin_client: Client, app):
    _, codes = enable_totp(admin_client)
    c, body = login(app)
    assert (
        c.post(
            "/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": codes[0].upper()}
        ).status_code
        == 200
    )
    c2, body2 = login(app)
    assert (
        c2.post(
            "/api/auth/login/verify", json={"challenge_token": body2["challenge_token"], "code": codes[0]}
        ).status_code
        == 401
    )
    assert c2.get("/api/me").status_code == 401
    assert admin_client.get("/api/me/mfa").json()["recovery_codes_remaining"] in (
        9,
        10,
    )  # (admin_client session may be revoked)


def test_challenge_tokens_are_not_sessions(admin_client: Client, app):
    enable_totp(admin_client)
    c, body = login(app)
    assert (
        c.post("/api/auth/login/resend", json={"challenge_token": body["challenge_token"]}).status_code == 400
    )  # totp: nothing to resend
    assert c.post("/api/auth/login/verify", json={"challenge_token": "x" * 40, "code": "123456"}).status_code == 400


# --- email codes -----------------------------------------------------------------------------


def test_email_code_enrolment_and_login(admin_client: Client, app):
    start = admin_client.post("/api/me/mfa/email/start", json={"current_password": PW}).json()
    assert start["destination_hint"] == "a***a@example.com"
    r = admin_client.post(
        "/api/me/mfa/confirm", json={"challenge_token": start["challenge_token"], "code": emailed_code(ADMIN["email"])}
    )
    assert r.status_code == 200

    c, body = login(app)
    assert body["mfa_method"] == "email" and body["destination_hint"] == "a***a@example.com"
    code = emailed_code(ADMIN["email"])
    assert (
        c.post(
            "/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": "000000"}
        ).status_code
        == 401
    )
    assert (
        c.post("/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": code}).status_code
        == 200
    )


def test_resend_is_throttled(admin_client: Client, app):
    start = admin_client.post("/api/me/mfa/email/start", json={"current_password": PW}).json()
    admin_client.post(
        "/api/me/mfa/confirm", json={"challenge_token": start["challenge_token"], "code": emailed_code(ADMIN["email"])}
    )
    c, body = login(app)
    r = c.post("/api/auth/login/resend", json={"challenge_token": body["challenge_token"]})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_email_method_unavailable_without_mail(admin_client: Client):
    get_settings().mail_provider = "disabled"
    assert admin_client.post("/api/me/mfa/email/start", json={"current_password": PW}).status_code == 409


# --- management ------------------------------------------------------------------------------


def test_enabling_signs_out_other_sessions_and_notifies(admin_client: Client, app):
    other, _ = login(app)
    enable_totp(admin_client)
    assert other.get("/api/me").status_code == 401
    assert admin_client.get("/api/me").status_code == 200
    assert "Security change" in last_email(ADMIN["email"]).subject


def test_disable_requires_password(admin_client: Client, app):
    enable_totp(admin_client)
    assert admin_client.post("/api/me/mfa/disable", json={"current_password": "wrong password!!"}).status_code == 400
    assert admin_client.post("/api/me/mfa/disable", json={"current_password": PW}).status_code == 200
    _, body = login(app)
    assert "user" in body and not body.get("mfa_required")


def test_regenerating_recovery_codes_invalidates_old_ones(admin_client: Client, app):
    _, old = enable_totp(admin_client)
    new = admin_client.post("/api/me/mfa/recovery-codes", json={"current_password": PW}).json()["recovery_codes"]
    assert set(old).isdisjoint(new)
    c, body = login(app)
    assert (
        c.post("/api/auth/login/verify", json={"challenge_token": body["challenge_token"], "code": old[0]}).status_code
        == 401
    )


def test_admin_can_reset_a_users_mfa(admin_client: Client, app):
    user, member = make_user(admin_client, app)
    start = member.post("/api/me/mfa/totp/start", json={"current_password": "member password 1"}).json()
    member.post(
        "/api/me/mfa/confirm",
        json={"challenge_token": start["challenge_token"], "code": totp.code_at(start["secret"], totp.current_step())},
    )
    assert admin_client.get(f"/api/users/{user['id']}").json()["mfa_method"] == "totp"
    r = admin_client.post(f"/api/users/{user['id']}/mfa/reset")
    assert r.status_code == 200 and r.json()["mfa_method"] is None
    _, body = login(app, password="member password 1", email="mia@example.com")
    assert "user" in body  # straight in, no second step
    assert role_ids(admin_client)


def test_admin_cannot_reset_own_mfa_via_users_api(admin_client: Client):
    me = admin_client.get("/api/me").json()
    assert admin_client.post(f"/api/users/{me['id']}/mfa/reset").status_code == 409
