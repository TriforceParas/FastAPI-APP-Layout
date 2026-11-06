"""Server-side sessions. The browser holds an opaque random token in an
HttpOnly cookie; the database stores only its HMAC digest."""

from __future__ import annotations

from datetime import timedelta

from fastapi import Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.request_info import client_ip, user_agent
from app.core.security import hash_token, new_token
from app.db.base import utcnow
from app.features.auth.models import UserSession
from app.features.users.models import User

_TOUCH_INTERVAL = timedelta(seconds=60)


def create_session(db: Session, user: User, request: Request) -> tuple[UserSession, str]:
    settings = get_settings()
    raw = new_token()
    now = utcnow()
    session = UserSession(
        token_hash=hash_token(raw),
        csrf_token=new_token(),
        user_id=user.id,
        created_by=user.id,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
    )
    db.add(session)
    return session, raw


def resolve_session(db: Session, raw_token: str) -> UserSession | None:
    """Return the live session for a cookie token, enforcing idle and
    absolute timeouts. Expired sessions are deleted on sight."""
    settings = get_settings()
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))
    if session is None:
        return None
    now = utcnow()
    idle_limit = session.last_seen_at + timedelta(minutes=settings.session_idle_minutes)
    if now >= session.expires_at or now >= idle_limit or not session.user.is_active:
        db.delete(session)
        db.commit()
        return None
    if now - session.last_seen_at >= _TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return session


def revoke_user_sessions(db: Session, user_id: str, *, keep_session_id: str | None = None) -> None:
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_session_id:
        stmt = stmt.where(UserSession.id != keep_session_id)
    db.execute(stmt)


def purge_expired_sessions(db: Session) -> int:
    settings = get_settings()
    now = utcnow()
    result = db.execute(
        delete(UserSession).where(
            (UserSession.expires_at <= now)
            | (UserSession.last_seen_at <= now - timedelta(minutes=settings.session_idle_minutes))
        )
    )
    db.commit()
    return result.rowcount or 0


# --- Cookies ---------------------------------------------------------------


def set_session_cookies(response: Response, raw_token: str, csrf_token: str) -> None:
    settings = get_settings()
    max_age = settings.session_absolute_hours * 3600
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=max_age,
        httponly=True,
        secure=bool(settings.cookie_secure),
        samesite="strict",
        path="/",
    )
    set_csrf_cookie(response, csrf_token, max_age=max_age)


def set_csrf_cookie(response: Response, csrf_token: str, *, max_age: int | None = None) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age or settings.session_absolute_hours * 3600,
        httponly=False,  # the SPA echoes it back in the X-CSRF-Token header
        secure=bool(settings.cookie_secure),
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=bool(settings.cookie_secure),
        httponly=True,
        samesite="strict",
    )
