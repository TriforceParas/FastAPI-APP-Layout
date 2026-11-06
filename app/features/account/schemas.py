"""Pydantic request/response models for the account feature (request models inherit Strict)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.api.schemas import Name, Password, Strict


class ProfileUpdate(Strict):
    name: Name


class PasswordChange(Strict):
    current_password: Password
    new_password: Password


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool = False
