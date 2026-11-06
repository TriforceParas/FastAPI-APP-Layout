from __future__ import annotations

import logging

from app.core.config import PROJECT_DIR


def run_migrations() -> None:
    """Apply all pending Alembic migrations (`alembic upgrade head`)."""
    # Alembic logs plugin registration at INFO on import; keep startup quiet.
    logging.getLogger("alembic").setLevel(logging.WARNING)
    from alembic import command
    from alembic.config import Config

    config = Config(str(PROJECT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_DIR / "migrations"))
    config.attributes["skip_logging"] = True  # keep the app's logging config
    command.upgrade(config, "head")
