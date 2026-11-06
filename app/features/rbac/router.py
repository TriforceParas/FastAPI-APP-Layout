"""Roles and the screen tree. Requires the `roles` page: Read to view, Write to change.

Rules enforced here (not just in the UI):
  * Write implies Read on every leaf; a role's landing page must be a PAGE it can open.
  * The system Administrator role cannot be edited or deleted.
  * You cannot grant, or edit a role containing, permissions you do not hold yourself.
  * A role that is still assigned to users cannot be deleted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, Principal, require_screen
from app.features.audit import service as audit
from app.features.rbac.models import Role, RoleScreen, Screen, UserRole
from app.features.rbac.schemas import AccessOut, RoleDetail, RoleOut, RoleWrite, ScreenOut
from app.features.rbac.service import Permissions, leaf_screens, permissions_for_roles

router = APIRouter(tags=["roles"])

CanRead = Depends(require_screen("roles"))
CanWrite = Depends(require_screen("roles", write=True))


def _screens(db: DbSession) -> list[Screen]:
    return list(db.scalars(select(Screen).where(Screen.is_active.is_(True)).order_by(Screen.sort_order, Screen.id)))


def _role_out(db: DbSession, role: Role) -> dict:
    count = db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)) or 0
    return {**RoleOut.model_validate(role).model_dump(), "user_count": count}


def _detail(db: DbSession, role: Role) -> RoleDetail:
    leaves = leaf_screens(_screens(db))
    have = {rs.screen_id: rs for rs in role.screens}
    access = [
        AccessOut(
            screen_id=leaf.id,
            can_read=bool(have[leaf.id].can_read) if leaf.id in have else False,
            can_write=bool(have[leaf.id].can_write) if leaf.id in have else False,
        )
        for leaf in leaves
    ]
    return RoleDetail(**_role_out(db, role), access=access)


def _get_role(db: DbSession, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Role not found.")
    return role


def _validated_access(db: DbSession, payload: RoleWrite) -> dict[int, tuple[bool, bool]]:
    leaves = {s.id: s for s in leaf_screens(_screens(db))}
    wanted: dict[int, tuple[bool, bool]] = {}
    for item in payload.access:
        if item.screen_id not in leaves:
            raise HTTPException(422, "Permissions can only be set on pages without features, or on features.")
        if item.screen_id in wanted:
            raise HTTPException(422, "Each screen can only appear once.")
        if item.can_write and not item.can_read:
            raise HTTPException(422, "Write access requires Read access.")
        wanted[item.screen_id] = (item.can_read, item.can_write)

    readable = {sid for sid, (r, _) in wanted.items() if r}
    if payload.default_screen_id is not None:
        page = next((s for s in _screens(db) if s.id == payload.default_screen_id), None)
        if page is None or page.parent_screen_id is not None:
            raise HTTPException(422, "The landing page must be a page.")
        kids = [s.id for s in _screens(db) if s.parent_screen_id == page.id]
        if not (readable & set(kids or [page.id])):
            raise HTTPException(422, "The landing page must be a page this role can open.")
    elif readable:
        raise HTTPException(422, "Choose a landing page for this role.")
    return wanted


def _granted_keys(db: DbSession, wanted: dict[int, tuple[bool, bool]]) -> dict[str, tuple[bool, bool]]:
    keys = {s.id: s.screen_key for s in _screens(db)}
    return {keys[sid]: rw for sid, rw in wanted.items() if sid in keys and (rw[0] or rw[1])}


def _guard_escalation(principal: Principal, requested: dict[str, tuple[bool, bool]]) -> None:
    if not principal.permissions.covers(Permissions(grants=requested)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot grant permissions you do not have yourself.")


def _apply(db: DbSession, role: Role, payload: RoleWrite, wanted: dict[int, tuple[bool, bool]]) -> None:
    role.name = payload.name
    role.description = payload.description
    role.default_screen_id = payload.default_screen_id
    db.execute(delete(RoleScreen).where(RoleScreen.role_id == role.id))
    db.flush()
    db.expire(role, ["screens"])
    for screen_id, (can_read, can_write) in wanted.items():
        db.add(RoleScreen(role_id=role.id, screen_id=screen_id, can_read=can_read, can_write=can_write))
    db.flush()
    db.expire(role, ["screens"])


@router.get("/screens", response_model=list[ScreenOut])
def list_screens(db: DbSession, _: Principal = CanRead) -> list[Screen]:
    return _screens(db)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: DbSession, _: Principal = CanRead) -> list[dict]:
    roles = db.scalars(select(Role).where(Role.is_active.is_(True)).order_by(Role.is_system.desc(), Role.name)).all()
    return [_role_out(db, r) for r in roles]


@router.get("/roles/{role_id}", response_model=RoleDetail)
def get_role(role_id: int, db: DbSession, _: Principal = CanRead) -> RoleDetail:
    return _detail(db, _get_role(db, role_id))


@router.post("/roles", response_model=RoleDetail, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleWrite, request: Request, db: DbSession, principal: Principal = CanWrite) -> RoleDetail:
    wanted = _validated_access(db, payload)
    _guard_escalation(principal, _granted_keys(db, wanted))
    role = Role(name=payload.name, created_by=principal.id, updated_by=principal.id)
    db.add(role)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A role with this name already exists.") from None
    _apply(db, role, payload, wanted)
    audit.record(
        db,
        request,
        "role.create",
        actor=principal,
        target_type="role",
        target_id=str(role.id),
        detail={"name": role.name, "permissions": sorted(_granted_keys(db, wanted))},
    )
    db.commit()
    return _detail(db, role)


@router.put("/roles/{role_id}", response_model=RoleDetail)
def update_role(
    role_id: int, payload: RoleWrite, request: Request, db: DbSession, principal: Principal = CanWrite
) -> RoleDetail:
    role = _get_role(db, role_id)
    if role.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "The system role cannot be edited.")
    # You may not edit a role that holds more than you do (it could be used to weaken or hijack it).
    if not principal.permissions.covers(permissions_for_roles(db, [role])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot edit a role with more access than you have.")

    wanted = _validated_access(db, payload)
    requested_keys = _granted_keys(db, wanted)
    _guard_escalation(principal, requested_keys)
    before = set(_granted_keys(db, {rs.screen_id: (rs.can_read, rs.can_write) for rs in role.screens}))

    role.updated_by = principal.id
    try:
        _apply(db, role, payload, wanted)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A role with this name already exists.") from None
    audit.record(
        db,
        request,
        "role.update",
        actor=principal,
        target_type="role",
        target_id=str(role.id),
        detail={
            "name": role.name,
            "added": sorted(set(requested_keys) - before),
            "removed": sorted(before - set(requested_keys)),
        },
    )
    db.commit()
    return _detail(db, role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, request: Request, db: DbSession, principal: Principal = CanWrite) -> Response:
    role = _get_role(db, role_id)
    if role.is_system:
        raise HTTPException(status.HTTP_409_CONFLICT, "The system role cannot be deleted.")
    if not principal.permissions.covers(permissions_for_roles(db, [role])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot delete a role with more access than you have.")
    if (db.scalar(select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)) or 0) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "This role is still assigned to users. Reassign them first.")
    audit.record(
        db,
        request,
        "role.delete",
        actor=principal,
        target_type="role",
        target_id=str(role.id),
        detail={"name": role.name},
    )
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
