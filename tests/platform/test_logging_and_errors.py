from __future__ import annotations

import json
import logging

from app.core.errors import Conflict, NotFound
from app.core.logging import JsonFormatter, RequestIdFilter
from tests.conftest import Client


def test_json_formatter_emits_one_object_with_request_id_and_extra_fields():
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.order_id = "o-1"
    RequestIdFilter().filter(record)
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "hello world" and data["level"] == "INFO" and data["logger"] == "app.test"
    assert data["request_id"] == "-" and data["order_id"] == "o-1" and data["ts"].endswith("Z")


def test_access_log_has_one_line_per_request_without_query_string(client: Client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        r = client.get("/reset-password?token=super-secret-token-value")
    lines = [rec for rec in caplog.records if rec.name == "app.access"]
    assert lines and lines[-1].path == "/reset-password" and lines[-1].status == r.status_code
    assert lines[-1].request_id == r.headers["x-request-id"]
    # (the TEST client's own httpx logger prints its URL; only the app's loggers matter here)
    app_records = [rec for rec in caplog.records if rec.name.startswith("app")]
    assert all("super-secret-token-value" not in rec.getMessage() for rec in app_records)


def test_health_probes_are_logged_at_debug_only(client: Client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get("/api/health/live")
    assert not [rec for rec in caplog.records if rec.name == "app.access"]


def test_app_errors_become_detail_responses(app, monkeypatch):
    from fastapi.testclient import TestClient

    from app.features.auth import router as auth

    def raise_conflict(db):
        raise Conflict("Nope, already done.", headers={"X-Extra": "1"})

    monkeypatch.setattr(auth, "setup_required", raise_conflict)
    r = TestClient(app).get("/api/auth/status")
    assert r.status_code == 409 and r.json() == {"detail": "Nope, already done."} and r.headers["x-extra"] == "1"
    assert NotFound.status_code == 404
