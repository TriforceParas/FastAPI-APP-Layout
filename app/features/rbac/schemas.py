"""Pydantic request/response models for the rbac feature (request models inherit Strict)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import Name, Strict


class ScreenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_screen_id: int | None
    screen_key: str
    name: str
    path: str | None
    description: str | None


class AccessIn(Strict):
    screen_id: int
    can_read: bool
    can_write: bool


class AccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    screen_id: int
    can_read: bool
    can_write: bool


class RoleWrite(Strict):
    name: Name
    description: Annotated[str | None, Field(max_length=255)] = None
    default_screen_id: int | None = None
    access: Annotated[list[AccessIn], Field(max_length=500)] = []


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_system: bool
    is_active: bool
    default_screen_id: int | None
    user_count: int = 0


class RoleDetail(RoleOut):
    access: list[AccessOut]
