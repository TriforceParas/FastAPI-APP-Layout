"""Authentication & authorization dependencies.

Use in routes:
    principal: Principal = Depends(require_user)                       # any signed-in user
    principal: Principal = Depends(require_screen("users"))            # needs Read on the page/feature
    principal: Principal = Depends(require_screen("users", write=True))  # needs Write

Keys are the screen keys from app/features/rbac/registry.py ("users", "dashboard.recent_activity").
`require_user` also enforces the per-session CSRF token on state-changing
requests, and blocks users who must change their password from everything
except /api/me and /api/auth. Settings and /api/me/* are outside RBAC: use
`SessionPrincipal` there.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth_mode import auth_bypass_active
from app.core.config import get_settings
from app.core.security import safe_equals
from app.db.session import get_db
from app.features.auth.models import UserSession
from app.features.auth.sessions import resolve_session
from app.features.rbac.service import Permissions, bypass_permissions, compute_permissions
from app.features.users.models import User

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DbSession = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class Principal:
    id: str | None
    email: str
    name: str
    must_change_password: bool = False
    is_bypass: bool = False
    user: User | None = None
    session: UserSession | None = None
    permissions: Permissions = field(default_factory=Permissions)

    def can(self, key: str, *, write: bool = False) -> bool:
        return self.permissions.can(key, write=write)


BYPASS_PRINCIPAL = Principal(
    id=None,
    email="auth-bypass@localhost",
    name="Developer (auth bypass)",
    is_bypass=True,
    permissions=bypass_permissions(),
)


def get_optional_principal(request: Request, db: DbSession) -> Principal | None:
    if auth_bypass_active():
        return BYPASS_PRINCIPAL
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token or len(token) > 128:
        return None
    session = resolve_session(db, token)
    if session is None:
        return None
    user = session.user
    return Principal(
        id=user.id,
        email=user.email,
        name=user.name,
        must_change_password=user.must_change_password,
        user=user,
        session=session,
        # Computed per request, so role changes take effect immediately.
        permissions=compute_permissions(db, user),
    )


OptionalPrincipal = Annotated[Principal | None, Depends(get_optional_principal)]


def require_session(request: Request, principal: OptionalPrincipal) -> Principal:
    if principal is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    if request.method not in SAFE_METHODS and principal.session is not None:
        # Bind CSRF token to the session (in addition to the double-submit
        # check in CSRFMiddleware).
        if not safe_equals(request.headers.get("x-csrf-token"), principal.session.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "csrf_failed")
    return principal


def require_user(principal: Annotated[Principal, Depends(require_session)]) -> Principal:
    if principal.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "password_change_required")
    return principal


# Markers read by tests/test_route_guards.py, which fails if any API route lacks a guard.
require_session.__rbac_guard__ = {"kind": "session"}  # type: ignore[attr-defined]
require_user.__rbac_guard__ = {"kind": "user"}  # type: ignore[attr-defined]


def require_screen(key: str, *, write: bool = False) -> Callable[..., Principal]:
    """Dependency factory: the user must hold Read (or Write) on this page/feature."""

    def dependency(principal: Annotated[Principal, Depends(require_user)]) -> Principal:
        if not principal.can(key, write=write):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return principal

    dependency.__rbac_guard__ = {"kind": "screen", "key": key, "write": write}  # type: ignore[attr-defined]
    return dependency


SessionPrincipal = Annotated[Principal, Depends(require_session)]
CurrentUser = Annotated[Principal, Depends(require_user)]
