"""Database models for the audit feature (names: db-naming-conventions skill)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utcnow


class Event(Base):
    """aud_: audit trail. Append-only security log. Actor fields are snapshots
    (no FK), so history survives user deletion."""

    __tablename__ = "aud_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    outcome: Mapped[str] = mapped_column(String(16), default="success")
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor_email: Mapped[str | None] = mapped_column(String(254))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(36))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    detail: Mapped[dict | None] = mapped_column(JSON)
