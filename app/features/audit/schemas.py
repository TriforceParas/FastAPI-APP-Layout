"""Pydantic request/response models for the audit feature (request models inherit Strict)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    action: str
    outcome: str
    actor_id: str | None
    actor_email: str | None
    target_type: str | None
    target_id: str | None
    ip_address: str | None
    detail: dict | None


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int
