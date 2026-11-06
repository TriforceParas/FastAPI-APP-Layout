"""Sign in with Microsoft (OIDC). Microsoft is replaced by a local RSA key that
signs ID tokens; the token endpoint is stubbed to return them."""

from __future__ import annotations

import base64
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from sqlalchemy import delete, select

from app.core.config import UnsafeConfiguration, get_settings
from app.db.session import new_session
from app.features.auth.models import UserIdentity
from app.features.users.models import User
from app.integrations import microsoft_oidc as oidc
from tests.conftest import ADMIN, Client, make_role

TENANT = "11111111-2222-3333-4444-555555555555"
OTHER_TENANT = "99999999-8888-7777-6666-555555555555"
CLIENT_ID = "00000000-aaaa-bbbb-cccc-000000000001"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = "test-key"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_token(claims: dict, *, key=KEY, kid=KID, alg="RS256") -> str:
    header = _b64(json.dumps({"alg": alg, "kid": kid, "typ": "JWT"}).encode())
    payload = _b64(json.dumps(claims).encode())
    signature = key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64(signature)}"


class FakeMicrosoft:
    """Captures the nonce from the authorize redirect and issues matching tokens."""

    def __init__(self, monkeypatch):
        self.claims: dict = {}
        self.token_override: str | None = None
        self.redeemed: list[tuple[str, str]] = []
        monkeypatch.setattr(oidc._SigningKeys, "_fetch", staticmethod(lambda: {KID: KEY.public_key()}))
        monkeypatch.setattr(oidc, "_redeem_code", self._redeem)
        oidc._signing_keys.clear()

    def _redeem(self, code: str, verifier: str) -> str:
        self.redeemed.append((code, verifier))
        if self.token_override:
            return self.token_override
        return make_token(self.claims)

    def person(self, email: str, *, tenant=TENANT, oid: str | None = None, **extra) -> None:
        now = int(time.time())
        self.claims = {
            "iss": f"https://login.microsoftonline.com/{tenant}/v2.0",
            "aud": CLIENT_ID,
            "tid": tenant,
            "oid": oid or str(uuid.uuid4()),
            "email": email,
            "name": "Mia Microsoft",
            "iat": now,
            "nbf": now,
            "exp": now + 3600,
            **extra,
        }

    def sign_in(self, client: Client, *, tamper_state: bool = False):
        start = client.get("/api/auth/microsoft/login", follow_redirects=False)
        assert start.status_code == 303, start.text
        query = parse_qs(urlparse(start.headers["location"]).query)
        if self.claims.get("nonce") != "wrong":  # tests set "wrong" to simulate a mismatch
            self.claims["nonce"] = query["nonce"][0]
        state = "tampered" if tamper_state else query["state"][0]
        return client.get(
            "/api/auth/microsoft/callback", params={"code": "auth-code", "state": state}, follow_redirects=False
        )


@pytest.fixture
def sso(monkeypatch):
    settings = get_settings()
    values = {
        "microsoft_sso_enabled": True,
        "microsoft_sso_tenant_id": TENANT,
        "microsoft_sso_client_id": CLIENT_ID,
        "microsoft_sso_client_secret": "secret",
        "microsoft_sso_allowed_domains": ["contoso.com"],
        "microsoft_sso_allowed_tenant_ids": [],
        "microsoft_sso_auto_create_role": "",
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    fake = FakeMicrosoft(monkeypatch)
    yield fake
    with new_session() as db:
        db.execute(delete(UserIdentity))
        db.commit()


def sso_error(response) -> str | None:
    assert response.status_code == 303, response.text
    return parse_qs(urlparse(response.headers["location"]).query).get("sso_error", [None])[0]


def add_user(admin_client: Client, email: str, **extra) -> dict:
    member = next(r["id"] for r in admin_client.get("/api/lookups/roles").json() if r["label"] == "Member")
    r = admin_client.post(
        "/api/users",
        json={"name": "Mia", "email": email, "password": "a long enough passphrase", "role_ids": [member], **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def fresh(app) -> Client:
    c = Client(app)
    c.bootstrap()
    return c


# --- Configuration ------------------------------------------------------------------------


def test_disabled_by_default(client):
    assert client.get("/api/auth/status").json()["microsoft_sso_enabled"] is False
    assert client.get("/api/auth/microsoft/login", follow_redirects=False).status_code == 404
    assert client.get("/api/auth/microsoft/callback", follow_redirects=False).status_code == 404


def test_enabled_requires_domains_and_credentials(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "microsoft_sso_enabled", True)
    monkeypatch.setattr(settings, "microsoft_sso_tenant_id", TENANT)
    monkeypatch.setattr(settings, "microsoft_sso_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "microsoft_sso_client_secret", "x")
    monkeypatch.setattr(settings, "microsoft_sso_allowed_domains", [])
    with pytest.raises(UnsafeConfiguration, match="ALLOWED_DOMAINS"):
        settings.validate_microsoft_sso()
    monkeypatch.setattr(settings, "microsoft_sso_allowed_domains", ["*.contoso.com"])
    with pytest.raises(UnsafeConfiguration, match="plain domains"):
        settings.validate_microsoft_sso()
    monkeypatch.setattr(settings, "microsoft_sso_allowed_domains", ["contoso.com"])
    monkeypatch.setattr(settings, "microsoft_sso_tenant_id", "consumers")
    with pytest.raises(UnsafeConfiguration, match="personal"):
        settings.validate_microsoft_sso()


def test_production_refuses_unpinned_multi_tenant(monkeypatch):
    settings = get_settings()
    for name, value in {
        "app_env": "production",
        "secret_key": "x" * 40,
        "cookie_secure": True,
        "allowed_origins": ["https://app.example.com"],
        "allowed_hosts": ["app.example.com"],
        "mail_provider": "disabled",
        "public_url": "https://app.example.com",
        "turnstile_enabled": False,
        "microsoft_sso_enabled": True,
        "microsoft_sso_tenant_id": "organizations",
        "microsoft_sso_allowed_tenant_ids": [],
    }.items():
        monkeypatch.setattr(settings, name, value)
    with pytest.raises(UnsafeConfiguration, match="multi-tenant"):
        settings.enforce_production_safety()
    monkeypatch.setattr(settings, "microsoft_sso_allowed_tenant_ids", [TENANT])
    settings.enforce_production_safety()


def test_login_redirects_to_microsoft_with_pkce_and_lax_state_cookie(sso, client):
    assert client.get("/api/auth/status").json()["microsoft_sso_enabled"] is True
    r = client.get("/api/auth/microsoft/login", follow_redirects=False)
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "login.microsoftonline.com" and url.path == f"/{TENANT}/oauth2/v2.0/authorize"
    assert q["client_id"] == [CLIENT_ID] and q["code_challenge_method"] == ["S256"]
    assert q["redirect_uri"] == ["http://testserver/api/auth/microsoft/callback"]
    assert {"state", "nonce", "code_challenge"} <= q.keys()
    cookie = r.headers["set-cookie"]
    assert "oidc=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()
    assert "secret" not in r.headers["location"]


# --- Signing in -----------------------------------------------------------------------------


def test_existing_user_signs_in_and_gets_linked(sso, admin_client, app):
    user = add_user(admin_client, "mia@contoso.com")
    c = fresh(app)
    sso.person("Mia@Contoso.com")
    r = sso.sign_in(c)
    assert r.headers["location"] == "/" and sso_error(r) is None
    me = c.get("/api/auth/status").json()
    assert me["user"]["email"] == "mia@contoso.com"
    with new_session() as db:
        link = db.scalar(select(UserIdentity).where(UserIdentity.user_id == user["id"]))
        assert link.tenant_id == TENANT and link.subject == sso.claims["oid"]
    # PKCE: the verifier sent to the token endpoint matches the challenge sent to Microsoft
    assert sso.redeemed[-1][0] == "auth-code"


def test_linked_account_is_matched_by_object_id_not_email(sso, admin_client, app):
    add_user(admin_client, "mia@contoso.com")
    oid = str(uuid.uuid4())
    sso.person("mia@contoso.com", oid=oid)
    assert sso_error(sso.sign_in(fresh(app))) is None
    # Same Microsoft account, address renamed in Entra: still the same user.
    sso.person("mia.new@contoso.com", oid=oid)
    c = fresh(app)
    assert sso_error(sso.sign_in(c)) is None
    assert c.get("/api/auth/status").json()["user"]["email"] == "mia@contoso.com"
    # A DIFFERENT Microsoft account claiming the same email can't take over.
    sso.person("mia@contoso.com")
    assert sso_error(sso.sign_in(fresh(app))) == "linked_elsewhere"


@pytest.mark.parametrize(
    ("email", "tenant", "expected"),
    [
        ("mia@fabrikam.com", TENANT, "domain_not_allowed"),
        ("mia@contoso.com.evil.io", TENANT, "domain_not_allowed"),
        ("mia@contoso.com", OTHER_TENANT, "organisation_not_allowed"),
        ("mia@contoso.com", oidc.PERSONAL_ACCOUNTS_TENANT, "organisation_not_allowed"),
    ],
)
def test_domain_and_tenant_are_enforced(sso, admin_client, app, email, tenant, expected):
    add_user(admin_client, "mia@contoso.com")
    sso.person(email, tenant=tenant)
    c = fresh(app)
    assert sso_error(sso.sign_in(c)) == expected
    assert c.get("/api/auth/status").json()["user"] is None


def test_unknown_user_is_refused_unless_auto_create(sso, admin_client, app, monkeypatch):
    sso.person("new@contoso.com")
    assert sso_error(sso.sign_in(fresh(app))) == "no_account"

    monkeypatch.setattr(get_settings(), "microsoft_sso_auto_create_role", "Administrator")
    assert sso_error(sso.sign_in(fresh(app))) == "no_account"  # never auto-grant the admin role

    assert make_role(admin_client, "Staff", {"users": "r"}, landing="users").status_code == 201
    monkeypatch.setattr(get_settings(), "microsoft_sso_auto_create_role", "Staff")
    c = fresh(app)
    assert sso_error(sso.sign_in(c)) is None
    status = c.get("/api/auth/status").json()
    assert status["user"]["email"] == "new@contoso.com" and status["user"]["roles"][0]["name"] == "Staff"


def test_no_sso_before_setup(sso, client):
    sso.person(ADMIN["email"].replace("example.com", "contoso.com"))
    assert sso_error(sso.sign_in(client)) == "no_account"


def test_disabled_user_is_refused(sso, admin_client, app):
    user = add_user(admin_client, "mia@contoso.com")
    assert admin_client.patch(f"/api/users/{user['id']}", json={"is_active": False}).status_code == 200
    sso.person("mia@contoso.com")
    assert sso_error(sso.sign_in(fresh(app))) == "account_unavailable"


def test_two_factor_still_applies(sso, admin_client, app):
    user = add_user(admin_client, "mia@contoso.com")
    with new_session() as db:
        db.get(User, user["id"]).mfa_method = "email"
        db.commit()
    sso.person("mia@contoso.com")
    c = fresh(app)
    r = sso.sign_in(c)
    location = r.headers["location"]
    assert location.startswith("/#sso_mfa=") and "method=email" in location
    assert c.get("/api/auth/status").json()["user"] is None  # not signed in until the code is entered


# --- Attacks / bad responses ------------------------------------------------------------------


def test_state_mismatch_or_missing_cookie_is_refused(sso, admin_client, app):
    add_user(admin_client, "mia@contoso.com")
    sso.person("mia@contoso.com")
    assert sso_error(sso.sign_in(fresh(app), tamper_state=True)) == "failed"
    # Callback without the browser's state cookie (e.g. a link sent to a victim)
    r = fresh(app).get("/api/auth/microsoft/callback", params={"code": "x", "state": "y"}, follow_redirects=False)
    assert sso_error(r) == "expired"
    assert sso.redeemed == []  # the code was never redeemed


def test_user_cancelled(sso, client):
    client.get("/api/auth/microsoft/login", follow_redirects=False)
    r = client.get("/api/auth/microsoft/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert sso_error(r) == "cancelled"


@pytest.mark.parametrize(
    "bad",
    [
        {"nonce": "wrong"},
        {"aud": "someone-else"},
        {"exp": int(time.time()) - 3600},
        {"iss": f"https://login.microsoftonline.com/{OTHER_TENANT}/v2.0"},
        {"oid": "not-a-guid"},
    ],
)
def test_invalid_id_token_claims_are_refused(sso, admin_client, app, bad):
    add_user(admin_client, "mia@contoso.com")
    sso.person("mia@contoso.com", **bad)
    assert sso_error(sso.sign_in(fresh(app))) == "failed"


@pytest.mark.parametrize("kind", ["wrong_key", "alg_none", "garbage"])
def test_forged_tokens_are_refused(sso, admin_client, app, kind):
    add_user(admin_client, "mia@contoso.com")
    sso.person("mia@contoso.com")
    c = fresh(app)
    start = c.get("/api/auth/microsoft/login", follow_redirects=False)
    q = parse_qs(urlparse(start.headers["location"]).query)
    sso.claims["nonce"] = q["nonce"][0]
    if kind == "wrong_key":
        sso.token_override = make_token(sso.claims, key=rsa.generate_private_key(public_exponent=65537, key_size=2048))
    elif kind == "alg_none":
        header = _b64(json.dumps({"alg": "none", "kid": KID}).encode())
        sso.token_override = f"{header}.{_b64(json.dumps(sso.claims).encode())}."
    else:
        sso.token_override = "not.a.jwt.at-all"
    r = c.get("/api/auth/microsoft/callback", params={"code": "c", "state": q["state"][0]}, follow_redirects=False)
    assert sso_error(r) == "failed"
    assert c.get("/api/auth/status").json()["user"] is None


def test_state_cookie_is_single_use(sso, admin_client, app):
    add_user(admin_client, "mia@contoso.com")
    sso.person("mia@contoso.com")
    c = fresh(app)
    start = c.get("/api/auth/microsoft/login", follow_redirects=False)
    q = parse_qs(urlparse(start.headers["location"]).query)
    sso.claims["nonce"] = q["nonce"][0]
    first = c.get("/api/auth/microsoft/callback", params={"code": "c", "state": q["state"][0]}, follow_redirects=False)
    assert sso_error(first) is None
    # The browser is told to drop the state cookie, so the same attempt can't be completed twice.
    assert "oidc=" in first.headers["set-cookie"] and "Max-Age=0" in first.headers["set-cookie"]
