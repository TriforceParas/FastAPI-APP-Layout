from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from tests.conftest import Client


def test_every_response_gets_a_request_id(client: Client):
    rid = client.get("/api/health/live").headers["x-request-id"]
    assert len(rid) == 32
    assert client.get("/api/health/live").headers["x-request-id"] != rid


def test_a_safe_incoming_request_id_is_kept(client: Client):
    r = client.get("/api/health/live", headers={"X-Request-ID": "edge-abc123.XYZ_9"})
    assert r.headers["x-request-id"] == "edge-abc123.XYZ_9"


def test_unsafe_incoming_request_ids_are_replaced(client: Client):
    for bad in ("short", "x" * 65, "abc\\nINJECTED log line", "<script>alert(1)</script>"):
        r = client.get("/api/health/live", headers={"X-Request-ID": bad})
        assert r.headers["x-request-id"] != bad and len(r.headers["x-request-id"]) == 32


def test_errors_carry_the_request_id_and_log_lines_include_it(app, caplog, monkeypatch):
    from app.features.auth import router as auth

    def boom(db):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(auth, "setup_required", boom)  # make a real endpoint fail
    with caplog.at_level(logging.ERROR):
        r = TestClient(app, raise_server_exceptions=False).get("/api/auth/status")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error" and body["request_id"] == r.headers["x-request-id"]
    assert "secret internal detail" not in r.text
    assert any(getattr(rec, "request_id", None) == body["request_id"] for rec in caplog.records)
