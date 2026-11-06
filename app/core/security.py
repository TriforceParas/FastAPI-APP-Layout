"""Password hashing, token generation and password policy.

- Passwords: Argon2id (argon2-cffi defaults follow RFC 9106 / OWASP guidance).
- Session tokens: 256-bit random values; only an HMAC-SHA256 digest is stored,
  so a database leak does not yield usable session cookies.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHasher()
# Verified against when the account does not exist, so response timing does
# not reveal which e-mail addresses are registered.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(24))

# A small deny-list of the most common passwords. Swap in a larger list
# (e.g. a breached-password corpus) for higher assurance.
_COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "password1234",
        "password12345",
        "passwordpassword",
        "qwertyuiopas",
        "qwerty123456",
        "iloveyou1234",
        "letmein12345",
        "welcome12345",
        "adminadmin12",
        "administrator",
        "changeme1234",
        "aaaaaaaaaaaa",
        "111111111111",
        "abcdefghijkl",
        "abc123456789",
    }
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and bool(password_hash)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def password_policy_error(password: str, *, email: str | None = None, name: str | None = None) -> str | None:
    """Return a human-readable reason the password is rejected, or None.

    Follows OWASP ASVS v5 §6.2: length-based, no composition rules, all
    characters allowed, and common/context-specific passwords rejected.
    """
    normalized = unicodedata.normalize("NFKC", password)
    if len(normalized) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if len(normalized) > PASSWORD_MAX_LENGTH:
        return f"Password must be at most {PASSWORD_MAX_LENGTH} characters."
    lowered = normalized.lower()
    if lowered in _COMMON_PASSWORDS or len(set(lowered)) <= 3:
        return "This password is too common or predictable."
    context = [email.split("@")[0] if email else "", name or ""]
    for item in context:
        item = item.strip().lower()
        if len(item) >= 4 and item in lowered:
            return "Password must not contain your name or e-mail address."
    return None


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def safe_equals(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return hmac.compare_digest(left.encode(), right.encode())
