from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="app-tests-"))
os.environ.update(
    {
        "APP_ENV": "test",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-123456",
        "DATABASE_URL": f"sqlite:///{_tmp / 'test.db'}",
        "DATA_DIR": str(_tmp),
        "AUTO_MIGRATE": "true",
        "AUTH_ENABLED": "true",
        "AUTH_BYPASS_FILE": str(_tmp / ".auth-bypass"),
        "SETUP_TOKEN_REQUIRED": "false",
        "ALLOWED_HOSTS": "testserver",
        "ALLOWED_ORIGINS": "http://testserver",
        "COOKIE_SECURE": "false",
        "FRONTEND_DIST": str(_tmp / "dist"),
        "TURNSTILE_ENABLED": "false",  # the dev .env enables it with Cloudflare test keys
        "MAIL_PROVIDER": "console",  # emails land in app.integrations.mail.console_mailer.outbox
        "PUBLIC_URL": "http://testserver",
    }
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import limiter
from app.db.session import new_session  # noqa: E402
from app.features.audit.models import Event
from app.features.auth.models import PasswordReset, UserSession
from app.features.mfa.models import MfaChallenge
from app.features.rbac.models import Role, UserRole
from app.features.system.models import SystemFlag
from app.features.users.models import User
from app.integrations.mail import console_mailer
from app.main import create_app  # noqa: E402

ADMIN = {"name": "Ada Admin", "email": "ada@example.com", "password": "correct horse battery"}


class Client(TestClient):
    """TestClient that behaves like the SPA: fetches the CSRF token first and
    sends it on every unsafe request."""

    csrf: str | None = None

    def bootstrap(self) -> dict:
        data = self.get("/api/auth/status").json()
        self.csrf = data["csrf_token"]
        return data

    def request(self, method, url, *args, **kwargs):  # type: ignore[override]
        if method.upper() not in {"GET", "HEAD", "OPTIONS"} and self.csrf:
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("X-CSRF-Token", self.csrf)
            headers.setdefault("Origin", "http://testserver")
            kwargs["headers"] = headers
        response = super().request(method, url, *args, **kwargs)
        if response.headers.get("content-type", "").startswith("application/json"):
            body = response.json()
            if isinstance(body, dict) and "csrf_token" in body:
                self.csrf = body["csrf_token"]
        return response


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(autouse=True)
def _clean_state(app) -> Iterator[None]:
    with TestClient(app):  # runs lifespan: migrations, screen sync, role seeding
        pass
    yield
    limiter.reset()
    settings = get_settings()
    settings.auth_enabled = True
    settings.turnstile_enabled = False
    settings.mail_provider = "console"
    console_mailer.outbox.clear()
    settings.auth_bypass_file.unlink(missing_ok=True)
    with new_session() as db:
        for model in (MfaChallenge, PasswordReset, UserRole, UserSession, Event, SystemFlag, User):
            db.execute(delete(model))
        db.execute(delete(Role).where(Role.is_system.is_(False)))  # the system Administrator stays
        db.commit()


@pytest.fixture
def client(app) -> Client:
    c = Client(app)
    c.bootstrap()
    return c


@pytest.fixture
def admin_client(client: Client) -> Client:
    r = client.post("/api/auth/setup", json=ADMIN)
    assert r.status_code == 201, r.text
    return client


def role_ids(admin_client: Client) -> dict[str, int]:
    return {r["name"]: r["id"] for r in admin_client.get("/api/roles").json()}


def screen_ids(admin_client: Client) -> dict[str, int]:
    return {s["screen_key"]: s["id"] for s in admin_client.get("/api/screens").json()}


def make_role(admin_client: Client, name: str, grants: dict[str, str], landing: str | None = None):
    """grants: {"users": "rw", "dashboard.user_stats": "r"}; landing: a page key."""
    ids = screen_ids(admin_client)
    access = [{"screen_id": ids[key], "can_read": True, "can_write": mode == "rw"} for key, mode in grants.items()]
    return admin_client.post(
        "/api/roles",
        json={
            "name": name,
            "description": None,
            "default_screen_id": ids[landing] if landing else None,
            "access": access,
        },
    )


def new_client(app, email: str, password: str) -> Client:
    c = Client(app)
    c.bootstrap()
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return c


def make_user(admin_client: Client, app, roles=("Member",), email="mia@example.com", password="member password 1"):
    ids = role_ids(admin_client)
    r = admin_client.post(
        "/api/users",
        json={
            "name": "Mia Member",
            "email": email,
            "password": password,
            "must_change_password": False,
            "role_ids": [ids[name] for name in roles],
        },
    )
    assert r.status_code == 201, r.text
    return r.json(), new_client(app, email, password)


# Kept for brevity in older tests.
make_member = make_user


def last_email(to: str | None = None):
    mails = [m for m in console_mailer.outbox if to is None or m.to == to]
    assert mails, "no email was sent"
    return mails[-1]
