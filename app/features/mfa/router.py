"""Two-factor settings for the signed-in user (outside RBAC, like the rest of /api/me).

Every change re-checks the current password, is audited, signs out the user's
OTHER sessions, and sends a security notice by email (when email is enabled).
"""

from __future__ import annotations

import segno
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.api.deps import DbSession, SessionPrincipal
from app.api.schemas import Message
from app.core import totp
from app.core.config import get_settings
from app.core.crypto import encrypt
from app.core.rate_limit import rate_limit
from app.core.security import verify_password
from app.db.base import utcnow
from app.features.audit import service as audit
from app.features.auth.sessions import revoke_user_sessions
from app.features.mfa import service as mfa
from app.features.mfa.schemas import (
    CurrentPassword,
    EmailEnrollment,
    MfaConfirmRequest,
    MfaStatus,
    RecoveryCodes,
    TotpEnrollment,
)
from app.features.users.models import User
from app.integrations.mail import send_safely

router = APIRouter(prefix="/me/mfa", tags=["me"], dependencies=[Depends(rate_limit("mfa_settings", 20, 60))])

METHOD_LABEL = {"totp": "an authenticator app", "email": "email codes"}


def _user(principal: SessionPrincipal) -> User:
    if principal.user is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not available while authentication is bypassed.")
    return principal.user


def _check_password(db: DbSession, request: Request, principal: SessionPrincipal, user: User, password: str) -> None:
    if not verify_password(user.password_hash, password):
        audit.record(
            db, request, "user.mfa_change", actor=principal, outcome="failure", target_type="user", target_id=user.id
        )
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")


def _status(user: User) -> MfaStatus:
    return MfaStatus(
        method=user.mfa_method,
        enabled_at=user.mfa_enabled_at,
        recovery_codes_remaining=len(user.mfa_recovery_hashes or []),
        email_available=get_settings().mail_enabled,
    )


@router.get("", response_model=MfaStatus)
def get_status(principal: SessionPrincipal) -> MfaStatus:
    return _status(_user(principal))


@router.post("/totp/start", response_model=TotpEnrollment)
def start_totp(
    payload: CurrentPassword, request: Request, db: DbSession, principal: SessionPrincipal
) -> TotpEnrollment:
    user = _user(principal)
    _check_password(db, request, principal, user, payload.current_password)
    secret = totp.new_secret()
    _, raw, _ = mfa.create_challenge(
        db, user, purpose="enroll", method="totp", request=request, secret_encrypted=encrypt(secret)
    )
    db.commit()
    settings = get_settings()
    uri = totp.provisioning_uri(secret, user.email, settings.mfa_issuer or settings.app_name)
    qr = segno.make(uri, error="m").svg_data_uri(scale=5, border=2, dark="#111111", light="#ffffff")
    return TotpEnrollment(challenge_token=raw, secret=secret, otpauth_uri=uri, qr_code=qr)


@router.post("/email/start", response_model=EmailEnrollment)
def start_email(
    payload: CurrentPassword,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    principal: SessionPrincipal,
) -> EmailEnrollment:
    user = _user(principal)
    if not get_settings().mail_enabled:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Email is not configured on this server. Use an authenticator app."
        )
    _check_password(db, request, principal, user, payload.current_password)
    _, raw, code = mfa.create_challenge(db, user, purpose="enroll", method="email", request=request)
    db.commit()
    background.add_task(send_safely, mfa.code_email(user, code or "", purpose="enroll"))
    return EmailEnrollment(challenge_token=raw, destination_hint=mfa.mask_email(user.email))


@router.post("/confirm", response_model=RecoveryCodes)
def confirm(
    payload: MfaConfirmRequest,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    principal: SessionPrincipal,
) -> RecoveryCodes:
    user = _user(principal)
    challenge = mfa.find_challenge(db, payload.challenge_token, "enroll")
    if challenge is None or challenge.user_id != user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This setup has expired. Please start again.")
    result = mfa.verify_enrollment_code(challenge, payload.code)
    if result is False:
        challenge.attempts += 1
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code is not correct.")

    challenge.consumed_at = utcnow()
    user.mfa_method = challenge.method
    user.mfa_secret_encrypted = challenge.secret_encrypted if challenge.method == "totp" else None
    # verify_enrollment_code returns the matched TOTP step (int) or True (email); bool is an int subclass.
    user.mfa_totp_last_step = result if challenge.method == "totp" and not isinstance(result, bool) else None
    user.mfa_enabled_at = utcnow()
    user.updated_by = user.id
    codes = mfa.issue_recovery_codes(user)
    revoke_user_sessions(db, user.id, keep_session_id=principal.session.id if principal.session else None)
    audit.record(
        db, request, "user.mfa_enable", actor=principal, target_type="user", target_id=user.id,
        detail={"method": challenge.method},
    )  # fmt: skip
    db.commit()
    background.add_task(
        send_safely,
        mfa.security_notice(user, f"Two-factor authentication was turned on using {METHOD_LABEL[challenge.method]}."),
    )
    return RecoveryCodes(recovery_codes=codes)


@router.post("/recovery-codes", response_model=RecoveryCodes)
def regenerate_recovery_codes(
    payload: CurrentPassword, request: Request, db: DbSession, principal: SessionPrincipal
) -> RecoveryCodes:
    user = _user(principal)
    if not user.mfa_method:
        raise HTTPException(status.HTTP_409_CONFLICT, "Two-factor authentication is not turned on.")
    _check_password(db, request, principal, user, payload.current_password)
    codes = mfa.issue_recovery_codes(user)  # old codes stop working
    audit.record(db, request, "user.mfa_recovery_codes", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    return RecoveryCodes(recovery_codes=codes)


@router.post("/disable", response_model=Message)
def disable(
    payload: CurrentPassword,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    principal: SessionPrincipal,
) -> Message:
    user = _user(principal)
    if not user.mfa_method:
        return Message(detail="Two-factor authentication is already off.")
    _check_password(db, request, principal, user, payload.current_password)
    mfa.clear_mfa(user)
    user.updated_by = user.id
    revoke_user_sessions(db, user.id, keep_session_id=principal.session.id if principal.session else None)
    audit.record(db, request, "user.mfa_disable", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    background.add_task(send_safely, mfa.security_notice(user, "Two-factor authentication was turned off."))
    return Message(detail="Two-factor authentication is now off.")
