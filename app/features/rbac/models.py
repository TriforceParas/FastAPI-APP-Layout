"""Database models for the rbac feature (names: db-naming-conventions skill)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, utcnow

if TYPE_CHECKING:
    from app.features.users.models import User


class Screen(Base):
    """md_: master data. A node in the screen tree. Top-level rows
    (parent_screen_id IS NULL) are pages; child rows are features of a page.
    Rows are synced from app/features/rbac/registry.py at startup; do not edit by hand."""

    __tablename__ = "md_screen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_screen_id: Mapped[int | None] = mapped_column(ForeignKey("md_screen.id", ondelete="CASCADE"), index=True)
    screen_key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    path: Mapped[str | None] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))


class Role(Base):
    """md_: master data. A named set of screen permissions."""

    __tablename__ = "md_role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))
    is_system: Mapped[bool] = mapped_column(default=False)  # Administrator: locked
    is_active: Mapped[bool] = mapped_column(default=True)
    # A PAGE this role can open; where its users land after sign-in.
    default_screen_id: Mapped[int | None] = mapped_column(ForeignKey("md_screen.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))
    updated_by: Mapped[str | None] = mapped_column(String(36))

    screens: Mapped[list[RoleScreen]] = relationship(
        back_populates="role", cascade="all, delete-orphan", passive_deletes=True
    )


class RoleScreen(Base):
    """map_: role <-> screen permissions. Rows exist for LEAF screens only
    (a page's features, or a page that has no features)."""

    __tablename__ = "map_role_screen"
    __table_args__ = (
        UniqueConstraint("role_id", "screen_id"),
        # Write implies Read: nobody can change what they cannot open.
        CheckConstraint("NOT can_write OR can_read", name="write_requires_read"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("md_role.id", ondelete="CASCADE"))
    screen_id: Mapped[int] = mapped_column(ForeignKey("md_screen.id", ondelete="CASCADE"))
    can_read: Mapped[bool] = mapped_column(default=False)
    can_write: Mapped[bool] = mapped_column(default=False)

    role: Mapped[Role] = relationship(back_populates="screens")


class UserRole(Base):
    """map_: user <-> role. A user can hold several roles; permissions are the
    union, and the role with the lowest sort_order decides the landing page."""

    __tablename__ = "map_user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id"),
        UniqueConstraint("user_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("md_user.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("md_role.id", ondelete="RESTRICT"))
    sort_order: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36))

    user: Mapped[User] = relationship(back_populates="role_links")
    role: Mapped[Role] = relationship(lazy="joined")
