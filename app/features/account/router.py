"""The signed-in user's own profile, password and sessions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, SessionPrincipal
from app.core.security import hash_password, password_policy_error, verify_password
from app.db.base import utcnow
from app.features.account.schemas import PasswordChange, ProfileUpdate, SessionOut
from app.features.audit import service as audit
from app.features.auth.models import UserSession
from app.features.auth.sessions import revoke_user_sessions
from app.features.users.models import User
from app.features.users.schemas import UserOut, user_out

router = APIRouter(prefix="/me", tags=["me"])


def _require_real_user(principal: SessionPrincipal) -> User:
    if principal.user is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Not available while authentication is bypassed.",
        )
    return principal.user


@router.get("", response_model=UserOut)
def get_me(principal: SessionPrincipal) -> UserOut:
    return user_out(_require_real_user(principal))


@router.patch("", response_model=UserOut)
def update_me(payload: ProfileUpdate, request: Request, db: DbSession, principal: SessionPrincipal) -> UserOut:
    user = db.merge(_require_real_user(principal))
    user.name = payload.name
    user.updated_by = user.id
    audit.record(db, request, "user.profile_update", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    return user_out(user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChange, request: Request, db: DbSession, principal: SessionPrincipal) -> Response:
    user = db.merge(_require_real_user(principal))
    if not verify_password(user.password_hash, payload.current_password):
        audit.record(
            db,
            request,
            "user.password_change",
            actor=principal,
            outcome="failure",
            target_type="user",
            target_id=user.id,
        )
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if payload.new_password == payload.current_password:
        raise HTTPException(422, "Choose a password different from the current one.")
    if error := password_policy_error(payload.new_password, email=user.email, name=user.name):
        raise HTTPException(422, error)

    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    user.updated_by = user.id
    # Sign out every other device; keep the current session.
    revoke_user_sessions(db, user.id, keep_session_id=principal.session.id if principal.session else None)
    audit.record(db, request, "user.password_change", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sessions", response_model=list[SessionOut])
def list_my_sessions(db: DbSession, principal: SessionPrincipal) -> list[SessionOut]:
    user = _require_real_user(principal)
    rows = db.scalars(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.expires_at > utcnow())
        .order_by(UserSession.last_seen_at.desc())
    ).all()
    current_id = principal.session.id if principal.session else None
    return [SessionOut.model_validate(row).model_copy(update={"current": row.id == current_id}) for row in rows]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_my_session(session_id: str, request: Request, db: DbSession, principal: SessionPrincipal) -> Response:
    user = _require_real_user(principal)
    row = db.get(UserSession, session_id)
    # Same 404 whether it doesn't exist or belongs to someone else (no IDOR oracle).
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found.")
    db.delete(row)
    audit.record(db, request, "session.revoke", actor=principal, target_type="session", target_id=session_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
