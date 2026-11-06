"""Imports every model so SQLAlchemy and Alembic see the full schema.

Add each new feature's models module here.
"""

from __future__ import annotations

from app.db.base import Base, UTCDateTime, new_id, utcnow  # noqa: F401
from app.features.audit.models import Event  # noqa: F401
from app.features.auth.models import PasswordReset, UserIdentity, UserSession  # noqa: F401
from app.features.mfa.models import MfaChallenge  # noqa: F401
from app.features.rbac.models import Role, RoleScreen, Screen, UserRole  # noqa: F401
from app.features.system.models import SystemFlag  # noqa: F401
from app.features.users.models import User  # noqa: F401

__all__ = [
    "utcnow",
    "new_id",
    "UTCDateTime",
    "Base",
    "User",
    "UserSession",
    "PasswordReset",
    "UserIdentity",
    "MfaChallenge",
    "Screen",
    "Role",
    "RoleScreen",
    "UserRole",
    "Event",
    "SystemFlag",
]
