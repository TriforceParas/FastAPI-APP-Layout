"""Authentication bypass guard.

Auth can be switched off for local development, but only when three
independent conditions are met at request time:

  1. AUTH_ENABLED=false in the environment / .env
  2. The sentinel file (AUTH_BYPASS_FILE, default `.auth-bypass`) exists
  3. APP_ENV is not "production"

The sentinel is excluded by .gitignore and .dockerignore, so a deployed
server never has it. Deleting the file re-enables authentication
immediately, with no restart, because it is checked on every request.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

log = logging.getLogger(__name__)


def auth_bypass_active() -> bool:
    settings = get_settings()
    if settings.auth_enabled or settings.is_production:
        return False
    return settings.auth_bypass_file.is_file()


def describe_auth_mode() -> None:
    """Log the effective auth mode once at startup."""
    settings = get_settings()
    if settings.auth_enabled:
        log.info("Authentication: enabled")
        return
    if settings.is_production:
        log.error("AUTH_ENABLED=false IGNORED: bypass is never allowed when APP_ENV=production")
    elif not settings.auth_bypass_file.is_file():
        log.error(
            "AUTH_ENABLED=false IGNORED: sentinel file %s is missing",
            settings.auth_bypass_file,
        )
    else:
        log.warning(
            "!!! AUTHENTICATION BYPASSED (dev only). Delete %s to re-enable. !!!",
            settings.auth_bypass_file,
        )
