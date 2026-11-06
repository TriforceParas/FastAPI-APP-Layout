"""Pydantic request/response models for the users feature (request models inherit Strict)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import Email, Name, Password, Strict

if TYPE_CHECKING:
    from app.features.users.models import User

RoleIds = Annotated[list[int], Field(min_length=1, max_length=20)]


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    roles: list[RoleBrief]  # in priority order; the first decides the landing page
    is_active: bool
    must_change_password: bool
    is_locked: bool = False
    mfa_method: str | None = None  # None | "totp" | "email"
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserCreate(Strict):
    name: Name
    email: Email
    role_ids: RoleIds  # ordered: first = primary role
    password: Password
    must_change_password: bool = True


class UserUpdate(Strict):
    name: Name | None = None
    role_ids: RoleIds | None = None
    is_active: bool | None = None


class PasswordReset(Strict):
    new_password: Password
    must_change_password: bool = True


class UsersPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


def user_out(user: User) -> UserOut:
    """The public view of a user (never includes hashes, secrets or tokens)."""
    return UserOut.model_validate(user)
