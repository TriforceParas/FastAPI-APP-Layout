from __future__ import annotations

from tests.conftest import Client, make_role, make_user, new_client, role_ids


def test_admin_can_create_list_and_search_users(admin_client: Client, app):
    make_user(admin_client, app)
    page = admin_client.get("/api/users", params={"q": "mia"}).json()
    assert page["total"] == 1
    assert page["items"][0]["email"] == "mia@example.com"
    assert [r["name"] for r in page["items"][0]["roles"]] == ["Member"]
    assert "password_hash" not in page["items"][0]


def test_filter_users_by_role(admin_client: Client, app):
    make_user(admin_client, app)
    ids = role_ids(admin_client)
    assert admin_client.get("/api/users", params={"role_id": ids["Member"]}).json()["total"] == 1
    assert admin_client.get("/api/users", params={"role_id": ids["Administrator"]}).json()["total"] == 1


def test_search_wildcards_are_escaped(admin_client: Client, app):
    make_user(admin_client, app)
    assert admin_client.get("/api/users", params={"q": "%"}).json()["total"] == 0


def test_duplicate_email_conflict(admin_client: Client, app):
    make_user(admin_client, app)
    r = admin_client.post(
        "/api/users",
        json={
            "name": "Dup",
            "email": "MIA@example.com",
            "password": "another long password",
            "role_ids": [role_ids(admin_client)["Member"]],
        },
    )
    assert r.status_code == 409


def test_user_without_users_page_is_forbidden(admin_client: Client, app):
    _, member = make_user(admin_client, app)
    assert member.get("/api/users").status_code == 403
    assert member.get("/api/audit").status_code == 403
    assert member.get("/api/roles").status_code == 403


def test_read_only_user_manager_cannot_change_anything(admin_client: Client, app):
    assert make_role(admin_client, "Viewer", {"users": "r"}, landing="users").status_code == 201
    _, viewer = make_user(admin_client, app, roles=("Viewer",), email="vi@example.com")
    assert viewer.get("/api/users").status_code == 200
    r = viewer.post(
        "/api/users",
        json={"name": "X Y", "email": "x@example.com", "password": "long enough pass", "role_ids": [1]},
    )
    assert r.status_code == 403


def test_role_ids_are_required_and_validated(admin_client: Client):
    base = {"name": "No Role", "email": "nr@example.com", "password": "long enough pass"}
    assert admin_client.post("/api/users", json={**base, "role_ids": []}).status_code == 422
    assert admin_client.post("/api/users", json={**base, "role_ids": [99999]}).status_code == 422
    member = role_ids(admin_client)["Member"]
    assert admin_client.post("/api/users", json={**base, "role_ids": [member, member]}).status_code == 422


def test_cannot_remove_last_admin_or_self(admin_client: Client):
    me = admin_client.get("/api/me").json()
    member = role_ids(admin_client)["Member"]
    assert admin_client.patch(f"/api/users/{me['id']}", json={"role_ids": [member]}).status_code == 409
    assert admin_client.patch(f"/api/users/{me['id']}", json={"is_active": False}).status_code == 409
    assert admin_client.delete(f"/api/users/{me['id']}").status_code == 409


FULL_ACCESS = {
    "dashboard.user_stats": "rw",
    "dashboard.active_sessions": "rw",
    "dashboard.locked_accounts": "rw",
    "dashboard.recent_activity": "rw",
    "dashboard.quick_actions": "rw",
    "users": "rw",
    "roles": "rw",
    "audit": "rw",
}


def test_last_administrator_is_protected_even_from_a_full_access_role(admin_client: Client, app):
    # "Super Ops" holds every permission but is NOT the Administrator role, so it may manage admins...
    assert make_role(admin_client, "Super Ops", FULL_ACCESS, landing="dashboard").status_code == 201
    _, ops = make_user(admin_client, app, roles=("Super Ops",), email="ops@example.com")
    admin_id = admin_client.get("/api/me").json()["id"]
    member = role_ids(admin_client)["Member"]
    # ...but the last active Administrator can still not be demoted, deactivated or deleted.
    assert ops.patch(f"/api/users/{admin_id}", json={"role_ids": [member]}).status_code == 409
    assert ops.patch(f"/api/users/{admin_id}", json={"is_active": False}).status_code == 409
    assert ops.delete(f"/api/users/{admin_id}").status_code == 409


def test_deactivation_revokes_sessions(admin_client: Client, app):
    user, member = make_user(admin_client, app)
    assert admin_client.patch(f"/api/users/{user['id']}", json={"is_active": False}).status_code == 200
    assert member.get("/api/me").status_code == 401


def test_role_change_forces_reauth(admin_client: Client, app):
    user, member = make_user(admin_client, app)
    ids = role_ids(admin_client)
    admin_client.patch(f"/api/users/{user['id']}", json={"role_ids": [ids["Administrator"]]})
    assert member.get("/api/me").status_code == 401


def test_admin_password_reset_and_unlock(admin_client: Client, app):
    user, member = make_user(admin_client, app)
    r = admin_client.post(
        f"/api/users/{user['id']}/password", json={"new_password": "reset by the admin", "must_change_password": True}
    )
    assert r.status_code == 204
    assert member.get("/api/me").status_code == 401
    assert admin_client.post(f"/api/users/{user['id']}/unlock").json()["is_locked"] is False


def test_delete_user_and_audit_trail(admin_client: Client, app):
    user, _ = make_user(admin_client, app)
    assert admin_client.delete(f"/api/users/{user['id']}").status_code == 204
    assert admin_client.get(f"/api/users/{user['id']}").status_code == 404
    actions = [e["action"] for e in admin_client.get("/api/audit").json()["items"]]
    assert "user.delete" in actions and "user.create" in actions and "auth.setup" in actions


def test_cannot_revoke_other_users_session(admin_client: Client, app):
    _, member = make_user(admin_client, app)
    admin_session = admin_client.get("/api/me/sessions").json()[0]["id"]
    assert member.delete(f"/api/me/sessions/{admin_session}").status_code == 404


# --- privilege escalation -------------------------------------------------------


def test_user_manager_cannot_assign_a_stronger_role(admin_client: Client, app):
    assert make_role(admin_client, "People Manager", {"users": "rw"}, landing="users").status_code == 201
    mgr, mgr_client = make_user(admin_client, app, roles=("People Manager",), email="pm@example.com")
    ids = role_ids(admin_client)
    base = {"name": "New Guy", "email": "ng@example.com", "password": "long enough pass"}
    # may assign roles that hold no more than they do...
    assert mgr_client.post("/api/users", json={**base, "role_ids": [ids["People Manager"]]}).status_code == 201
    # ...but never Administrator, and cannot promote themselves.
    assert (
        mgr_client.post(
            "/api/users", json={**base, "email": "ng2@example.com", "role_ids": [ids["Administrator"]]}
        ).status_code
        == 403
    )
    assert mgr_client.patch(f"/api/users/{mgr['id']}", json={"role_ids": [ids["Administrator"]]}).status_code == 409


def test_user_manager_cannot_take_over_an_administrator(admin_client: Client, app):
    assert make_role(admin_client, "People Manager", {"users": "rw"}, landing="users").status_code == 201
    _, mgr_client = make_user(admin_client, app, roles=("People Manager",), email="pm@example.com")
    admin_id = admin_client.get("/api/me").json()["id"]
    assert (
        mgr_client.post(f"/api/users/{admin_id}/password", json={"new_password": "attacker chosen pass"}).status_code
        == 403
    )
    assert mgr_client.patch(f"/api/users/{admin_id}", json={"is_active": False}).status_code == 403
    assert mgr_client.delete(f"/api/users/{admin_id}").status_code == 403
    assert mgr_client.post(f"/api/users/{admin_id}/unlock").status_code == 403
    # the administrator can still sign in with the original password
    new_client(app, "ada@example.com", "correct horse battery")
