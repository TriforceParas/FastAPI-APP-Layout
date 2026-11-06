"""Pydantic request/response models for the dashboard feature (request models inherit Strict)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.features.audit.schemas import AuditEventOut


class DashboardSummary(BaseModel):
    """Each group is present only if the user may read that dashboard feature."""

    users_total: int | None = None  # dashboard.user_stats
    users_active: int | None = None
    admins: int | None = None
    users_locked: int | None = None  # dashboard.locked_accounts
    sessions_active: int | None = None  # dashboard.active_sessions
    my_sessions: int | None = None
    my_last_login_at: datetime | None = None
    recent_events: list[AuditEventOut] | None = None  # dashboard.recent_activity
