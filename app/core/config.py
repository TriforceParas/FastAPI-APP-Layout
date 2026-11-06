"""Application settings, loaded from environment variables and `.env`.

Every setting can be overridden by an environment variable of the same name
(upper-case). Production refuses to start with unsafe values; see
`Settings._enforce_production_safety`.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_DIR = Path(__file__).resolve().parents[2]

log = logging.getLogger(__name__)

CsvList = Annotated[list[str], NoDecode]


class UnsafeConfiguration(RuntimeError):
    pass


# Cloudflare's documented dummy keys (always pass / always block / force challenge).
TURNSTILE_TEST_PREFIXES = ("1x0000", "2x0000", "3x0000")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "Workspace"
    app_tagline: str = "Operations dashboard"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    # text: readable lines for development; json: one JSON object per line for log collectors.
    # Defaults to json in production.
    log_format: Literal["text", "json"] | None = None

    # --- Secrets / database -----------------------------------------------
    secret_key: str = ""
    database_url: str = f"sqlite:///{PROJECT_DIR / 'data' / 'app.db'}"
    data_dir: Path = PROJECT_DIR / "data"
    auto_migrate: bool = True

    # --- Authentication ---------------------------------------------------
    # AUTH_ENABLED=false only takes effect when ALL of these hold:
    #   1. the bypass sentinel file (AUTH_BYPASS_FILE) exists on disk
    #   2. APP_ENV is not "production"
    # The sentinel is git- and docker-ignored, so it never ships to a server.
    auth_enabled: bool = True
    auth_bypass_file: Path = PROJECT_DIR / ".auth-bypass"

    # Initial-registration protection. When required, the first account can
    # only be created with the one-time token printed in the server log
    # (or SETUP_TOKEN if you set one). Defaults to required in production.
    setup_token_required: bool | None = None
    setup_token: str = ""

    session_idle_minutes: int = Field(default=60, ge=5, le=24 * 60)
    session_absolute_hours: int = Field(default=12, ge=1, le=24 * 30)
    login_max_attempts: int = Field(default=5, ge=3, le=50)
    login_lockout_minutes: int = Field(default=15, ge=1, le=24 * 60)

    # --- HTTP hardening ---------------------------------------------------
    allowed_hosts: CsvList = ["localhost", "127.0.0.1"]
    # Origins allowed to make state-changing requests (CSRF origin check).
    allowed_origins: CsvList = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    cookie_secure: bool | None = None
    enable_api_docs: bool | None = None
    max_body_bytes: int = Field(default=1_048_576, ge=1024)

    # --- Cloudflare Turnstile (bot protection on login / first-run setup) ----
    # The defaults in .env.example are Cloudflare's public TEST keys: the widget
    # always passes locally. Production refuses to start with them (see below).
    turnstile_enabled: bool = False
    turnstile_site_key: str = ""
    turnstile_secret_key: str = ""
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    # --- Email -------------------------------------------------------------
    # console:   development only; prints emails (incl. reset links / codes) to the log
    # microsoft: Microsoft 365 / Outlook via the Microsoft Graph API (app registration with
    #            the Mail.Send application permission, client-credentials flow)
    # disabled:  no email; forgot-password and email 2FA codes are unavailable
    mail_provider: Literal["console", "microsoft", "disabled"] = "console"
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    sender_email: str = ""  # the mailbox that sends (must exist in the tenant)
    # Public base URL used in email links, e.g. https://app.example.com
    public_url: str = "http://localhost:8000"
    password_reset_minutes: int = Field(default=30, ge=5, le=24 * 60)

    # --- Sign in with Microsoft (OpenID Connect, Microsoft Entra ID) ----------
    # Adds a "Sign in with Microsoft" button. Only Microsoft accounts whose email
    # domain is in MICROSOFT_SSO_ALLOWED_DOMAINS may sign in this way; password
    # sign-in is unaffected. The app registration needs a Web redirect URI of
    # {PUBLIC_URL}/api/auth/microsoft/callback. Tenant / client id / secret fall
    # back to AZURE_* (the mail app registration) when left empty.
    microsoft_sso_enabled: bool = False
    # A tenant GUID (single organisation, recommended) or "organizations" (any work
    # or school account; production then requires MICROSOFT_SSO_ALLOWED_TENANT_IDS).
    microsoft_sso_tenant_id: str = ""
    microsoft_sso_client_id: str = ""
    microsoft_sso_client_secret: str = ""
    microsoft_sso_allowed_domains: CsvList = []  # e.g. example.com,example.org
    microsoft_sso_allowed_tenant_ids: CsvList = []  # extra pin when the tenant is "organizations"
    # Empty: only existing users can sign in (an admin adds them first). A role name
    # (never the Administrator role): unknown users from allowed domains get an
    # account with that role on first sign-in.
    microsoft_sso_auto_create_role: str = ""
    microsoft_sso_authority: str = "https://login.microsoftonline.com"

    # --- Two-factor authentication -----------------------------------------
    mfa_code_minutes: int = Field(default=10, ge=2, le=60)
    mfa_issuer: str = ""  # shown in authenticator apps; defaults to APP_NAME

    # --- Frontend ---------------------------------------------------------
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"

    @field_validator(
        "allowed_hosts",
        "allowed_origins",
        "microsoft_sso_allowed_domains",
        "microsoft_sso_allowed_tenant_ids",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("microsoft_sso_allowed_domains", "microsoft_sso_allowed_tenant_ids")
    @classmethod
    def _lower_items(cls, value: list[str]) -> list[str]:
        return [item.strip().lower().lstrip("@") for item in value if item.strip()]

    @field_validator("microsoft_sso_authority")
    @classmethod
    def _strip_authority(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("public_url")
    @classmethod
    def _strip_public_url(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("allowed_origins")
    @classmethod
    def _strip_trailing_slash(cls, value: list[str]) -> list[str]:
        return [origin.rstrip("/") for origin in value]

    @field_validator("auth_bypass_file", "data_dir", "frontend_dist")
    @classmethod
    def _resolve_relative(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_DIR / value).resolve()

    @model_validator(mode="after")
    def _apply_environment_defaults(self) -> Settings:
        prod = self.app_env == "production"
        if self.log_format is None:
            self.log_format = "json" if prod else "text"
        if self.cookie_secure is None:
            self.cookie_secure = prod
        if self.enable_api_docs is None:
            self.enable_api_docs = not prod
        if self.setup_token_required is None:
            self.setup_token_required = prod
        if not prod and not self.secret_key:
            self.secret_key = _development_secret(self.data_dir)
        return self

    @property
    def mail_enabled(self) -> bool:
        return self.mail_provider != "disabled"

    def validate_mail(self) -> None:
        if self.mail_provider == "microsoft":
            missing = [
                name
                for name, value in (
                    ("AZURE_TENANT_ID", self.azure_tenant_id),
                    ("AZURE_CLIENT_ID", self.azure_client_id),
                    ("AZURE_CLIENT_SECRET", self.azure_client_secret),
                    ("SENDER_EMAIL", self.sender_email),
                )
                if not value
            ]
            if missing:
                raise UnsafeConfiguration("MAIL_PROVIDER=microsoft requires " + ", ".join(missing))

    # Microsoft SSO values, falling back to the mail app registration.
    @property
    def sso_tenant_id(self) -> str:
        return (self.microsoft_sso_tenant_id or self.azure_tenant_id).strip().lower()

    @property
    def sso_client_id(self) -> str:
        return self.microsoft_sso_client_id or self.azure_client_id

    @property
    def sso_client_secret(self) -> str:
        return self.microsoft_sso_client_secret or self.azure_client_secret

    @property
    def sso_multi_tenant(self) -> bool:
        return self.sso_tenant_id in {"organizations", "common"}

    def validate_microsoft_sso(self) -> None:
        if not self.microsoft_sso_enabled:
            return
        missing = [
            name
            for name, value in (
                ("MICROSOFT_SSO_TENANT_ID (or AZURE_TENANT_ID)", self.sso_tenant_id),
                ("MICROSOFT_SSO_CLIENT_ID (or AZURE_CLIENT_ID)", self.sso_client_id),
                ("MICROSOFT_SSO_CLIENT_SECRET (or AZURE_CLIENT_SECRET)", self.sso_client_secret),
                ("MICROSOFT_SSO_ALLOWED_DOMAINS", self.microsoft_sso_allowed_domains),
            )
            if not value
        ]
        if missing:
            raise UnsafeConfiguration("MICROSOFT_SSO_ENABLED=true requires " + ", ".join(missing))
        if self.sso_tenant_id == "consumers":
            raise UnsafeConfiguration(
                "MICROSOFT_SSO_TENANT_ID=consumers is not supported: personal accounts can't be limited by domain"
            )
        if any("@" in d or "." not in d or "*" in d for d in self.microsoft_sso_allowed_domains):
            raise UnsafeConfiguration("MICROSOFT_SSO_ALLOWED_DOMAINS must be plain domains, e.g. example.com")

    def validate_turnstile(self) -> None:
        if self.turnstile_enabled and not (self.turnstile_site_key and self.turnstile_secret_key):
            raise UnsafeConfiguration("TURNSTILE_ENABLED=true requires TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY")

    @property
    def turnstile_uses_test_keys(self) -> bool:
        return self.turnstile_site_key.startswith(TURNSTILE_TEST_PREFIXES) or self.turnstile_secret_key.startswith(
            TURNSTILE_TEST_PREFIXES
        )

    def enforce_production_safety(self) -> None:
        """Raise if production settings are unsafe. Runs outside pydantic
        validation so error messages never echo setting values (secrets)."""
        if not self.is_production:
            return
        problems: list[str] = []
        if len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be set to at least 32 random characters")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (serve over HTTPS)")
        if "*" in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS must list explicit host names, not '*'")
        if not self.allowed_origins or any(not origin.startswith("https://") for origin in self.allowed_origins):
            problems.append("ALLOWED_ORIGINS must contain only https:// origins")
        if self.mail_provider == "console":
            problems.append("MAIL_PROVIDER=console prints reset links and codes to the log; use microsoft or disabled")
        if not self.public_url.startswith("https://"):
            problems.append("PUBLIC_URL must be an https:// URL (it is used in emailed links)")
        if self.microsoft_sso_enabled and self.sso_multi_tenant and not self.microsoft_sso_allowed_tenant_ids:
            problems.append(
                "MICROSOFT_SSO_TENANT_ID is multi-tenant; set your tenant GUID or MICROSOFT_SSO_ALLOWED_TENANT_IDS "
                "(email domains alone can't be trusted across tenants)"
            )
        if self.turnstile_enabled and self.turnstile_uses_test_keys:
            problems.append("TURNSTILE_* are Cloudflare TEST keys; use your real site and secret keys")
        if problems:
            raise UnsafeConfiguration("Unsafe production configuration: " + "; ".join(problems))

    # --- Derived values ---------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix forces Secure, Path=/ and no Domain attribute.
        return "__Host-session" if self.cookie_secure else "session"

    @property
    def csrf_cookie_name(self) -> str:
        return "__Host-csrf" if self.cookie_secure else "csrf"


def _development_secret(data_dir: Path) -> str:
    """Persist a random key locally so dev sessions survive reloads."""
    data_dir.mkdir(parents=True, exist_ok=True)
    key_file = data_dir / ".dev-secret-key"
    if key_file.is_file():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(48)
    key_file.write_text(key)
    key_file.chmod(0o600)
    log.warning("SECRET_KEY not set; generated a development key at %s", key_file)
    return key


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_turnstile()
    settings.validate_mail()
    settings.validate_microsoft_sso()
    settings.enforce_production_safety()
    return settings
