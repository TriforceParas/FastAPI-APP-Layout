from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import new_session
from app.features.rbac.models import Role, RoleScreen
from tests.conftest import Client, make_role, make_user, role_ids, screen_ids


def status_of(client: Client) -> dict:
    return client.get("/api/auth/status").json()


# --- seeding and the screen tree ---------------------------------------------------


def test_screens_form_a_tree_of_pages_and_features(admin_client: Client):
    screens = admin_client.get("/api/screens").json()
    by_key = {s["screen_key"]: s for s in screens}
    assert by_key["dashboard"]["parent_screen_id"] is None and by_key["dashboard"]["path"] == "/dashboard"
    feature = by_key["dashboard.recent_activity"]
    assert feature["parent_screen_id"] == by_key["dashboard"]["id"] and feature["path"] is None
    assert "settings" not in by_key  # Settings is outside RBAC


def test_administrator_role_has_everything_and_member_is_seeded(admin_client: Client):
    roles = {r["name"]: r for r in admin_client.get("/api/roles").json()}
    assert roles["Administrator"]["is_system"] is True and roles["Member"]["is_system"] is False
    detail = admin_client.get(f"/api/roles/{roles['Administrator']['id']}").json()
    assert detail["access"] and all(a["can_read"] and a["can_write"] for a in detail["access"])
    # the Administrator has no rows for pages that have features: only leaves carry permissions
    ids = screen_ids(admin_client)
    assert ids["dashboard"] not in {a["screen_id"] for a in detail["access"]}


# --- effective permissions -------------------------------------------------------------


def test_member_only_sees_granted_dashboard_features(admin_client: Client, app):
    _, member = make_user(admin_client, app)
    perms = status_of(member)["permissions"]
    assert perms["dashboard"]["read"] is True  # derived: any feature readable
    assert perms["dashboard.recent_activity"]["read"] is True
    assert perms["dashboard.user_stats"] == {"read": False, "write": False}
    assert perms["users"] == {"read": False, "write": False}

    summary = member.get("/api/dashboard/summary").json()
    assert summary["users_total"] is None and summary["users_locked"] is None  # features not granted
    assert summary["sessions_active"] is not None and summary["recent_events"] is not None


def test_dashboard_requires_at_least_one_feature(admin_client: Client, app):
    assert make_role(admin_client, "Users Only", {"users": "r"}, landing="users").status_code == 201
    _, user = make_user(admin_client, app, roles=("Users Only",), email="uo@example.com")
    assert user.get("/api/dashboard/summary").status_code == 403


def test_recent_activity_shows_only_own_events_without_audit_access(admin_client: Client, app):
    _, member = make_user(admin_client, app)
    events = member.get("/api/dashboard/summary").json()["recent_events"]
    assert events and all(e["actor_email"] == "mia@example.com" for e in events)
    assert any(
        e["actor_email"] != "mia@example.com"
        for e in admin_client.get("/api/dashboard/summary").json()["recent_events"]
    )


def test_permissions_are_the_union_of_all_roles(admin_client: Client, app):
    assert make_role(admin_client, "Auditor", {"audit": "r"}, landing="audit").status_code == 201
    _, user = make_user(admin_client, app, roles=("Member", "Auditor"), email="two@example.com")
    perms = status_of(user)["permissions"]
    assert perms["audit"]["read"] and perms["dashboard.recent_activity"]["read"]
    assert user.get("/api/audit").status_code == 200
    assert user.get("/api/audit").status_code == 200 and user.post("/api/users", json={}).status_code == 403


def test_first_role_decides_the_landing_page(admin_client: Client, app):
    assert make_role(admin_client, "Auditor", {"audit": "r"}, landing="audit").status_code == 201
    user, client = make_user(admin_client, app, roles=("Member", "Auditor"), email="two@example.com")
    assert status_of(client)["landing_path"] == "/dashboard"  # Member is first

    ids = role_ids(admin_client)
    r = admin_client.patch(f"/api/users/{user['id']}", json={"role_ids": [ids["Auditor"], ids["Member"]]})
    assert r.status_code == 200 and [x["name"] for x in r.json()["roles"]] == ["Auditor", "Member"]
    client = Client(app)
    client.bootstrap()
    client.post("/api/auth/login", json={"email": "two@example.com", "password": "member password 1"})
    assert status_of(client)["landing_path"] == "/audit"  # Auditor now first


def test_landing_falls_back_when_first_role_has_no_default_page(admin_client: Client, app):
    ids = screen_ids(admin_client)
    r = admin_client.post(
        "/api/roles", json={"name": "Empty", "description": None, "default_screen_id": None, "access": []}
    )
    assert r.status_code == 201
    _, client = make_user(admin_client, app, roles=("Empty", "Member"), email="two@example.com")
    assert status_of(client)["landing_path"] == "/dashboard"
    assert ids  # (screen ids exist)


def test_user_with_no_readable_page_has_no_landing_page(admin_client: Client, app):
    r = admin_client.post(
        "/api/roles", json={"name": "Empty", "description": None, "default_screen_id": None, "access": []}
    )
    assert r.status_code == 201
    _, client = make_user(admin_client, app, roles=("Empty",), email="e@example.com")
    assert status_of(client)["landing_path"] is None
    assert client.get("/api/me").status_code == 200  # Settings / /api/me are outside RBAC


def test_role_changes_apply_immediately(admin_client: Client, app):
    r = make_role(admin_client, "Flex", {"users": "r"}, landing="users")
    assert r.status_code == 201
    role = r.json()
    _, client = make_user(admin_client, app, roles=("Flex",), email="f@example.com")
    assert client.get("/api/users").status_code == 200
    r = admin_client.put(
        f"/api/roles/{role['id']}",
        json={"name": "Flex", "description": None, "default_screen_id": None, "access": []},
    )
    assert r.status_code == 200
    assert client.get("/api/users").status_code == 403  # no re-login needed


# --- role management rules ------------------------------------------------------------


def test_write_requires_read(admin_client: Client):
    ids = screen_ids(admin_client)
    r = admin_client.post(
        "/api/roles",
        json={
            "name": "Bad",
            "default_screen_id": ids["users"],
            "access": [{"screen_id": ids["users"], "can_read": False, "can_write": True}],
        },
    )
    assert r.status_code == 422


def test_permissions_only_on_leaves(admin_client: Client):
    ids = screen_ids(admin_client)  # "dashboard" has features, so it is not a leaf
    r = admin_client.post(
        "/api/roles",
        json={
            "name": "Bad",
            "default_screen_id": ids["users"],
            "access": [{"screen_id": ids["dashboard"], "can_read": True, "can_write": False}],
        },
    )
    assert r.status_code == 422


def test_landing_page_rules(admin_client: Client):
    ids = screen_ids(admin_client)
    base = {"name": "Landing Test", "description": None}
    grant = [{"screen_id": ids["dashboard.recent_activity"], "can_read": True, "can_write": False}]
    # must be a page, not a feature
    assert (
        admin_client.post(
            "/api/roles", json={**base, "default_screen_id": ids["dashboard.recent_activity"], "access": grant}
        ).status_code
        == 422
    )
    # must be a page the role can open
    assert (
        admin_client.post("/api/roles", json={**base, "default_screen_id": ids["users"], "access": grant}).status_code
        == 422
    )
    # required when the role can read anything
    assert admin_client.post("/api/roles", json={**base, "default_screen_id": None, "access": grant}).status_code == 422
    # a page is openable through any one of its features
    assert (
        admin_client.post(
            "/api/roles", json={**base, "default_screen_id": ids["dashboard"], "access": grant}
        ).status_code
        == 201
    )


def test_system_role_cannot_be_edited_or_deleted(admin_client: Client):
    admin_id = role_ids(admin_client)["Administrator"]
    body = {"name": "Renamed", "description": None, "default_screen_id": None, "access": []}
    assert admin_client.put(f"/api/roles/{admin_id}", json=body).status_code == 409
    assert admin_client.delete(f"/api/roles/{admin_id}").status_code == 409


def test_role_with_users_cannot_be_deleted(admin_client: Client, app):
    make_user(admin_client, app)
    member = role_ids(admin_client)["Member"]
    assert admin_client.delete(f"/api/roles/{member}").status_code == 409
    empty = admin_client.post("/api/roles", json={"name": "Temp", "description": None, "access": []}).json()
    assert admin_client.delete(f"/api/roles/{empty['id']}").status_code == 204


def test_duplicate_role_name_conflict(admin_client: Client):
    body = {"name": "Dup Role", "description": None, "access": []}
    assert admin_client.post("/api/roles", json=body).status_code == 201
    assert admin_client.post("/api/roles", json=body).status_code == 409


def test_role_manager_cannot_grant_permissions_they_lack(admin_client: Client, app):
    assert make_role(admin_client, "Role Manager", {"roles": "rw"}, landing="roles").status_code == 201
    _, mgr = make_user(admin_client, app, roles=("Role Manager",), email="rm@example.com")
    ids = screen_ids(admin_client)
    # cannot create a role that grants Users or Audit
    r = mgr.post(
        "/api/roles",
        json={
            "name": "Sneaky",
            "default_screen_id": ids["users"],
            "access": [{"screen_id": ids["users"], "can_read": True, "can_write": True}],
        },
    )
    assert r.status_code == 403
    # may create roles within their own permissions
    r = mgr.post(
        "/api/roles",
        json={
            "name": "Fine",
            "default_screen_id": ids["roles"],
            "access": [{"screen_id": ids["roles"], "can_read": True, "can_write": False}],
        },
    )
    assert r.status_code == 201
    # cannot edit a role that holds more than they do (e.g. Member has dashboard access)
    member = role_ids(admin_client)["Member"]
    assert (
        mgr.put(f"/api/roles/{member}", json={"name": "Member", "description": None, "access": []}).status_code == 403
    )
    assert mgr.delete(f"/api/roles/{member}").status_code in (403, 409)


def test_role_changes_are_audited(admin_client: Client):
    r = make_role(admin_client, "Audited", {"users": "r"}, landing="users")
    events = admin_client.get("/api/audit", params={"action": "role."}).json()["items"]
    assert events and events[0]["action"] == "role.create" and events[0]["detail"]["permissions"] == ["users"]
    assert r.status_code == 201


# --- the database enforces the same invariants ------------------------------------------


def test_database_rejects_write_without_read(admin_client: Client):
    with new_session() as db:
        role = db.scalar(select(Role).where(Role.name == "Member"))
        users = admin_client.get("/api/screens").json()
        screen_id = next(s["id"] for s in users if s["screen_key"] == "users")
        db.add(RoleScreen(role_id=role.id, screen_id=screen_id, can_read=False, can_write=True))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_a_user_cannot_hold_the_same_role_twice(admin_client: Client, app):
    user, _ = make_user(admin_client, app)
    member = role_ids(admin_client)["Member"]
    from app.features.rbac.models import UserRole

    with new_session() as db:
        db.add(UserRole(user_id=user["id"], role_id=member, sort_order=9))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert sqlite3  # (imported for completeness of the sqlite-backed test run)
