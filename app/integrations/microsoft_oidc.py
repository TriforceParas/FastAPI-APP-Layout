"""Sign in with Microsoft: OpenID Connect against Microsoft Entra ID.

Authorization-code flow with PKCE, a `state` bound to the browser and a
`nonce` bound to the ID token. The ID token is fully validated here:

* RS256 signature against Microsoft's published keys (cached, refreshed when an
  unknown key id appears, as Microsoft rotates keys),
* audience = our client id, issuer = the token's own tenant,
* expiry / not-before (with 2 minutes of clock skew),
* nonce = the one we generated for this attempt.

Policy (which tenants, domains and users may sign in) is decided by the caller,
in `app/features/auth/microsoft.py`. No FastAPI imports here.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.core.config import get_settings
from app.core.errors import ServiceUnavailable

log = logging.getLogger(__name__)

SCOPES = "openid profile email"
CLOCK_SKEW_SECONDS = 120
# Microsoft's fixed tenant id for personal (outlook.com / hotmail) accounts. Their
# email addresses are not verified by an organisation, so they are always refused.
PERSONAL_ACCOUNTS_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"
_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class OidcError(Exception):
    """The sign-in response was invalid. The message is for logs, never for users."""


@dataclass(frozen=True)
class MicrosoftIdentity:
    tenant_id: str  # "tid"
    object_id: str  # "oid": immutable per user and tenant
    email: str  # lower-case
    name: str


def redirect_uri() -> str:
    return f"{get_settings().public_url}/api/auth/microsoft/callback"


def pkce_challenge(verifier: str) -> str:
    return _b64encode(hashlib.sha256(verifier.encode()).digest())


def authorization_url(*, state: str, nonce: str, code_verifier: str) -> str:
    settings = get_settings()
    query = {
        "client_id": settings.sso_client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri(),
        "response_mode": "query",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": pkce_challenge(code_verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{settings.microsoft_sso_authority}/{settings.sso_tenant_id}/oauth2/v2.0/authorize?{urlencode(query)}"


def sign_in(code: str, *, code_verifier: str, nonce: str) -> MicrosoftIdentity:
    """Redeem the authorization code and return the validated identity."""
    id_token = _redeem_code(code, code_verifier)
    claims = validate_id_token(id_token, nonce=nonce)
    return identity_from_claims(claims)


# --- Token endpoint ---------------------------------------------------------------


def _redeem_code(code: str, code_verifier: str) -> str:
    settings = get_settings()
    url = f"{settings.microsoft_sso_authority}/{settings.sso_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.sso_client_id,
        "client_secret": settings.sso_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(),
        "code_verifier": code_verifier,
        "scope": SCOPES,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, data=data)
    except httpx.HTTPError as exc:
        log.warning("Microsoft token endpoint unreachable: %s", type(exc).__name__)
        raise ServiceUnavailable("Microsoft sign-in is unavailable right now.") from None
    if response.status_code != 200:
        # Error codes only (e.g. invalid_grant / AADSTS70008); the body never holds secrets we sent.
        try:
            body = response.json()
        except ValueError:
            body = {}
        raise OidcError(
            f"token endpoint returned {response.status_code}: {body.get('error')} {body.get('error_codes')}"
        )
    try:
        token = response.json()["id_token"]
    except (ValueError, KeyError, TypeError):
        raise OidcError("token response has no id_token") from None
    if not isinstance(token, str):
        raise OidcError("id_token is not a string")
    return token


# --- ID token validation ------------------------------------------------------------


def validate_id_token(token: str, *, nonce: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64decode(header_b64))
        claims = json.loads(_b64decode(payload_b64))
        signature = _b64decode(signature_b64)
    except ValueError:
        raise OidcError("id_token is not a well-formed JWT") from None
    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise OidcError("id_token header/payload is not an object")
    if header.get("alg") != "RS256":  # never "none" or HMAC
        raise OidcError(f"unexpected id_token algorithm {header.get('alg')!r}")

    key = _signing_keys.get(str(header.get("kid", "")))
    try:
        key.verify(signature, f"{header_b64}.{payload_b64}".encode(), padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature:
        raise OidcError("id_token signature is invalid") from None

    now = time.time()
    tid = str(claims.get("tid", "")).lower()
    if not _GUID.match(tid):
        raise OidcError("id_token has no valid tid")
    if claims.get("iss") != f"{settings.microsoft_sso_authority}/{tid}/v2.0":
        raise OidcError("id_token issuer does not match its tenant")
    if claims.get("aud") != settings.sso_client_id:
        raise OidcError("id_token audience is not this application")
    if not isinstance(claims.get("exp"), int | float) or claims["exp"] < now - CLOCK_SKEW_SECONDS:
        raise OidcError("id_token has expired")
    if isinstance(claims.get("nbf"), int | float) and claims["nbf"] > now + CLOCK_SKEW_SECONDS:
        raise OidcError("id_token is not valid yet")
    if not nonce or claims.get("nonce") != nonce:
        raise OidcError("id_token nonce does not match this sign-in attempt")
    return claims


def identity_from_claims(claims: dict[str, Any]) -> MicrosoftIdentity:
    oid = str(claims.get("oid", "")).lower()
    if not _GUID.match(oid):
        raise OidcError("id_token has no oid")
    # `email` is set when the account has a mailbox; `preferred_username` (the UPN) otherwise.
    email = str(claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if email.count("@") != 1 or len(email) > 254:
        raise OidcError("id_token has no usable email address")
    name = " ".join(str(claims.get("name") or "").split())[:100] or email.split("@")[0]
    return MicrosoftIdentity(tenant_id=str(claims["tid"]).lower(), object_id=oid, email=email, name=name)


def email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1]


# --- Signing keys (JWKS) ---------------------------------------------------------------


class _SigningKeys:
    """Microsoft's public keys, cached for a day. An unknown key id triggers one
    refresh (at most once a minute), which handles key rotation."""

    MAX_AGE = 24 * 3600
    MIN_REFRESH_INTERVAL = 60

    def __init__(self) -> None:
        self._keys: dict[str, rsa.RSAPublicKey] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def get(self, kid: str) -> rsa.RSAPublicKey:
        with self._lock:
            now = time.monotonic()
            stale = now - self._fetched_at > self.MAX_AGE
            unknown = kid not in self._keys and now - self._fetched_at > self.MIN_REFRESH_INTERVAL
            if stale or unknown or not self._keys:
                self._keys = self._fetch()
                self._fetched_at = now
            try:
                return self._keys[kid]
            except KeyError:
                raise OidcError("id_token is signed with an unknown key") from None

    def clear(self) -> None:
        with self._lock:
            self._keys, self._fetched_at = {}, 0.0

    @staticmethod
    def _fetch() -> dict[str, rsa.RSAPublicKey]:
        settings = get_settings()
        # ?appid= also returns keys specific to this app registration, if it has any.
        url = f"{settings.microsoft_sso_authority}/{settings.sso_tenant_id}/discovery/v2.0/keys"
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, params={"appid": settings.sso_client_id})
                response.raise_for_status()
                document = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Could not fetch Microsoft signing keys: %s", type(exc).__name__)
            raise ServiceUnavailable("Microsoft sign-in is unavailable right now.") from None
        keys: dict[str, rsa.RSAPublicKey] = {}
        for jwk in document.get("keys", []) if isinstance(document, dict) else []:
            if not isinstance(jwk, dict) or jwk.get("kty") != "RSA" or jwk.get("use", "sig") != "sig":
                continue
            try:
                numbers = rsa.RSAPublicNumbers(
                    e=int.from_bytes(_b64decode(jwk["e"]), "big"), n=int.from_bytes(_b64decode(jwk["n"]), "big")
                )
                keys[str(jwk["kid"])] = numbers.public_key()
            except (KeyError, ValueError, TypeError):
                continue
        return keys


_signing_keys = _SigningKeys()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
