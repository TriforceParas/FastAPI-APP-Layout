from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DbSession, Principal, require_screen
from app.features.audit.models import Event
from app.features.audit.schemas import AuditEventOut, AuditPage

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=AuditPage)
def list_audit_events(
    db: DbSession,
    _: Principal = Depends(require_screen("audit")),
    action: Annotated[str | None, Query(max_length=64, pattern=r"^[a-z_.]+$")] = None,
    outcome: Literal["success", "failure", "denied"] | None = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditPage:
    stmt = select(Event)
    if action:
        stmt = stmt.where(Event.action.startswith(action, autoescape=True))
    if outcome:
        stmt = stmt.where(Event.outcome == outcome)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Event.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return AuditPage(items=[AuditEventOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)
