"""One-time setup token that protects the initial registration page.

Without it, anyone who reaches a freshly deployed server before you do
could register the first admin account. The token is written to
`<DATA_DIR>/setup-token` (mode 0600) and printed in the server log, so all
workers share it. It is deleted as soon as the first account exists.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.core.config import get_settings
from app.core.security import new_token

log = logging.getLogger(__name__)


def _token_path() -> Path:
    return get_settings().data_dir / "setup-token"


def ensure_setup_token() -> None:
    settings = get_settings()
    if not settings.setup_token_required or settings.setup_token:
        return
    path = _token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w") as handle:
            handle.write(new_token(18))
    log.warning(
        "Initial setup required. Setup token: %s  (stored in %s)",
        path.read_text().strip(),
        path,
    )


def current_setup_token() -> str | None:
    settings = get_settings()
    if settings.setup_token:
        return settings.setup_token
    try:
        return _token_path().read_text().strip() or None
    except FileNotFoundError:
        return None


def discard_setup_token() -> None:
    _token_path().unlink(missing_ok=True)
