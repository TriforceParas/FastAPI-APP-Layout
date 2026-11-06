"""The single source of truth for pages and features that role permissions
can be assigned to. Synced into md_screen at startup (see
app.features.rbac.service.sync_screens).

To add a page: append a ScreenDef here, add its route in frontend/src/app/App.tsx
and its sidebar entry in frontend/src/app/navigation.ts (same `key`).
To add a feature to a page: add a FeatureDef to that page and guard the
endpoint with `require_screen("<page>.<feature>")`.

Not part of RBAC (always available to every signed-in user): Settings and the
`/api/me/*` endpoints (own profile, password, sessions).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDef:
    key: str  # "<page>.<feature>"
    name: str
    description: str


@dataclass(frozen=True)
class ScreenDef:
    key: str
    name: str
    path: str
    description: str
    features: tuple[FeatureDef, ...] = ()


SCREENS: tuple[ScreenDef, ...] = (
    ScreenDef(
        "dashboard",
        "Dashboard",
        "/dashboard",
        "Overview and analytics",
        features=(
            FeatureDef("dashboard.user_stats", "User statistics", "Total, active and administrator counts"),
            FeatureDef("dashboard.active_sessions", "Active sessions", "Signed-in devices"),
            FeatureDef("dashboard.locked_accounts", "Locked accounts", "Accounts locked after failed sign-ins"),
            FeatureDef("dashboard.recent_activity", "Recent activity", "Latest security events"),
            FeatureDef("dashboard.quick_actions", "Quick actions", "Shortcuts to common tasks"),
        ),
    ),
    ScreenDef("users", "Users", "/users", "Create and manage accounts"),
    ScreenDef("roles", "Roles", "/roles", "Roles and page permissions"),
    ScreenDef("audit", "Audit log", "/audit", "Security and admin events"),
)

DEFAULT_LANDING_KEY = "dashboard"


def all_keys() -> list[str]:
    """Every permission key: pages and features."""
    keys: list[str] = []
    for page in SCREENS:
        keys.append(page.key)
        keys.extend(f.key for f in page.features)
    return keys
