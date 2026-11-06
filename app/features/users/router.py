"""User management. Requires the `users` page: Read to view, Write to change.

Privilege-escalation rules (OWASP A01), enforced on every change:
  * you can only assign roles whose permissions you hold yourself, and
  * you can only manage (edit, reset, unlock, delete) users whose current
    permissions you hold yourself,
so a limited user manager can never promote themselves or take over a stronger account.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, Principal, require_screen
from app.core.security import hash_password, password_policy_error
from app.db.base import utcnow
from app.features.audit import service as audit
from app.features.auth.sessions import revoke_user_sessions
from app.features.mfa import service as mfa
from app.features.rbac.models import Role, UserRole
from app.features.rbac.service import compute_permissions, permissions_for_roles
from app.features.users.models import User
from app.features.users.schemas import PasswordReset, UserCreate, UserOut, UsersPage, UserUpdate, user_out

router = APIRouter(prefix="/users", tags=["users"])

CanRead = Depends(require_screen("users"))
CanWrite = Depends(require_screen("users", write=True))


def _get_user(db: DbSession, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


def _active_admin_ids(db: DbSession) -> set[str]:
    """Active users holding the system Administrator role."""
    rows = db.scalars(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.is_system.is_(True), Role.is_active.is_(True), User.is_active.is_(True))
    )
    return set(rows)


def _guard_last_admin(db: DbSession, user: User) -> None:
    if _active_admin_ids(db) == {user.id}:
        raise HTTPException(status.HTTP_409_CONFLICT, "At least one active administrator is required.")


def _guard_self(principal: Principal, user: User, action: str) -> None:
    if principal.id == user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"You cannot {action} your own account.")


def _ensure_can_manage(db: DbSession, principal: Principal, target: User) -> None:
    if principal.id != target.id and not principal.permissions.covers(compute_permissions(db, target)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot manage a user with more access than you have.")


def _load_roles(db: DbSession, principal: Principal, role_ids: list[int]) -> list[Role]:
    """Validate an ordered role id list and return the roles in that order."""
    if len(set(role_ids)) != len(role_ids):
        raise HTTPException(422, "Each role can only be assigned once.")
    found = {r.id: r for r in db.scalars(select(Role).where(Role.id.in_(role_ids), Role.is_active.is_(True)))}
    if len(found) != len(role_ids):
        raise HTTPException(422, "One or more roles do not exist or are inactive.")
    roles = [found[i] for i in role_ids]
    if not principal.permissions.covers(permissions_for_roles(db, roles)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot assign roles with more access than you have.")
    return roles


def _set_roles(db: DbSession, user: User, roles: list[Role], principal: Principal) -> None:
    # Delete + flush first: the (user_id, role_id) and (user_id, sort_order) unique
    # constraints would otherwise clash with the rows being replaced.
    db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    db.flush()
    db.expire(user, ["role_links"])
    for position, role in enumerate(roles, start=1):
        db.add(UserRole(user_id=user.id, role_id=role.id, sort_order=position, created_by=principal.id))
    db.flush()
    db.expire(user, ["role_links"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("", response_model=UsersPage)
def list_users(
    db: DbSession,
    _: Principal = CanRead,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role_id: Annotated[int | None, Query(ge=1)] = None,
    state: Literal["active", "inactive", "locked"] | None = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> UsersPage:
    stmt = select(User)
    if q:
        pattern = f"%{_escape_like(q.strip().lower())}%"
        stmt = stmt.where(
            func.lower(User.email).like(pattern, escape="\\") | func.lower(User.name).like(pattern, escape="\\")
        )
    if role_id:
        stmt = stmt.where(User.id.in_(select(UserRole.user_id).where(UserRole.role_id == role_id)))
    if state == "active":
        stmt = stmt.where(User.is_active.is_(True))
    elif state == "inactive":
        stmt = stmt.where(User.is_active.is_(False))
    elif state == "locked":
        stmt = stmt.where(User.locked_until > utcnow())

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.created_at.asc()).offset((page - 1) * page_size).limit(page_size)).all()
    return UsersPage(items=[user_out(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, request: Request, db: DbSession, principal: Principal = CanWrite) -> UserOut:
    if error := password_policy_error(payload.password, email=payload.email, name=payload.name):
        raise HTTPException(422, error)
    roles = _load_roles(db, principal, payload.role_ids)
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        must_change_password=payload.must_change_password,
        created_by=principal.id,
        updated_by=principal.id,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this e-mail already exists.") from None
    _set_roles(db, user, roles, principal)
    audit.record(
        db,
        request,
        "user.create",
        actor=principal,
        target_type="user",
        target_id=user.id,
        detail={"email": user.email, "roles": [r.name for r in roles]},
    )
    db.commit()
    return user_out(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, db: DbSession, _: Principal = CanRead) -> UserOut:
    return user_out(_get_user(db, user_id))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str, payload: UserUpdate, request: Request, db: DbSession, principal: Principal = CanWrite
) -> UserOut:
    user = _get_user(db, user_id)
    _ensure_can_manage(db, principal, user)
    changes: dict[str, object] = {}

    if payload.name is not None and payload.name != user.name:
        changes["name"] = payload.name
        user.name = payload.name

    if payload.is_active is not None and payload.is_active != user.is_active:
        _guard_self(principal, user, "deactivate")
        if not payload.is_active and user.id in _active_admin_ids(db):
            _guard_last_admin(db, user)
        changes["is_active"] = payload.is_active
        user.is_active = payload.is_active
        if not payload.is_active:
            revoke_user_sessions(db, user.id)

    if payload.role_ids is not None and payload.role_ids != [r.id for r in user.roles]:
        _guard_self(principal, user, "change the roles of")
        roles = _load_roles(db, principal, payload.role_ids)
        if user.id in _active_admin_ids(db) and not any(r.is_system for r in roles):
            _guard_last_admin(db, user)
        _set_roles(db, user, roles, principal)
        changes["roles"] = [r.name for r in roles]
        # Privilege change: force re-authentication everywhere.
        revoke_user_sessions(db, user.id)

    if changes:
        user.updated_by = principal.id
        audit.record(db, request, "user.update", actor=principal, target_type="user", target_id=user.id, detail=changes)
        db.commit()
    return user_out(user)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: str, payload: PasswordReset, request: Request, db: DbSession, principal: Principal = CanWrite
) -> Response:
    user = _get_user(db, user_id)
    _guard_self(principal, user, "reset the password of (use Settings)")
    _ensure_can_manage(db, principal, user)
    if error := password_policy_error(payload.new_password, email=user.email, name=user.name):
        raise HTTPException(422, error)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = payload.must_change_password
    user.updated_by = principal.id
    user.failed_login_count = 0
    user.locked_until = None
    revoke_user_sessions(db, user.id)
    audit.record(db, request, "user.password_reset", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/unlock", response_model=UserOut)
def unlock_user(user_id: str, request: Request, db: DbSession, principal: Principal = CanWrite) -> UserOut:
    user = _get_user(db, user_id)
    _ensure_can_manage(db, principal, user)
    user.failed_login_count = 0
    user.locked_until = None
    user.updated_by = principal.id
    audit.record(db, request, "user.unlock", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    return user_out(user)


@router.post("/{user_id}/sessions/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_sessions(user_id: str, request: Request, db: DbSession, principal: Principal = CanWrite) -> Response:
    user = _get_user(db, user_id)
    _ensure_can_manage(db, principal, user)
    keep = principal.session.id if principal.session and principal.id == user.id else None
    revoke_user_sessions(db, user.id, keep_session_id=keep)
    audit.record(db, request, "user.sessions_revoke", actor=principal, target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/mfa/reset", response_model=UserOut)
def reset_mfa(user_id: str, request: Request, db: DbSession, principal: Principal = CanWrite) -> UserOut:
    """For a user who lost their phone and recovery codes. They sign in with their
    password afterwards and can enrol again in Settings."""
    user = _get_user(db, user_id)
    _guard_self(principal, user, "reset two-factor for (use Settings)")
    _ensure_can_manage(db, principal, user)
    if user.mfa_method:
        mfa.clear_mfa(user)
        user.updated_by = principal.id
        revoke_user_sessions(db, user.id)
        audit.record(db, request, "user.mfa_reset", actor=principal, target_type="user", target_id=user.id)
        db.commit()
    return user_out(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, request: Request, db: DbSession, principal: Principal = CanWrite) -> Response:
    user = _get_user(db, user_id)
    _guard_self(principal, user, "delete")
    _ensure_can_manage(db, principal, user)
    if user.id in _active_admin_ids(db):
        _guard_last_admin(db, user)
    audit.record(
        db,
        request,
        "user.delete",
        actor=principal,
        target_type="user",
        target_id=user.id,
        detail={"email": user.email},
    )
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
