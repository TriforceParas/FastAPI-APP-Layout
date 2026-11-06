"""Logging setup. Every record carries the request id (`req=…` / "request_id").

LOG_FORMAT=text   2026-11-06 10:00:00 INFO [app.access] [req=3f2a…] GET /api/users 200 12.3ms
LOG_FORMAT=json   {"ts": "...", "level": "INFO", "logger": "app.access", "request_id": "3f2a…", "message": "...",
                   "method": "GET", "path": "/api/users", "status": 200, "duration_ms": 12.3}

Log with `log = logging.getLogger(__name__)` and pass structured fields with
`extra={...}`; they appear as JSON keys. Never log secrets (see the
error-handling-logging skill).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from app.core.config import get_settings

# Attributes every LogRecord has; anything else came from `extra=` and is emitted as a JSON field.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime", "request_id"}


class RequestIdFilter(logging.Filter):
    """Adds `request_id` to every record ("-" outside a request)."""

    def filter(self, record: logging.LogRecord) -> bool:
        from app.middleware.request_id import current_request_id

        record.request_id = current_request_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _STANDARD and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    formatter: logging.Formatter = (
        JsonFormatter()
        if settings.log_format == "json"
        else logging.Formatter("%(asctime)s %(levelname)s [%(name)s] [req=%(request_id)s] %(message)s")
    )
    # Third-party loggers that log every outbound request URL at INFO: keep them quiet.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    for handler in root.handlers:
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())
        if isinstance(handler, logging.StreamHandler) and not getattr(handler, "_app_configured", False):
            handler.setFormatter(formatter)
            handler._app_configured = True  # type: ignore[attr-defined]
