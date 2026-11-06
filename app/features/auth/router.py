from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.deps import BYPASS_PRINCIPAL, DbSession, OptionalPrincipal
from app.api.schemas import Message
from app.core.auth_mode import auth_bypass_active
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    password_needs_rehash,
    password_policy_error,
    safe_equals,
    verify_password,
)
from app.db.base import utcnow
from app.features.audit import service as audit
from app.features.auth.microsoft import sso_available
from app.features.auth.models import PasswordReset
from app.features.auth.schemas import (
    AuthResult,
    AuthStatus,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MfaResendRequest,
    MfaVerifyRequest,
    PermissionOut,
    ResetPasswordRequest,
    SetupRequest,
)
from app.features.auth.sessions import (
    clear_session_cookie,
    create_session,
    revoke_user_sessions,
    set_csrf_cookie,
    set_session_cookies,
)
from app.features.auth.setup_token import current_setup_token, discard_setup_token
from app.features.mfa import service as mfa
from app.features.rbac.models import Role, UserRole
from app.features.system.models import SystemFlag
from app.features.users.models import User
from app.features.users.schemas import RoleBrief, UserOut, user_out
from app.integrations import turnstile
from app.integrations.mail import render, send_safely

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_LOGIN = "Invalid email or password, or the account is temporarily locked."


def _bypass_user_out() -> UserOut:
    p = BYPASS_PRINCIPAL
    return UserOut(
        id="auth-bypass",
        email=p.email,
        name=p.name,
        roles=[RoleBrief(id=0, name="Auth bypass")],
        is_active=True,
        must_change_password=False,
    )


def setup_required(db: DbSession) -> bool:
    return (db.scalar(select(func.count()).select_from(User)) or 0) == 0


@router.get("/status", response_model=AuthStatus)
def auth_status(request: Request, response: Response, db: DbSession, principal: OptionalPrincipal) -> AuthStatus:
    """Bootstrap call for the SPA. Also issues the CSRF cookie that every
    state-changing request must echo back in `X-CSRF-Token`."""
    settings = get_settings()
    if principal and principal.session:
        csrf = principal.session.csrf_token
    else:
        csrf = request.cookies.get(settings.csrf_cookie_name) or new_token()
    set_csrf_cookie(response, csrf)

    user = None
    permissions: dict[str, PermissionOut] = {}
    landing_path = None
    if principal:
        user = _bypass_user_out() if principal.is_bypass else user_out(principal.user)  # type: ignore[arg-type]
        permissions = {k: PermissionOut(**v) for k, v in principal.permissions.as_dict().items()}
        landing_path = principal.permissions.landing_path
    turnstile_on = settings.turnstile_enabled and not auth_bypass_active()
    return AuthStatus(
        app_name=settings.app_name,
        app_tagline=settings.app_tagline,
        environment=settings.app_env,
        auth_enabled=not auth_bypass_active(),
        auth_bypass=auth_bypass_active(),
        setup_required=setup_required(db),
        setup_token_required=bool(settings.setup_token_required),
        turnstile_enabled=turnstile_on,
        turnstile_site_key=settings.turnstile_site_key if turnstile_on else None,
        mail_enabled=settings.mail_enabled,
        microsoft_sso_enabled=sso_available(),
        csrf_token=csrf,
        user=user,
        permissions=permissions,
        landing_path=landing_path,
    )


@router.post(
    "/setup",
    response_model=AuthResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("setup", 5, 60))],
)
def initial_setup(payload: SetupRequest, request: Request, response: Response, db: DbSession) -> AuthResult:
    """Create the first administrator. Only works while no users exist."""
    if not setup_required(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup has already been completed.")

    turnstile.verify_or_raise(request, payload.turnstile_token, action="setup")

    settings = get_settings()
    if settings.setup_token_required and not safe_equals(payload.setup_token, current_setup_token()):
        audit.record(db, request, "auth.setup", actor_email=payload.email, outcome="denied")
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid setup token.")

    if error := password_policy_error(payload.password, email=payload.email, name=payload.name):
        raise HTTPException(422, error)

    admin_role = db.scalar(select(Role).where(Role.is_system.is_(True)))
    if admin_role is None:  # ensure_roles() runs at startup; this is a safety net
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Roles are not initialised.")

    now = utcnow()
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        last_login_at=now,
    )
    db.add(SystemFlag(flag_key="setup_completed"))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup has already been completed.") from None
    db.add(UserRole(user_id=user.id, role_id=admin_role.id, sort_order=1))
    db.flush()
    db.refresh(user)

    session, raw = create_session(db, user, request)
    audit.record(db, request, "auth.setup", actor_email=user.email, target_type="user", target_id=user.id)
    db.commit()
    discard_setup_token()

    set_session_cookies(response, raw, session.csrf_token)
    return AuthResult(user=user_out(user), csrf_token=session.csrf_token)


def _register_failure(db: DbSession, request: Request, user: User | None, email: str) -> None:
    """Failed password OR failed 2FA code: both count towards the same lockout."""
    settings = get_settings()
    now = utcnow()
    if user is not None and user.is_active and not user.locked_at(now):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
            audit.record(
                db,
                request,
                "auth.lockout",
                actor_email=user.email,
                outcome="failure",
                target_type="user",
                target_id=user.id,
            )
    audit.record(db, request, "auth.login", actor_email=email, outcome="failure")


def _complete_login(
    db: DbSession, request: Request, response: Response, user: User, detail: dict | None = None
) -> LoginResponse:
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    # A fresh session (new token) on every login prevents session fixation.
    session, raw = create_session(db, user, request)
    audit.record(
        db, request, "auth.login", actor_email=user.email, target_type="user", target_id=user.id, detail=detail
    )
    db.commit()
    set_session_cookies(response, raw, session.csrf_token)
    return LoginResponse(user=user_out(user), csrf_token=session.csrf_token)


@router.post(
    "/login",
    response_model=LoginResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(rate_limit("login", 10, 60))],
)
def login(
    payload: LoginRequest, request: Request, response: Response, background: BackgroundTasks, db: DbSession
) -> LoginResponse:
    turnstile.verify_or_raise(request, payload.turnstile_token, action="login")

    user = db.scalar(select(User).where(User.email == payload.email))
    now = utcnow()

    # Always run a hash verification so timing does not reveal whether the
    # account exists.
    password_ok = verify_password(user.password_hash if user else None, payload.password)

    if user is None or not user.is_active or user.locked_at(now) or not password_ok:
        _register_failure(db, request, user, payload.email)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    if user.mfa_method:
        # Second step. The failure counter is NOT reset until the code is correct,
        # so knowing the password does not allow unlimited code guesses.
        challenge, raw, code = mfa.create_challenge(db, user, purpose="login", method=user.mfa_method, request=request)
        audit.record(
            db, request, "auth.mfa_challenge", actor_email=user.email, target_type="user", target_id=user.id,
            detail={"method": user.mfa_method},
        )  # fmt: skip
        db.commit()
        if code and get_settings().mail_enabled:
            background.add_task(send_safely, mfa.code_email(user, code, purpose="login"))
        return LoginResponse(
            mfa_required=True,
            mfa_method=challenge.method,
            challenge_token=raw,
            destination_hint=mfa.mask_email(user.email) if challenge.method == "email" else None,
        )
    return _complete_login(db, request, response, user)


@router.post(
    "/login/verify",
    response_model=LoginResponse,
    response_model_exclude_none=True,
    dependencies=[Depends(rate_limit("mfa_verify", 10, 60))],
)
def verify_login(payload: MfaVerifyRequest, request: Request, response: Response, db: DbSession) -> LoginResponse:
    challenge = mfa.find_challenge(db, payload.challenge_token, "login")
    if challenge is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This sign-in attempt has expired. Please sign in again.")
    user = challenge.user
    if not user.is_active or user.locked_at() or not user.mfa_method:
        challenge.consumed_at = utcnow()
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_LOGIN)

    used = mfa.verify_login_code(user, challenge, payload.code)
    if used is None:
        challenge.attempts += 1
        _register_failure(db, request, user, user.email)
        exhausted = challenge.attempts >= mfa.MAX_ATTEMPTS or user.locked_at()
        if exhausted:
            challenge.consumed_at = utcnow()
        db.commit()
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Too many attempts. Please sign in again." if exhausted else "That code is not correct.",
        )

    challenge.consumed_at = utcnow()
    return _complete_login(
        db, request, response, user, detail={"mfa": challenge.method, "recovery_code": used == "recovery"}
    )


@router.post("/login/resend", response_model=Message, dependencies=[Depends(rate_limit("mfa_resend", 5, 60))])
def resend_login_code(payload: MfaResendRequest, background: BackgroundTasks, db: DbSession) -> Message:
    challenge = mfa.find_challenge(db, payload.challenge_token, "login")
    if challenge is None or challenge.method != "email":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This sign-in attempt has expired. Please sign in again.")
    result = mfa.resend_code(challenge)
    if isinstance(result, int):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Please wait before requesting another code.",
            headers={"Retry-After": str(result)},
        )
    db.commit()
    if get_settings().mail_enabled:
        background.add_task(send_safely, mfa.code_email(challenge.user, result, purpose="login"))
    return Message(detail="We sent a new code.")


# --- Forgot / reset password ----------------------------------------------------------

FORGOT_REPLY = "If an account exists for that address, we have emailed a link to reset the password."


@router.post(
    "/password/forgot",
    response_model=Message,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("password_forgot", 5, 900))],
)
def forgot_password(
    payload: ForgotPasswordRequest, request: Request, background: BackgroundTasks, db: DbSession
) -> Message:
    """Always gives the same answer, so it cannot be used to find out which
    e-mail addresses have accounts. The email is sent in the background."""
    settings = get_settings()
    if not settings.mail_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Password reset by email is not available.")
    turnstile.verify_or_raise(request, payload.turnstile_token, action="forgot")

    now = utcnow()
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active:
        audit.record(db, request, "auth.password_reset_request", actor_email=payload.email, outcome="failure")
        db.commit()
        return Message(detail=FORGOT_REPLY)

    recent = db.scalar(
        select(PasswordReset).where(
            PasswordReset.user_id == user.id, PasswordReset.created_at > now - timedelta(seconds=60)
        )
    )
    if recent is None:  # at most one email per minute per account
        db.execute(
            update(PasswordReset)
            .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
            .values(used_at=now)  # only the newest link works
        )
        raw = new_token()
        db.add(
            PasswordReset(
                user_id=user.id,
                token_hash=hash_token(raw),
                expires_at=now + timedelta(minutes=settings.password_reset_minutes),
                ip_address=request.client.host if request.client else None,
            )
        )
        audit.record(
            db, request, "auth.password_reset_request", actor_email=user.email, target_type="user", target_id=user.id
        )
        db.commit()
        link = f"{settings.public_url}/reset-password?token={raw}"
        background.add_task(
            send_safely,
            render(
                user.email,
                "Reset your password",
                greeting=f"Hi {user.name},",
                lines=[
                    "We received a request to reset your password.",
                    f"This link works once and expires in {settings.password_reset_minutes} minutes.",
                ],
                action=("Choose a new password", link),
            ),
        )
    return Message(detail=FORGOT_REPLY)


@router.post("/password/reset", response_model=Message, dependencies=[Depends(rate_limit("password_reset", 10, 60))])
def reset_password_with_token(
    payload: ResetPasswordRequest, request: Request, background: BackgroundTasks, db: DbSession
) -> Message:
    now = utcnow()
    row = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == hash_token(payload.token)))
    if row is None or row.used_at is not None or row.expires_at <= now or not row.user.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired. Request a new one."
        )
    user = row.user
    if error := password_policy_error(payload.new_password, email=user.email, name=user.name):
        raise HTTPException(422, error)

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_by = user.id
    db.execute(
        update(PasswordReset)
        .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
        .values(used_at=now)
    )
    revoke_user_sessions(db, user.id)  # sign out everywhere
    audit.record(
        db, request, "user.password_reset_by_email", actor_email=user.email, target_type="user", target_id=user.id
    )
    db.commit()
    background.add_task(send_safely, mfa.security_notice(user, "Your password was just reset using a reset link."))
    # Two-factor still applies: the user signs in normally next.
    return Message(detail="Your password has been reset. You can now sign in.")


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession, principal: OptionalPrincipal) -> dict[str, str]:
    if principal and principal.session:
        audit.record(db, request, "auth.logout", actor=principal)
        db.delete(principal.session)
        db.commit()
    clear_session_cookie(response)
    csrf = new_token()
    set_csrf_cookie(response, csrf)
    return {"csrf_token": csrf}
