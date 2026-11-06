"""Role-based access control.

Model (see db-naming-conventions skill for table names):
  md_screen        tree of pages and features (synced from app/features/rbac/registry.py)
  md_role          named sets of permissions (+ default landing page)
  map_role_screen  read/write per LEAF screen (a page's features, or a page with none)
  map_user_role    a user's roles, ordered: the FIRST role decides the landing page

Effective permissions are the UNION of all of a user's active roles. A page
that has features is "readable" if any feature is, and "writable" if any is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.rbac.models import Role, RoleScreen, Screen
from app.features.rbac.registry import DEFAULT_LANDING_KEY, SCREENS, all_keys
from app.features.system.models import SystemFlag
from app.features.users.models import User

ADMIN_ROLE_NAME = "Administrator"
MEMBER_ROLE_NAME = "Member"
# Features a freshly seeded "Member" role can read.
MEMBER_DEFAULT_KEYS = ("dashboard.active_sessions", "dashboard.recent_activity", "dashboard.quick_actions")


@dataclass(frozen=True)
class Permissions:
    """key -> (read, write), for pages AND features."""

    grants: dict[str, tuple[bool, bool]] = field(default_factory=dict)
    landing_path: str | None = None
    full: bool = False  # auth-bypass principal

    def can(self, key: str, *, write: bool = False) -> bool:
        if self.full:
            return True
        read_ok, write_ok = self.grants.get(key, (False, False))
        return write_ok if write else read_ok

    def can_any(self, keys: tuple[str, ...] | list[str]) -> bool:
        return any(self.can(key) for key in keys)

    def covers(self, other: Permissions) -> bool:
        """True if everything `other` can do, this can do too. Used to stop
        users granting or managing more access than they hold themselves."""
        if self.full:
            return True
        return all(
            self.can(key, write=False) and (not write_ok or self.can(key, write=True))
            for key, (read_ok, write_ok) in other.grants.items()
            if read_ok or write_ok
        )

    def as_dict(self) -> dict[str, dict[str, bool]]:
        return {key: {"read": r, "write": w} for key, (r, w) in self.grants.items()}


def bypass_permissions() -> Permissions:
    return Permissions(
        grants={key: (True, True) for key in all_keys()},
        landing_path=SCREENS[0].path,
        full=True,
    )


# --- Startup sync ------------------------------------------------------------


def sync_screens(db: Session) -> None:
    """Upsert md_screen from app/features/rbac/registry.py. Screens removed from code are
    deactivated (never deleted), so existing role grants are not lost."""
    existing = {s.screen_key: s for s in db.scalars(select(Screen))}
    seen: set[str] = set()

    def upsert(key: str, *, parent_id: int | None, name: str, path: str | None, description: str, order: int) -> Screen:
        row = existing.get(key)
        if row is None:
            row = Screen(screen_key=key)
            db.add(row)
            existing[key] = row
        row.parent_screen_id = parent_id
        row.name = name
        row.path = path
        row.description = description
        row.sort_order = order
        row.is_active = True
        seen.add(key)
        return row

    for page_order, page in enumerate(SCREENS, start=1):
        page_row = upsert(
            page.key,
            parent_id=None,
            name=page.name,
            path=page.path,
            description=page.description,
            order=page_order * 100,
        )
        db.flush()
        for feature_order, feature in enumerate(page.features, start=1):
            upsert(
                feature.key,
                parent_id=page_row.id,
                name=feature.name,
                path=None,
                description=feature.description,
                order=page_order * 100 + feature_order,
            )
    for key, row in existing.items():
        if key not in seen and row.is_active:
            row.is_active = False
    db.commit()


def _active_screens(db: Session) -> list[Screen]:
    return list(db.scalars(select(Screen).where(Screen.is_active.is_(True)).order_by(Screen.sort_order, Screen.id)))


def leaf_screens(screens: list[Screen]) -> list[Screen]:
    parents = {s.parent_screen_id for s in screens if s.parent_screen_id is not None}
    return [s for s in screens if s.id not in parents]


def ensure_roles(db: Session) -> None:
    """Make sure the system Administrator role exists with full access to every
    screen (including ones added since the last start), and seed a starter
    Member role exactly once."""
    screens = _active_screens(db)
    leaves = leaf_screens(screens)
    landing = next((s for s in screens if s.screen_key == DEFAULT_LANDING_KEY), None)

    admin = db.scalar(select(Role).where(Role.is_system.is_(True)))
    if admin is None:
        admin = Role(
            name=ADMIN_ROLE_NAME,
            description="Full access to everything. System role: it cannot be edited or deleted.",
            is_system=True,
        )
        db.add(admin)
        db.flush()
    if admin.default_screen_id is None and landing is not None:
        admin.default_screen_id = landing.id
    have = {rs.screen_id: rs for rs in admin.screens}
    for leaf in leaves:
        row = have.get(leaf.id)
        if row is None:
            db.add(RoleScreen(role_id=admin.id, screen_id=leaf.id, can_read=True, can_write=True))
        else:
            row.can_read = row.can_write = True

    seeded = db.scalar(select(SystemFlag).where(SystemFlag.flag_key == "rbac_seeded"))
    if seeded is None:
        member = Role(
            name=MEMBER_ROLE_NAME,
            description="Standard access to their own workspace.",
            default_screen_id=landing.id if landing else None,
        )
        db.add(member)
        db.flush()
        by_key = {s.screen_key: s for s in leaves}
        for key in MEMBER_DEFAULT_KEYS:
            if key in by_key:
                db.add(RoleScreen(role_id=member.id, screen_id=by_key[key].id, can_read=True, can_write=False))
        db.add(SystemFlag(flag_key="rbac_seeded"))
    db.commit()


# --- Effective permissions ------------------------------------------------------


def permissions_for_roles(db: Session, roles: list[Role]) -> Permissions:
    """Union of the given roles' grants. `roles` must already be in priority order."""
    active_roles = [r for r in roles if r.is_active]
    if not active_roles:
        return Permissions()

    screens = _active_screens(db)
    by_id = {s.id: s for s in screens}
    leaves = leaf_screens(screens)
    leaf_ids = {s.id for s in leaves}
    children: dict[int, list[Screen]] = {}
    for s in screens:
        if s.parent_screen_id is not None:
            children.setdefault(s.parent_screen_id, []).append(s)

    rows = db.scalars(select(RoleScreen).where(RoleScreen.role_id.in_([r.id for r in active_roles]))).all()
    per_role: dict[int, dict[int, tuple[bool, bool]]] = {r.id: {} for r in active_roles}
    union: dict[int, tuple[bool, bool]] = {}
    for row in rows:
        if row.screen_id not in leaf_ids:
            continue
        per_role[row.role_id][row.screen_id] = (row.can_read, row.can_write)
        prev_r, prev_w = union.get(row.screen_id, (False, False))
        union[row.screen_id] = (prev_r or row.can_read, prev_w or row.can_write)

    grants: dict[str, tuple[bool, bool]] = {}
    for leaf in leaves:
        grants[leaf.screen_key] = union.get(leaf.id, (False, False))
    for page in (s for s in screens if s.parent_screen_id is None and s.id in children):
        kids = [grants[k.screen_key] for k in children[page.id] if k.screen_key in grants]
        grants[page.screen_key] = (any(r for r, _ in kids), any(w for _, w in kids))

    def page_readable(page: Screen, source: dict[int, tuple[bool, bool]]) -> bool:
        ids = [k.id for k in children[page.id]] if page.id in children else [page.id]
        return any(source.get(i, (False, False))[0] for i in ids)

    landing: str | None = None
    for role in active_roles:  # the first role with a usable default page wins
        page = by_id.get(role.default_screen_id) if role.default_screen_id else None
        if page and page.parent_screen_id is None and page.path and page_readable(page, per_role[role.id]):
            landing = page.path
            break
    if landing is None:
        for page in (s for s in screens if s.parent_screen_id is None):
            if page.path and page_readable(page, union):
                landing = page.path
                break
    return Permissions(grants=grants, landing_path=landing)


def compute_permissions(db: Session, user: User) -> Permissions:
    return permissions_for_roles(db, user.roles)
