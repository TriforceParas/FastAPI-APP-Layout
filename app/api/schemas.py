"""Shared request/response building blocks: Strict base model, common field types, Message, LookupItem."""

from __future__ import annotations

import unicodedata
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.core.security import PASSWORD_MAX_LENGTH


def _clean_name(value: str) -> str:
    value = " ".join(unicodedata.normalize("NFKC", value).split())
    if any(unicodedata.category(ch).startswith("C") for ch in value):
        raise ValueError("Name contains invalid characters")
    if len(value) < 2:
        raise ValueError("Name must be at least 2 characters")
    return value


def _lower_email(value: str) -> str:
    return value.strip().lower()


Name = Annotated[str, Field(min_length=2, max_length=100), AfterValidator(_clean_name)]


Email = Annotated[EmailStr, Field(max_length=254), AfterValidator(_lower_email)]


Password = Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


TurnstileToken = Annotated[str | None, Field(default=None, max_length=2048)]


ChallengeToken = Annotated[str, Field(min_length=16, max_length=128)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Message(BaseModel):
    detail: str


class LookupItem(BaseModel):
    """The ONLY shape a lookup may return: an id and a display label."""

    id: int
    label: str
