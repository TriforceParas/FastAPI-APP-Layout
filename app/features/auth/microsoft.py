"""Sign in with Microsoft (Entra ID, OpenID Connect).

    GET /api/auth/microsoft/login     -> redirect to Microsoft
    GET /api/auth/microsoft/callback  -> validate, then redirect to the app

Who may sign in this way (all must hold):
  * the token is from the configured tenant (or MICROSOFT_SSO_ALLOWED_TENANT_IDS),
    and never from a personal Microsoft account,
  * the account's email domain is in MICROSOFT_SSO_ALLOWED_DOMAINS,
  * the account is linked to an active, unlocked user, or an existing user has that
    email (linked now, by tenant + object id), or MICROSOFT_SSO_AUTO_CREATE_ROLE
    is set (a new user with that role is created).
If the user turned on 2FA in Settings, they still enter their code afterwards.

Outcomes go back to the SPA in the URL: `/?sso_error=<code>` or, for the 2FA step,
`/#sso_mfa=<challenge>&method=..&hint=..` (a fragment never reaches servers or logs).
"""

from __future__ import annotations

import json
import logging
import secrets
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.core import crypto
from app.core.auth_mode import auth_bypass_active
from app.core.config import get_settings
from app.core.errors import ServiceUnavailable
from app.core.rate_limit import rate_limit
from app.core.security import hash_password, new_token, safe_equals
from app.db.base import utcnow
from app.features.audit import service as audit
from app.features.auth.models import UserIdentity
from app.features.auth.sessions import create_session, set_session_cookies
from app.features.mfa import service as mfa
from app.features.rbac.models import Role, UserRole
from app.features.users.models import User
from app.integrations import microsoft_oidc as oidc
from app.integrations.mail import send_safely

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/microsoft", tags=["auth"])

PROVIDER = "microsoft"
STATE_TTL_SECONDS = 600
_CRYPTO_PURPOSE = "oidc-state"


def sso_available() -> bool:
    return get_settings().microsoft_sso_enabled and not auth_bypass_active()


def _state_cookie_name() -> str:
    return "__Host-oidc" if get_settings().cookie_secure else "oidc"


def _redirect(location: str) -> RedirectResponse:
    response = RedirectResponse(location, status_code=status.HTTP_303_SEE_OTHER)
    # Single use: the state cookie goes whatever the outcome.
    response.delete_cookie(_state_cookie_name(), path="/", secure=bool(get_settings().cookie_secure), httponly=True)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/login", dependencies=[Depends(rate_limit("sso_login", 20, 60))])
def start_sign_in() -> RedirectResponse:
    if not sso_available():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Microsoft sign-in is not enabled.")
    state, nonce, verifier = new_token(), new_token(), secrets.token_urlsafe(48)
    response = RedirectResponse(
        oidc.authorization_url(state=state, nonce=nonce, code_verifier=verifier),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    response.set_cookie(
        _state_cookie_name(),
        crypto.encrypt(json.dumps({"s": state, "n": nonce, "v": verifier}), purpose=_CRYPTO_PURPOSE),
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=bool(settings.cookie_secure),
        # Lax (not Strict): Microsoft sends the browser back with a cross-site GET.
        samesite="lax",
        path="/",
    )
    return response


@router.get("/callback", dependencies=[Depends(rate_limit("sso_callback", 20, 60))])
def finish_sign_in(
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    code: str | None = Query(default=None, max_length=4096),
    state: str | None = Query(default=None, max_length=200),
    error: str | None = Query(default=None, max_length=100),
) -> RedirectResponse:
    if not sso_available():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Microsoft sign-in is not enabled.")
    settings = get_settings()

    def fail(reason: str, email: str | None = None, outcome: str = "failure") -> RedirectResponse:
        audit.record(
            db, request, "auth.login", actor_email=email, outcome=outcome, detail={"method": PROVIDER, "reason": reason}
        )
        db.commit()
        return _redirect(f"/?sso_error={reason}")

    raw_state = request.cookies.get(_state_cookie_name())
    saved = crypto.decrypt(raw_state, purpose=_CRYPTO_PURPOSE, ttl=STATE_TTL_SECONDS) if raw_state else None
    if saved is None:
        return fail("expired")  # no cookie (other browser, >10 min, or a forged callback)
    pending = json.loads(saved)
    if error:
        return fail("cancelled" if error == "access_denied" else "failed")
    if not code or not state or not safe_equals(state, pending["s"]):
        return fail("failed")

    try:
        identity = oidc.sign_in(code, code_verifier=pending["v"], nonce=pending["n"])
    except ServiceUnavailable:
        return fail("unavailable")
    except oidc.OidcError as exc:
        log.warning("Microsoft sign-in rejected: %s", exc)
        return fail("failed")

    # --- Policy ---------------------------------------------------------------------
    tenant_ok = identity.tenant_id != oidc.PERSONAL_ACCOUNTS_TENANT and (
        identity.tenant_id in settings.microsoft_sso_allowed_tenant_ids
        if settings.microsoft_sso_allowed_tenant_ids
        else (settings.sso_multi_tenant or identity.tenant_id == settings.sso_tenant_id)
    )
    if not tenant_ok:
        return fail("organisation_not_allowed", identity.email, "denied")
    if oidc.email_domain(identity.email) not in settings.microsoft_sso_allowed_domains:
        return fail("domain_not_allowed", identity.email, "denied")

    link = db.scalar(
        select(UserIdentity).where(
            UserIdentity.provider == PROVIDER,
            UserIdentity.tenant_id == identity.tenant_id,
            UserIdentity.subject == identity.object_id,
        )
    )
    user = link.user if link else db.scalar(select(User).where(User.email == identity.email))

    if user is None:
        if (db.scalar(select(func.count()).select_from(User)) or 0) == 0:
            return fail("no_account", identity.email)  # the first administrator is created by setup
        user = _auto_create(db, request, identity)
        if user is None:
            return fail("no_account", identity.email, "denied")

    if not user.is_active or user.locked_at():
        return fail("account_unavailable", identity.email, "denied")

    if link is None:
        existing = db.scalar(
            select(UserIdentity).where(UserIdentity.user_id == user.id, UserIdentity.provider == PROVIDER)
        )
        if existing is not None:
            # This user is already linked to a different Microsoft account.
            return fail("linked_elsewhere", identity.email, "denied")
        link = UserIdentity(
            user_id=user.id,
            provider=PROVIDER,
            tenant_id=identity.tenant_id,
            subject=identity.object_id,
            email=identity.email,
            created_by=user.id,
        )
        db.add(link)
        audit.record(
            db, request, "user.identity_link", actor_email=identity.email, target_type="user", target_id=user.id,
            detail={"provider": PROVIDER, "tenant_id": identity.tenant_id},
        )  # fmt: skip

    link.email = identity.email
    link.last_login_at = utcnow()

    if user.mfa_method:
        # The second step (the app's own 2FA) works exactly as after a password.
        challenge, raw, mfa_code = mfa.create_challenge(
            db, user, purpose="login", method=user.mfa_method, request=request
        )
        audit.record(
            db, request, "auth.mfa_challenge", actor_email=user.email, target_type="user", target_id=user.id,
            detail={"method": user.mfa_method, "via": PROVIDER},
        )  # fmt: skip
        db.commit()
        if mfa_code and settings.mail_enabled:
            background.add_task(send_safely, mfa.code_email(user, mfa_code, purpose="login"))
        fragment = f"sso_mfa={raw}&method={challenge.method}"
        if challenge.method == "email":
            fragment += f"&hint={quote(mfa.mask_email(user.email))}"
        return _redirect(f"/#{fragment}")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    session, raw_session = create_session(db, user, request)
    audit.record(
        db, request, "auth.login", actor_email=user.email, target_type="user", target_id=user.id,
        detail={"method": PROVIDER},
    )  # fmt: skip
    db.commit()
    response = _redirect("/")
    set_session_cookies(response, raw_session, session.csrf_token)
    return response


def _auto_create(db: DbSession, request: Request, identity: oidc.MicrosoftIdentity) -> User | None:
    role_name = get_settings().microsoft_sso_auto_create_role.strip()
    if not role_name:
        return None
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is None or role.is_system:
        log.error("MICROSOFT_SSO_AUTO_CREATE_ROLE %r is not an existing, non-administrator role", role_name)
        return None
    user = User(
        email=identity.email,
        name=identity.name,
        # Unusable random password: this account signs in with Microsoft (an admin
        # can still set a password later).
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id, sort_order=1))
    audit.record(
        db, request, "user.create", actor_email=identity.email, target_type="user", target_id=user.id,
        detail={"via": PROVIDER, "role": role.name},
    )  # fmt: skip
    db.flush()
    db.refresh(user)
    return user
