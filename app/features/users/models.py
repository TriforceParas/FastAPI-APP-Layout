"""Database models for the users feature (names: db-naming-conventions skill)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, new_id, utcnow

if TYPE_CHECKING:
    from app.features.auth.models import UserSession
    from app.features.rbac.models import Role, UserRole


class User(Base):
    """md_: master data. Application users."""

    __tablename__ = "md_user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    must_change_password: Mapped[bool] = mapped_column(default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    # Optional two-factor authentication, chosen by the user in Settings.
    mfa_method: Mapped[str | None] = mapped_column(String(10))  # None | "totp" | "email"
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(255))  # TOTP seed, Fernet-encrypted
    mfa_totp_last_step: Mapped[int | None] = mapped_column(Integer)  # blocks TOTP code replay
    mfa_recovery_hashes: Mapped[list[str] | None] = mapped_column(JSON)  # HMACs of one-time recovery codes
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # Standard audit columns. created_by/updated_by hold a user id but are not
    # foreign keys, so deleting a user never blocks or rewrites history.
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))

    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    # Ordered by sort_order: the FIRST role decides the landing page.
    role_links: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        order_by="UserRole.sort_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    @property
    def roles(self) -> list[Role]:
        return [link.role for link in self.role_links]

    def locked_at(self, now: datetime | None = None) -> bool:
        return self.locked_until is not None and self.locked_until > (now or utcnow())

    @property
    def is_locked(self) -> bool:
        return self.locked_at()
