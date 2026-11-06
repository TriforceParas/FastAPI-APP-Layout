"""Pydantic request/response models for the auth feature (request models inherit Strict)."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.api.schemas import ChallengeToken, Email, Name, Password, Strict, TurnstileToken, _lower_email
from app.features.users.schemas import UserOut


class SetupRequest(Strict):
    name: Name
    email: Email
    password: Password
    setup_token: str | None = Field(default=None, max_length=200)
    turnstile_token: TurnstileToken = None


class LoginRequest(Strict):
    email: Annotated[str, Field(min_length=3, max_length=254), AfterValidator(_lower_email)]
    password: Password
    turnstile_token: TurnstileToken = None


class PermissionOut(BaseModel):
    read: bool
    write: bool


class AuthStatus(BaseModel):
    app_name: str
    app_tagline: str
    environment: str
    auth_enabled: bool
    auth_bypass: bool
    setup_required: bool
    setup_token_required: bool
    turnstile_enabled: bool
    turnstile_site_key: str | None
    mail_enabled: bool  # forgot-password and email 2FA codes are available
    microsoft_sso_enabled: bool  # show "Sign in with Microsoft"
    csrf_token: str
    user: UserOut | None
    # key -> {read, write} for every page and feature (empty when signed out)
    permissions: dict[str, PermissionOut]
    # Where to send the user after sign-in; null if they can open no page.
    landing_path: str | None


class AuthResult(BaseModel):
    user: UserOut
    csrf_token: str


class LoginResponse(BaseModel):
    """Either a signed-in user, or a second step (2FA) to complete."""

    mfa_required: bool = False
    mfa_method: str | None = None
    challenge_token: str | None = None
    destination_hint: str | None = None  # masked e-mail for emailed codes
    user: UserOut | None = None
    csrf_token: str | None = None


Code = Annotated[str, Field(min_length=6, max_length=32)]


class MfaVerifyRequest(Strict):
    challenge_token: ChallengeToken
    code: Code  # 6-digit code, or a recovery code


class MfaResendRequest(Strict):
    challenge_token: ChallengeToken


class ForgotPasswordRequest(Strict):
    email: Annotated[str, Field(min_length=3, max_length=254), AfterValidator(_lower_email)]
    turnstile_token: TurnstileToken = None


class ResetPasswordRequest(Strict):
    token: Annotated[str, Field(min_length=16, max_length=128)]
    new_password: Password
