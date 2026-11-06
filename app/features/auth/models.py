"""Database models for the auth feature (names: db-naming-conventions skill)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_id, utcnow

if TYPE_CHECKING:
    from app.features.users.models import User


class UserSession(Base):
    """txn_: transaction data. One row per signed-in browser, created by normal usage."""

    __tablename__ = "txn_user_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("md_user.id", ondelete="CASCADE"), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))

    user: Mapped[User] = relationship(back_populates="sessions", lazy="joined")


class UserIdentity(Base):
    """md_: master data. An external sign-in (Microsoft Entra ID) linked to a user.
    Matched by the provider's immutable ids (tenant + object id), never by email,
    so renaming or re-using an email address can't take over an account."""

    __tablename__ = "md_user_identity"
    __table_args__ = (
        UniqueConstraint("provider", "tenant_id", "subject"),
        UniqueConstraint("user_id", "provider"),  # one Microsoft account per user
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("md_user.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # "microsoft"
    tenant_id: Mapped[str] = mapped_column(String(64))  # Entra "tid"
    subject: Mapped[str] = mapped_column(String(64))  # Entra "oid"
    email: Mapped[str] = mapped_column(String(254))  # as last reported by the provider
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))

    user: Mapped[User] = relationship(lazy="joined")


class PasswordReset(Base):
    """txn_: transaction data. A "forgot password" link. Only the token's HMAC is
    stored; links are single use and expire (PASSWORD_RESET_MINUTES)."""

    __tablename__ = "txn_password_reset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("md_user.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ip_address: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))

    user: Mapped[User] = relationship(lazy="joined")
