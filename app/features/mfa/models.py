"""Database models for the mfa feature (names: db-naming-conventions skill)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_id, utcnow

if TYPE_CHECKING:
    from app.features.users.models import User


class MfaChallenge(Base):
    """txn_: transaction data. A pending second step: signing in with 2FA, or
    confirming a new 2FA method. The client holds an opaque token; only its HMAC
    is stored. Single use, short-lived, limited attempts."""

    __tablename__ = "txn_mfa_challenge"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("md_user.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # "login" | "enroll"
    method: Mapped[str] = mapped_column(String(10))  # "totp" | "email"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    code_hash: Mapped[str | None] = mapped_column(String(64))  # emailed code (HMAC)
    secret_encrypted: Mapped[str | None] = mapped_column(String(255))  # TOTP seed being enrolled
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sends: Mapped[int] = mapped_column(Integer, default=0)
    last_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))

    user: Mapped[User] = relationship(lazy="joined")
