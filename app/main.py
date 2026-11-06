"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.auth_mode import describe_auth_mode
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import new_session
from app.features.auth.sessions import purge_expired_sessions
from app.features.auth.setup_token import discard_setup_token, ensure_setup_token
from app.features.mfa import service as mfa
from app.features.rbac.service import ensure_roles, sync_screens
from app.features.users.models import User
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security import (
    BodySizeLimitMiddleware,
    CSRFMiddleware,
    HostValidationMiddleware,
    SecurityHeadersMiddleware,
)
from app.web.spa import mount_frontend

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.auto_migrate:
        from app.db.migrate import run_migrations

        run_migrations()
    with new_session() as db:
        sync_screens(db)
        ensure_roles(db)
        purge_expired_sessions(db)
        mfa.purge_expired(db)
        has_users = db.query(User.id).first() is not None
    if has_users:
        discard_setup_token()
    else:
        ensure_setup_token()
    describe_auth_mode()
    if settings.is_production and not settings.turnstile_enabled:
        log.warning("Cloudflare Turnstile is DISABLED in production; the login form has no bot protection.")
    yield


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.enable_api_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.enable_api_docs else None,
    )

    # --- Error handling: never leak internals or echo submitted values ----
    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": [str(p) for p in err.get("loc", ())][1:], "msg": err.get("msg", "Invalid value")}
            for err in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    # Unhandled exceptions -> generic 500 with a request id: see RequestIdMiddleware.

    # --- Middleware (last added = outermost) ------------------------------
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(HostValidationMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(AccessLogMiddleware)  # one line per request (inside RequestId, so it has the id)
    app.add_middleware(RequestIdMiddleware)  # outermost: every response and log line gets an id

    app.include_router(api_router)
    mount_frontend(app, settings.frontend_dist)  # must be last: catch-all route
    return app
