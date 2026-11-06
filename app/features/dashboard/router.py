"""Dashboard summary. Each group of numbers is a dashboard FEATURE with its own
permission (see app/features/rbac/registry.py); only the groups the user may read are returned."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DbSession, Principal, require_screen
from app.db.base import utcnow
from app.features.audit.models import Event
from app.features.audit.schemas import AuditEventOut
from app.features.auth.models import UserSession
from app.features.dashboard.schemas import DashboardSummary
from app.features.rbac.models import Role, UserRole
from app.features.users.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _count(db: DbSession, stmt) -> int:  # type: ignore[no-untyped-def]
    return db.scalar(stmt) or 0


@router.get("/summary", response_model=DashboardSummary)
def summary(db: DbSession, principal: Principal = Depends(require_screen("dashboard"))) -> DashboardSummary:
    now = utcnow()
    result = DashboardSummary()

    if principal.can("dashboard.user_stats"):
        users = select(func.count()).select_from(User)
        result.users_total = _count(db, users)
        result.users_active = _count(db, users.where(User.is_active.is_(True)))
        result.admins = _count(
            db,
            select(func.count(func.distinct(UserRole.user_id)))
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.is_system.is_(True)),
        )

    if principal.can("dashboard.locked_accounts"):
        result.users_locked = _count(db, select(func.count()).select_from(User).where(User.locked_until > now))

    if principal.can("dashboard.active_sessions"):
        result.sessions_active = _count(
            db, select(func.count()).select_from(UserSession).where(UserSession.expires_at > now)
        )
        result.my_sessions = _count(
            db,
            select(func.count())
            .select_from(UserSession)
            .where(UserSession.user_id == principal.id, UserSession.expires_at > now),
        )
        result.my_last_login_at = principal.user.last_login_at if principal.user else None

    if principal.can("dashboard.recent_activity"):
        stmt = select(Event).order_by(Event.id.desc()).limit(8)
        if not principal.can("audit"):  # without the Audit log page you only see your own events
            # Sign-in events carry the actor's e-mail but no id, so match on either.
            stmt = stmt.where((Event.actor_id == principal.id) | (Event.actor_email == principal.email))
        result.recent_events = [AuditEventOut.model_validate(e) for e in db.scalars(stmt).all()]
    return result
