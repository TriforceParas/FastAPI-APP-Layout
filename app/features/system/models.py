"""Database models for the system feature (names: db-naming-conventions skill)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, utcnow


class SystemFlag(Base):
    """cfg_: configuration. Key/value markers. The unique `flag_key` guarantees two
    concurrent setup requests cannot both create the first admin."""

    __tablename__ = "cfg_system_flag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    flag_key: Mapped[str] = mapped_column(String(64), unique=True)
    flag_value: Mapped[str] = mapped_column(String(255), default="1")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))
