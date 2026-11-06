"""Every lookup needs these three tests (see AGENTS.md, "Lookups")."""

from __future__ import annotations

from app.features.lookups.router import LOOKUPS
from tests.conftest import Client, make_role, make_user


def test_roles_lookup_returns_exactly_id_and_label(admin_client: Client):
    items = admin_client.get("/api/lookups/roles").json()
    assert items and all(set(item) == {"id", "label"} for item in items)
    assert {i["label"] for i in items} >= {"Administrator", "Member"}


def test_lookup_forbidden_without_a_consuming_screen(admin_client: Client, app):
    # Member has the dashboard but not the Users page (the only consumer of this lookup).
    _, member = make_user(admin_client, app)
    assert member.get("/api/lookups/roles").status_code == 403


def test_lookup_works_with_only_the_consuming_screen_and_no_access_to_the_source_page(admin_client: Client, app):
    # The user may use the Users page but has NO access to the Roles page...
    assert make_role(admin_client, "People Viewer", {"users": "r"}, landing="users").status_code == 201
    _, viewer = make_user(admin_client, app, roles=("People Viewer",), email="pv@example.com")
    assert viewer.get("/api/roles").status_code == 403
    # ...yet the role dropdown on the Users page still works, and leaks nothing else.
    r = viewer.get("/api/lookups/roles")
    assert r.status_code == 200
    assert all(set(item) == {"id", "label"} for item in r.json())


def test_lookup_search_and_limit(admin_client: Client):
    assert len(admin_client.get("/api/lookups/roles", params={"q": "admin"}).json()) == 1
    assert admin_client.get("/api/lookups/roles", params={"limit": 1}).json().__len__() == 1
    assert admin_client.get("/api/lookups/roles", params={"limit": 500}).status_code == 422
    assert admin_client.get("/api/lookups/roles", params={"q": "%"}).json() == []


def test_lookup_excludes_inactive_records(admin_client: Client):
    from sqlalchemy import update

    from app.db.session import new_session
    from app.features.rbac.models import Role

    assert make_role(admin_client, "Retired", {"users": "r"}, landing="users").status_code == 201
    with new_session() as db:
        db.execute(update(Role).where(Role.name == "Retired").values(is_active=False))
        db.commit()
    assert "Retired" not in {i["label"] for i in admin_client.get("/api/lookups/roles").json()}


def test_every_lookup_has_registered_consumers():
    assert LOOKUPS and all(consumers for consumers in LOOKUPS.values())
