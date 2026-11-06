"""Symmetric encryption for secrets stored in the database (e.g. TOTP seeds).

The key is derived from SECRET_KEY, so changing SECRET_KEY makes existing
authenticator enrolments unreadable: affected users then sign in with a
recovery code (or an admin resets their 2FA) and enrol again.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet(secret_key: str, purpose: str) -> Fernet:
    # A separate key per purpose, so a value encrypted for one use (e.g. a sign-in
    # state cookie) can never be passed off as another (a stored TOTP seed).
    key = hashlib.sha256(f"app.{purpose}.v1:".encode() + secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value: str, *, purpose: str = "mfa") -> str:
    return _fernet(get_settings().secret_key, purpose).encrypt(value.encode()).decode()


def decrypt(token: str, *, purpose: str = "mfa", ttl: int | None = None) -> str | None:
    """None if the token is invalid, was made for another purpose, or is older than `ttl` seconds."""
    try:
        return _fernet(get_settings().secret_key, purpose).decrypt(token.encode(), ttl=ttl).decode()
    except (InvalidToken, ValueError):
        return None
