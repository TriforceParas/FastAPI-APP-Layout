"""Optional two-factor authentication (chosen per user in Settings).

Methods
  totp   an authenticator app (RFC 6238). The seed is encrypted at rest and a
         code's time step can only be used once (replay protection).
  email  a 6-digit code emailed at sign-in (needs MAIL_PROVIDER != disabled).

Every enrolment also issues 10 single-use recovery codes (stored as HMACs) so a
lost phone or mailbox never locks the user out. An administrator can reset a
user's 2FA from the Users page.

Sign-in flow: password OK -> a short-lived *challenge* (opaque token, HMAC
stored) -> the user submits a code -> session. Failed codes count towards the
same lockout as failed passwords, so a known password does not allow unlimited
code guessing.
"""

from __future__ import annotations

import hmac
import secrets
from datetime import timedelta

from fastapi import Request
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core import totp
from app.core.config import get_settings
from app.core.crypto import decrypt
from app.core.request_info import client_ip
from app.core.security import hash_token, new_token
from app.db.base import utcnow
from app.features.auth.models import PasswordReset
from app.features.mfa.models import MfaChallenge
from app.features.users.models import User
from app.integrations.mail import Email, render

MAX_ATTEMPTS = 5
MAX_SENDS = 3
RESEND_SECONDS = 30
RECOVERY_CODE_COUNT = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o/1/l/i


def new_email_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    shown = local[:1] + "***" + (local[-1:] if len(local) > 2 else "")
    return f"{shown}@{domain}"


# --- Challenges ------------------------------------------------------------------


def create_challenge(
    db: Session,
    user: User,
    *,
    purpose: str,
    method: str,
    request: Request,
    secret_encrypted: str | None = None,
) -> tuple[MfaChallenge, str, str | None]:
    """Returns (challenge, raw token for the client, emailed code or None).
    Any earlier open challenge of the same purpose is closed first."""
    now = utcnow()
    db.execute(
        update(MfaChallenge)
        .where(MfaChallenge.user_id == user.id, MfaChallenge.purpose == purpose, MfaChallenge.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    raw = new_token()
    code = new_email_code() if method == "email" else None
    challenge = MfaChallenge(
        user_id=user.id,
        purpose=purpose,
        method=method,
        token_hash=hash_token(raw),
        code_hash=hash_token(code) if code else None,
        secret_encrypted=secret_encrypted,
        sends=1 if code else 0,
        last_sent_at=now if code else None,
        expires_at=now + timedelta(minutes=get_settings().mfa_code_minutes),
        ip_address=client_ip(request),
        created_by=user.id,
    )
    db.add(challenge)
    db.flush()
    return challenge, raw, code


def find_challenge(db: Session, raw_token: str, purpose: str) -> MfaChallenge | None:
    if not raw_token or len(raw_token) > 128:
        return None
    challenge = db.scalar(select(MfaChallenge).where(MfaChallenge.token_hash == hash_token(raw_token)))
    if (
        challenge is None
        or challenge.purpose != purpose
        or challenge.consumed_at is not None
        or challenge.expires_at <= utcnow()
        or challenge.attempts >= MAX_ATTEMPTS
    ):
        return None
    return challenge


def resend_code(challenge: MfaChallenge) -> str | int:
    """Returns the new code, or the number of seconds to wait."""
    now = utcnow()
    if challenge.sends >= MAX_SENDS:
        return RESEND_SECONDS * 10
    if challenge.last_sent_at and now - challenge.last_sent_at < timedelta(seconds=RESEND_SECONDS):
        return RESEND_SECONDS - int((now - challenge.last_sent_at).total_seconds())
    code = new_email_code()
    challenge.code_hash = hash_token(code)
    challenge.sends += 1
    challenge.last_sent_at = now
    return code


def _matches_email_code(challenge: MfaChallenge, code: str) -> bool:
    digits = "".join(ch for ch in code if ch.isdigit())
    return bool(challenge.code_hash) and hmac.compare_digest(hash_token(digits), challenge.code_hash or "")


def verify_login_code(user: User, challenge: MfaChallenge, code: str) -> str | None:
    """Check a sign-in code. Returns "code", "recovery" or None (failure).
    Updates replay / recovery state on the user on success."""
    if use_recovery_code(user, code):
        return "recovery"
    if challenge.method == "email":
        return "code" if _matches_email_code(challenge, code) else None
    secret = decrypt(user.mfa_secret_encrypted or "")
    if not secret:
        return None
    step = totp.verify(secret, code, last_step=user.mfa_totp_last_step)
    if step is None:
        return None
    user.mfa_totp_last_step = step
    return "code"


def verify_enrollment_code(challenge: MfaChallenge, code: str) -> int | bool:
    """For a new method: TOTP returns the matched step (int), email returns True."""
    if challenge.method == "email":
        return _matches_email_code(challenge, code)
    secret = decrypt(challenge.secret_encrypted or "")
    step = totp.verify(secret, code) if secret else None
    return step if step is not None else False


# --- Recovery codes --------------------------------------------------------------


def _normalize(code: str) -> str:
    return "".join(ch for ch in code.lower() if ch.isalnum())


def issue_recovery_codes(user: User) -> list[str]:
    codes = [
        "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))
        + "-"
        + "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))
        for _ in range(RECOVERY_CODE_COUNT)
    ]
    user.mfa_recovery_hashes = [hash_token(_normalize(c)) for c in codes]
    return codes


def use_recovery_code(user: User, code: str) -> bool:
    normalized = _normalize(code)
    if len(normalized) != 10 or not user.mfa_recovery_hashes:
        return False
    digest = hash_token(normalized)
    remaining = [h for h in user.mfa_recovery_hashes if not hmac.compare_digest(h, digest)]
    if len(remaining) == len(user.mfa_recovery_hashes):
        return False
    user.mfa_recovery_hashes = remaining  # single use
    return True


def clear_mfa(user: User) -> None:
    user.mfa_method = None
    user.mfa_secret_encrypted = None
    user.mfa_totp_last_step = None
    user.mfa_recovery_hashes = None
    user.mfa_enabled_at = None


def purge_expired(db: Session) -> None:
    now = utcnow()
    db.execute(delete(MfaChallenge).where(MfaChallenge.expires_at <= now - timedelta(days=1)))
    db.execute(delete(PasswordReset).where(PasswordReset.expires_at <= now - timedelta(days=7)))
    db.commit()


# --- Emails ------------------------------------------------------------------------


def code_email(user: User, code: str, *, purpose: str) -> Email:
    minutes = get_settings().mfa_code_minutes
    what = "sign in" if purpose == "login" else "turn on email verification codes"
    return render(
        user.email,
        "Your verification code",
        greeting=f"Hi {user.name},",
        lines=[f"Use this code to {what}. It expires in {minutes} minutes."],
        code=code,
        footer="If you did not try to sign in, change your password: someone may know it.",
    )


def security_notice(user: User, what: str) -> Email:
    return render(
        user.email,
        "Security change on your account",
        greeting=f"Hi {user.name},",
        lines=[what, "If this was you, no action is needed."],
        footer="If this was not you, reset your password immediately and contact your administrator.",
    )
