"""Pydantic request/response models for the mfa feature (request models inherit Strict)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.api.schemas import ChallengeToken, Password, Strict


class MfaStatus(BaseModel):
    method: str | None
    enabled_at: datetime | None
    recovery_codes_remaining: int
    email_available: bool


class CurrentPassword(Strict):
    current_password: Password


class TotpEnrollment(BaseModel):
    challenge_token: str
    secret: str  # for manual entry
    otpauth_uri: str
    qr_code: str  # data:image/svg+xml URI


class EmailEnrollment(BaseModel):
    challenge_token: str
    destination_hint: str


class MfaConfirmRequest(Strict):
    challenge_token: ChallengeToken
    code: Annotated[str, Field(min_length=6, max_length=12)]


class RecoveryCodes(BaseModel):
    recovery_codes: list[str]
