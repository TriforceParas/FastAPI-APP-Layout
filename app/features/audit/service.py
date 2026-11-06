"""Security audit trail (OWASP A09). Never put secrets or passwords in
`detail`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.request_info import client_ip
from app.features.audit.models import Event

if TYPE_CHECKING:
    from app.api.deps import Principal

log = logging.getLogger("app.audit")


def record(
    db: Session,
    request: Request,
    action: str,
    *,
    actor: Principal | None = None,
    actor_email: str | None = None,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Stage an audit event on the session; the caller commits it."""
    event = Event(
        action=action,
        outcome=outcome,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else actor_email,
        target_type=target_type,
        target_id=target_id,
        ip_address=client_ip(request),
        detail=detail,
    )
    db.add(event)
    log.info(
        "audit action=%s outcome=%s actor=%s target=%s:%s ip=%s",
        action,
        outcome,
        event.actor_email,
        target_type,
        target_id,
        event.ip_address,
    )
