"""Lookups: minimal id+label lists for dropdowns on pages that do not own the data.

A user may be allowed to use page B (e.g. the Users form) while having no access
to page A (e.g. Roles), yet B needs a dropdown of A's records. Never call A's
management endpoint and never widen the user's permissions: add a lookup here.

Rules (see AGENTS.md "Lookups"):
  * return ONLY `LookupItem` (id + label); never reuse the entity's full schema;
  * select only the columns needed, active records only, read-only, paginated;
  * register the consuming screens in LOOKUPS; a user needs Read on at least one.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import DbSession, Principal, require_user
from app.api.schemas import LookupItem
from app.features.rbac.models import Role

# lookup name -> screen keys (pages or features) that legitimately use it
LOOKUPS: dict[str, tuple[str, ...]] = {
    "roles": ("users",),  # the Users page assigns roles to users
}

router = APIRouter(prefix="/lookups", tags=["lookups"])


def require_lookup(name: str):  # type: ignore[no-untyped-def]
    consumers = LOOKUPS[name]

    def dependency(principal: Annotated[Principal, Depends(require_user)]) -> Principal:
        if not principal.permissions.can_any(consumers):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return principal

    dependency.__rbac_guard__ = {"kind": "lookup", "key": name}  # type: ignore[attr-defined]
    return dependency


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/roles", response_model=list[LookupItem])
def lookup_roles(
    db: DbSession,
    _: Principal = Depends(require_lookup("roles")),
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[LookupItem]:
    stmt = select(Role.id, Role.name).where(Role.is_active.is_(True))
    if q:
        stmt = stmt.where(func.lower(Role.name).like(f"%{_escape_like(q.strip().lower())}%", escape="\\"))
    rows = db.execute(stmt.order_by(Role.name).limit(limit)).all()
    return [LookupItem(id=row.id, label=row.name) for row in rows]
